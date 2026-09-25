#!/usr/bin/env python3
"""Light head-training probe on the REAL fleet labels: is the 0.48 holdout ceiling a feature choice?

train_head.py fits softmax regression on ONE feature: the last hidden state at the last prompt
position. This sweeps cheap alternatives on the frozen trunk without touching it:
  layers  -1 (post-norm, what anvil serves), -2, -3, -4, and a concat of the last two
  pooling last-token | mean over the user turn | max over the user turn
  classifiers  softmax regression (L2 sweep) | prototype (nearest class centroid, cosine) | kNN (k=3,5)
Reports 5-fold CV on the train rows AND the disjoint holdout for every combination, plus
confident-wrong counts (conf >= 0.9). CPU-only, minutes on 7M params.

  python3 tools/head_probe.py --hf hf-m7router3s384 --train data/machinfit_real.jsonl \
      --holdout data/machinfit_holdout27.jsonl [--extra data/hitl_machinfit.jsonl]
"""
import argparse, json, sys
import numpy as np

DEFAULT_SYSTEM = "You are a prospect classifier for machin."
def load(path):
    rows = [json.loads(l) for l in open(path) if l.strip()]
    # hitl_*.jsonl rows carry the issue text under "state" and no system prompt
    return [(r.get("system") or DEFAULT_SYSTEM, r.get("context") or [], r.get("user") or r.get("state") or "",
             r.get("expect_tool") or "chat") for r in rows]

def features(hfdir, rows, batch=16):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(hfdir)
    model = AutoModelForCausalLM.from_pretrained(hfdir, output_hidden_states=True); model.eval()
    _m = [{"role": "user", "content": "x"}]
    _a = tok.apply_chat_template(_m, add_generation_prompt=True); _a = _a["input_ids"] if hasattr(_a, "keys") else _a; _a = _a[0] if _a and isinstance(_a[0], list) else _a
    _b = tok.apply_chat_template(_m, add_generation_prompt=False); _b = _b["input_ids"] if hasattr(_b, "keys") else _b; _b = _b[0] if _b and isinstance(_b[0], list) else _b
    TAIL = len(_a) - len(_b)  # "<|assistant|>\n" generation tail (anvil: tail_len)
    feats = {}  # (layer, pooling) -> [n, d]
    with torch.no_grad():
        for i in range(0, len(rows), batch):
            chunk = rows[i:i + batch]; idl = []; ulen = []
            for s, cx, u, _ in chunk:
                msgs = [{"role": "system", "content": s}]
                msgs += [{"role": "user" if k % 2 == 0 else "assistant", "content": c} for k, c in enumerate(cx)]
                pre = tok.apply_chat_template(msgs, add_generation_prompt=False)
                pre = pre["input_ids"] if hasattr(pre, "keys") else pre
                pre = pre[0] if pre and isinstance(pre[0], list) else pre
                msgs.append({"role": "user", "content": u})
                enc = tok.apply_chat_template(msgs, add_generation_prompt=True)
                ids = enc["input_ids"] if hasattr(enc, "keys") else enc
                ids = ids[0] if ids and isinstance(ids[0], list) else ids
                # anvil head_prefill pools the rendered LAST USER TURN only: "<|user|>\n" + state + "</s>\n",
                # i.e. everything after the prior messages and before the "<|assistant|>\n" generation tail.
                idl.append(list(ids)); ulen.append((len(pre), len(ids) - TAIL))
            ml = max(len(x) for x in idl)
            ii = torch.tensor([x + [0] * (ml - len(x)) for x in idl])
            am = torch.tensor([[1] * len(x) + [0] * (ml - len(x)) for x in idl])
            out = model(input_ids=ii, attention_mask=am)
            hs = out.hidden_states  # tuple: embeddings + one per layer; [-1] is post final norm
            for li in (-1, -2, -3, -4):
                H = hs[li].float().cpu().numpy()
                for j, x in enumerate(idl):
                    a, b = ulen[j]; span = H[j, a:b, :] if b > a else H[j, :b, :]
                    feats.setdefault((li, "last"), []).append(H[j, len(x) - 1, :])
                    feats.setdefault((li, "mean"), []).append(span.mean(axis=0))
                    feats.setdefault((li, "max"), []).append(span.max(axis=0))
            print(f"  features {i + len(chunk)}/{len(rows)}", file=sys.stderr)
    return {k: np.stack(v) for k, v in feats.items()}

def softmax(z):
    z = z - z.max(axis=1, keepdims=True); e = np.exp(z); return e / e.sum(axis=1, keepdims=True)

def fit_lr(X, y, ncls, l2, iters=800, lr=0.05):
    W = np.zeros((X.shape[1], ncls)); b = np.zeros(ncls); Y = np.eye(ncls)[y]
    for _ in range(iters):
        P = softmax(X @ W + b); G = P - Y
        W -= lr * (X.T @ G / len(X) + l2 * W); b -= lr * G.mean(axis=0)
    return W, b

