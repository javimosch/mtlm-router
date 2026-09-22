#!/usr/bin/env python3
"""Train a route-decision head on frozen mtlm weights (Jev-style: score, don't generate).

Reads hidden states at the last prompt position (post final rmsnorm == the tensor
anvil keeps in s_x) for every spec probe, then fits softmax regression over the
route labels. Writes models/<name>.head consumed by anvil's /v1/decide endpoint.

Usage:
  python3 tools/synth_tools.py --eval 4000 555      # big labeled spec (incl. chat rows)
  python3 tools/synth_tools.py --eval 560 777       # held-out spec, different seed
  python3 tools/train_head.py --hf /tmp/hf-m7router1 \
      --spec data/eval_exact.jsonl --eval-spec data/eval_holdout.jsonl \
      --out models/m7router1.head
"""
import argparse, json, struct, sys
import numpy as np

def load_specs(path):
    rows = [json.loads(l) for l in open(path) if l.strip()]
    return [(p["system"], p.get("context") or [], p["user"], p["expect_tool"] or "chat") for p in rows]

def hidden_states(hfdir, rows, batch=32):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(hfdir)
    model = AutoModelForCausalLM.from_pretrained(hfdir, output_hidden_states=True)
    model.eval()
    H = np.zeros((len(rows), model.config.hidden_size), dtype=np.float32)
    with torch.no_grad():
        for i in range(0, len(rows), batch):
            chunk = rows[i:i + batch]
            # per-text tokenize (template emits BOS itself); RIGHT-pad so real
            # tokens keep RoPE positions; causal attn => pads can't leak back.
            idl = []
            for s, cx, u, _ in chunk:
                # context turns alternate user/assistant, oldest first — same
                # rendering as anvil's head_prefill.
                msgs = [{"role": "system", "content": s}]
                msgs += [{"role": "user" if k % 2 == 0 else "assistant", "content": c}
                         for k, c in enumerate(cx)]
                msgs.append({"role": "user", "content": u})
                enc = tok.apply_chat_template(msgs, add_generation_prompt=True)
                ids = enc["input_ids"] if hasattr(enc, "keys") else enc
                ids = ids[0] if ids and isinstance(ids[0], list) else ids
                idl.append(list(ids))
            ml = max(len(x) for x in idl)
            ii = torch.tensor([x + [0] * (ml - len(x)) for x in idl])
            am = torch.tensor([[1] * len(x) + [0] * (ml - len(x)) for x in idl])
            out = model(input_ids=ii, attention_mask=am)
            hsd = out.hidden_states[-1]  # post final rmsnorm == anvil s_x
            for j, x in enumerate(idl):
                H[i + j] = hsd[j, len(x) - 1, :].float().cpu().numpy()
            print(f"  hidden {i + len(chunk)}/{len(rows)}", file=sys.stderr)
    return H

def softmax(z):
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)

def train_lr(H, y, ncls, iters=600, lr=0.05, l2=1e-4):
    W = np.zeros((ncls, H.shape[1]), dtype=np.float64)
    b = np.zeros(ncls, dtype=np.float64)
    X = H.astype(np.float64)
    Y = np.eye(ncls)[y]
    n = len(X)
    for it in range(iters):
        P = softmax(X @ W.T + b)
        G = (P - Y) / n
        W -= lr * (G.T @ X + l2 * W)
        b -= lr * G.sum(axis=0)
        if it % 100 == 0:
            loss = -np.log(np.maximum((P * Y).sum(1), 1e-12)).mean()
            print(f"  it {it} nll {loss:.4f}", file=sys.stderr)
    return W.astype(np.float32), b.astype(np.float32)

def fit_temperature(Z, y):
    # grid search T minimizing val NLL — enough for a calibration knob
    best_t, best_nll = 1.0, 1e18
    for t in np.linspace(0.25, 8.0, 128):
        p = softmax(Z / t)
        nll = -np.log(np.maximum(p[np.arange(len(y)), y], 1e-12)).mean()
        if nll < best_nll:
            best_nll, best_t = nll, t
    return float(best_t)

def ece(P, y, nb=10):
    conf = P.max(1); corr = (P.argmax(1) == y)
    e = 0.0
    for lo in np.linspace(0, 1, nb + 1)[:-1]:
        m = (conf >= lo) & (conf < lo + 1.0 / nb)
        if m.sum():
            e += m.mean() * abs(corr[m].mean() - conf[m].mean())
    return float(e)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hf", required=True)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--eval-spec", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--lr", type=float, default=0.05)
    ap.add_argument("--iters", type=int, default=600)
    ap.add_argument("--standardize", action="store_true",
                    help="z-score hidden states before LR; the scaler is folded "
                         "into W,b so the .head format and anvil stay unchanged")
    a = ap.parse_args()

    rows = load_specs(a.spec)
    labels = sorted(set(r[3] for r in rows))
    lix = {n: i for i, n in enumerate(labels)}
    y = np.array([lix[r[3]] for r in rows])
    print(f"spec: {len(rows)} rows, {len(labels)} routes: {labels}", file=sys.stderr)

    H = hidden_states(a.hf, rows, a.batch)
    mu = sd = None
    if a.standardize:
        mu, sd = H.mean(0), H.std(0) + 1e-6
        H = (H - mu) / sd
    rng = np.random.default_rng(0)
    perm = rng.permutation(len(rows))
    nval = max(200, len(rows) // 5)
    va, tr = perm[:nval], perm[nval:]
    W, b = train_lr(H[tr], y[tr], len(labels), lr=a.lr, iters=a.iters)
    Zv = H[va] @ W.T + b
    T = fit_temperature(Zv, y[va])
    Pv = softmax(Zv / T)
    acc = float((Pv.argmax(1) == y[va]).mean())
    print(json.dumps({"val_n": len(va), "acc": round(acc, 4),
                      "ece": round(ece(Pv, y[va]), 4), "T": round(T, 3)}))

    # full retrain on train+val at the end so the artifact sees all data
    W, b = train_lr(H, y, len(labels), lr=a.lr, iters=a.iters)
    if a.standardize:
        # fold the scaler into the linear head: anvil sees raw s_x
        Ws = W / sd
        W, b = Ws, b - Ws @ mu

    if a.eval_spec:
        er = [r for r in load_specs(a.eval_spec) if r[3] in lix]
        ey = np.array([lix[r[3]] for r in er])
        EH = hidden_states(a.hf, er, a.batch)
        # W,b are already folded into raw space when --standardize — score raw
        EP = softmax((EH @ W.T + b) / T)
        pred = EP.argmax(1)
        conf = {}
        for i, r in enumerate(er):
            conf.setdefault(r[3], {}).setdefault(labels[pred[i]], 0)
            conf[r[3]][labels[pred[i]]] += 1
        print(json.dumps({"eval_n": len(er), "acc": round(float((pred == ey).mean()), 4),
                          "ece": round(ece(EP, ey), 4), "confusion": conf}))

    # head.bin: magic 'mhd1' + nr + dim + T + W[nr*dim] + b[nr] + per-name u8len+bytes
    with open(a.out, "wb") as f:
        f.write(struct.pack("<4s i i f", b"mhd1", len(labels), W.shape[1], T))
        f.write(W.astype("<f4").tobytes())
        f.write(b.astype("<f4").tobytes())
        for n in labels:
            nb = n.encode()
            f.write(struct.pack("<B", len(nb)) + nb)
    print(json.dumps({"wrote": a.out, "routes": len(labels), "dim": int(W.shape[1]), "T": T}))

if __name__ == "__main__":
    main()