def feat_sd(X):
    # floor each feature's sd at 10% of the global sd: a max-pooled dimension that hits the same value in every
    # row has sd~0, and folding 1/sd into the served head then amplifies int8 rounding by 1e4x (saw W~4e4, b~8e4,
    # every anvil answer saturated to one class while fp32 numpy said another).
    sd = X.std(axis=0); return np.maximum(sd, 0.1 * X.std() + 1e-6)

def standardize(Xtr, Xte):
    mu = Xtr.mean(axis=0); sd = feat_sd(Xtr)
    return (Xtr - mu) / sd, (Xte - mu) / sd

def eval_clf(kind, Xtr, ytr, Xte, yte, ncls, param):
    if kind == "lr":
        Xtr2, Xte2 = standardize(Xtr, Xte); W, b = fit_lr(Xtr2, ytr, ncls, param)
        P = softmax(Xte2 @ W + b); pred = P.argmax(1); conf = P.max(1)
    elif kind == "proto":
        n = lambda A: A / (np.linalg.norm(A, axis=1, keepdims=True) + 1e-9)
        C = np.stack([n(Xtr[ytr == c]).mean(axis=0) if (ytr == c).any() else np.zeros(Xtr.shape[1]) for c in range(ncls)])
        S = n(Xte) @ n(C).T; pred = S.argmax(1); conf = softmax(S * 10).max(1)
    else:  # knn
        k = param; n = lambda A: A / (np.linalg.norm(A, axis=1, keepdims=True) + 1e-9)
        S = n(Xte) @ n(Xtr).T; idx = np.argsort(-S, axis=1)[:, :k]
        votes = np.zeros((len(Xte), ncls))
        for r in range(len(Xte)):
            for j in idx[r]: votes[r, ytr[j]] += 1
        pred = votes.argmax(1); conf = votes.max(1) / k
    acc = float((pred == yte).mean()); cw = int(((pred != yte) & (conf >= 0.9)).sum())
    return acc, cw

def cv(kind, X, y, ncls, param, folds=5, seed=0):
    rng = np.random.RandomState(seed); order = rng.permutation(len(X)); accs = []
    for f in range(folds):
        te = order[f::folds]; tr = np.setdiff1d(order, te)
        accs.append(eval_clf(kind, X[tr], y[tr], X[te], y[te], ncls, param)[0])
    return float(np.mean(accs))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hf", required=True); ap.add_argument("--train", required=True); ap.add_argument("--holdout", required=True)
    ap.add_argument("--extra", default=None, help="more labeled rows folded into train")
    ap.add_argument("--emit", default=None, help="write an mhd2 .head trained on ALL rows with --emit-layer/--emit-pool/--emit-l2")
    ap.add_argument("--emit-layer", type=int, default=-2, help="HF hidden_states index (-2 = output of layer n-2 = ANVIL_POOL_LAYER -2)")
    ap.add_argument("--emit-pool", default="max", choices=["max", "mean", "last"])
    ap.add_argument("--emit-l2", type=float, default=1e-3)
    ap.add_argument("--emit-temp", default="1.0", help="mhd2 temp field: a float, or 'auto' = fit T on holdout logits of a train-only head (NLL grid, as train_head.py); prod heads use calibrated T (0.61-1.04), T=1.0 over-confidences pooled heads")
    ap.add_argument("--maxc", type=int, default=0, help="truncate the user text to N chars (real fleet rows exceed the 384 context; anvil 400s above it)")
    ap.add_argument("--serve-system", action="store_true", help="compute features under anvil's FIXED decide_sys prompt (what /v1/decide and /v1/route actually use), not the rows' own system text")
    a = ap.parse_args()
    tr = load(a.train) + (load(a.extra) if a.extra else []); ho = load(a.holdout)
    if a.maxc: tr = [(s_, c, u[:a.maxc], y) for s_, c, u, y in tr]; ho = [(s_, c, u[:a.maxc], y) for s_, c, u, y in ho]
    if a.serve_system:
        DS = "You are a helpful assistant. You can call tools. When a tool is needed, reply with only the JSON tool call. Otherwise answer in plain English."
        tr = [(DS, c, u, y) for s_, c, u, y in tr]; ho = [(DS, c, u, y) for s_, c, u, y in ho]
    labels = sorted({r[3] for r in tr + ho}); lab = {l: i for i, l in enumerate(labels)}
    ytr = np.array([lab[r[3]] for r in tr]); yho = np.array([lab[r[3]] for r in ho])
    print(json.dumps({"train_rows": len(tr), "holdout_rows": len(ho), "labels": labels,
                      "train_dist": np.bincount(ytr, minlength=len(labels)).tolist(), "holdout_dist": np.bincount(yho, minlength=len(labels)).tolist()}))
    F = features(a.hf, tr + ho)
    n = len(tr); results = []
    for (li, pool), X in sorted(F.items()):
        Xtr, Xho = X[:n], X[n:]
        for kind, params in (("lr", [1e-4, 1e-3, 1e-2, 1e-1]), ("proto", [0]), ("knn", [3, 5])):
            for p in params:
                c = cv(kind, Xtr, ytr, len(labels), p)
                acc, cw = eval_clf(kind, Xtr, ytr, Xho, yho, len(labels), p)
                results.append({"layer": li, "pool": pool, "clf": kind, "param": p, "cv5": round(c, 3), "holdout": round(acc, 3), "conf_wrong": cw})
    # concat of last two layers, last-token
    X = np.concatenate([F[(-1, "last")], F[(-2, "last")]], axis=1); Xtr, Xho = X[:n], X[n:]
    for p in (1e-3, 1e-2):
        c = cv("lr", Xtr, ytr, len(labels), p); acc, cw = eval_clf("lr", Xtr, ytr, Xho, yho, len(labels), p)
        results.append({"layer": "-1+-2", "pool": "last", "clf": "lr", "param": p, "cv5": round(c, 3), "holdout": round(acc, 3), "conf_wrong": cw})
    results.sort(key=lambda r: (-r["holdout"], -r["cv5"]))
    base = [r for r in results if r["layer"] == -1 and r["pool"] == "last" and r["clf"] == "lr"]
    print("BASELINE (what train_head.py does: layer -1, last token, LR):", json.dumps(base))
    print("TOP 12:")
    for r in results: print(json.dumps(r))  # full sweep; sorted best-first
    print(f"majority-class holdout baseline: {np.bincount(yho).max() / len(yho):.3f}")
    if a.emit:
        # anvil mhd2: magic "mhd2", i32 nr, i32 dim, f32 temp, u32 flags, W[nr*dim] f32 (row = class), b[nr] f32,
        # then names as (u8 len + bytes). flags = pool_kind | ((pool_layer + 1) << 4), pool_kind 1=max 2=mean 0=last,
        # pool_layer = anvil layer index (tap after that layer) = n_layers + hf_index for hf_index < 0 ... but HF
        # hidden_states[-1] is post-final-norm, so hf_index -2 -> after layer n-2 -> ANVIL_POOL_LAYER -2. Match exactly:
        # anvil pool_layer = n_layers + hf_index (hf_index in -2..-n_layers); "last"/"final" = flags 0 or kind|(0<<4).
        X = np.concatenate([F[(a.emit_layer, a.emit_pool)]], axis=1); Xall = X; yall = np.concatenate([ytr, yho])
        mu = Xall.mean(axis=0); sd = feat_sd(Xall); Xs = (Xall - mu) / sd
        W, b = fit_lr(Xs, yall, len(labels), a.emit_l2)
        # fold the standardization into the affine head so anvil applies raw features: z = ((x-mu)/sd) W + b
        Wr = W / sd[:, None]; br = b - (mu / sd) @ W
        if a.emit_temp == "auto":
            # calibrate on rows the head did not see: fit on train only, grid-search T on holdout NLL
            Xt, Xh = X[:n], X[n:]; mu_t = Xt.mean(axis=0); sd_t = feat_sd(Xt)
            Wt, bt = fit_lr((Xt - mu_t) / sd_t, ytr, len(labels), a.emit_l2); Z = ((Xh - mu_t) / sd_t) @ Wt + bt
            temp, best_nll = 1.0, 1e18
            for t in np.exp(np.linspace(np.log(0.25), np.log(64.0), 200)):
                P = softmax(Z / t); nll = -np.log(np.maximum(P[np.arange(len(yho)), yho], 1e-12)).mean()
                if nll < best_nll: best_nll, temp = nll, float(t)
            print(json.dumps({"emit_temp": round(temp, 4), "holdout_nll": round(float(best_nll), 4), "holdout_acc_train_only": round(float((Z.argmax(1) == yho).mean()), 4)}))
        else:
            temp = float(a.emit_temp)
        print(json.dumps({"emit_cond": {"W_absmax": float(np.abs(Wr).max()), "b_absmax": float(np.abs(br).max()), "sd_min": float(sd.min())}}))
        import struct
        nl = 6  # m7 trunk depth; anvil layer index for the tap
        if a.emit_pool == "last": flags = 0
        else:
            kind = 1 if a.emit_pool == "max" else 2
            layer = nl + a.emit_layer if a.emit_layer < 0 else a.emit_layer
            flags = kind | ((layer + 1) << 4)
        with open(a.emit, "wb") as f:
            f.write(struct.pack("<i", 0x3264686d)); f.write(struct.pack("<i", len(labels))); f.write(struct.pack("<i", X.shape[1]))
            f.write(struct.pack("<f", temp)); f.write(struct.pack("<I", flags))
            f.write(Wr.T.astype(np.float32).tobytes())  # [nr][dim] rows = classes
            f.write(br.astype(np.float32).tobytes())
            for l in labels: f.write(bytes([len(l)])) ; f.write(l.encode())
        print(json.dumps({"emitted": a.emit, "flags": flags, "temp": round(temp, 4), "pool": a.emit_pool, "hf_layer": a.emit_layer, "classes": labels, "rows": int(len(yall))}))

if __name__ == "__main__":
    main()
