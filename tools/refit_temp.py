#!/usr/bin/env python3
"""Refit a .head's temperature on held-out REAL traffic.

A head's stored T is fit on the training spec's validation split — synthetic
data where margins are clean, so on real traffic confidences saturate ~1.0
even when wrong (measured: fleet gate traffic 65/72 at conf>=0.99 with 61.5%
accuracy, empirical ECE ~0.39). This tool recomputes logits on a labeled
real set, refits T by NLL grid-search on a fit split, and reports acc/ECE
before+after on the disjoint eval split. Accuracy is T-invariant — only
calibration moves.

  python3 tools/refit_temp.py --hf /tmp/hf-m7router3s384 \
      --head models/machin_fit.head --labels data/machinfit_real.jsonl \
      --fit-frac 0.6 --out models/machin_fit.recal.head

--labels rows are spec-format jsonl (system/context/user/expect_tool) — the
same shape train_head.py consumes; labels must match the head's route names.
Without --out it is a dry-run report; nothing is written.
"""
import argparse, json, struct, sys

import numpy as np

from train_head import hidden_states, load_specs, softmax, fit_temperature, ece


def read_head(path):
    raw = open(path, "rb").read()
    if raw[:4] != b"mhd1":
        sys.exit(f"bad magic in {path}")
    nr, dim, T = struct.unpack("<i i f", raw[4:16])
    wend = 16 + nr * dim * 4
    W = np.frombuffer(raw[16:wend], dtype="<f4").reshape(nr, dim).astype(np.float64)
    b = np.frombuffer(raw[wend:wend + nr * 4], dtype="<f4").astype(np.float64)
    names, off = [], wend + nr * 4
    for _ in range(nr):
        n = raw[off]; off += 1
        names.append(raw[off:off + n].decode()); off += n
    return raw, nr, dim, T, W, b, names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hf", required=True, help="HF bundle of the head's trunk")
    ap.add_argument("--head", required=True)
    ap.add_argument("--labels", required=True, help="real-traffic labeled spec jsonl")
    ap.add_argument("--fit-frac", type=float, default=0.6)
    ap.add_argument("--mode", choices=["nll", "marginal"], default="marginal",
                    help="nll: classic NLL-optimal T (right answer when the head "
                         "is mostly right). marginal: pick T so mean confidence "
                         "equals empirical accuracy on the fit split — a head "
                         "that is wrong a lot reports honestly-low confidence "
                         "and the abstention gate fires, which is the correct "
                         "product behavior for an untrusted head.")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    raw, nr, dim, T_old, W, b, names = read_head(a.head)
    nix = {n: i for i, n in enumerate(names)}
    rows = [r for r in load_specs(a.labels) if r[3] in nix]
    dropped = sum(1 for r in load_specs(a.labels) if r[3] not in nix)
    y = np.array([nix[r[3]] for r in rows])
    print(f"head: {nr} routes, dim {dim}, stored T={T_old:.3f}; "
          f"labels: {len(rows)} usable rows ({dropped} dropped, label not in head)",
          file=sys.stderr)

    H = hidden_states(a.hf, rows, a.batch)
    Z = H @ W.T + b                      # pre-temperature logits
    rng = np.random.default_rng(a.seed)
    perm = rng.permutation(len(rows))
    nf = max(1, int(len(rows) * a.fit_frac))
    fi, ei = perm[:nf], perm[nf:]

    if a.mode == "nll":
        T_new = fit_temperature(Z[fi], y[fi])
    else:
        # marginal calibration: binary-search T until mean top-prob on the fit
        # split equals its empirical accuracy there. conf is monotone
        # decreasing in T, acc is T-invariant.
        acc_fit = float((Z[fi].argmax(1) == y[fi]).mean())
        lo, hi = 0.05, 512.0
        for _ in range(40):
            mid = (lo * hi) ** 0.5
            mc = float(softmax(Z[fi] / mid).max(1).mean())
            if mc > acc_fit:
                lo = mid
            else:
                hi = mid
        T_new = (lo * hi) ** 0.5
    out = {"head": a.head, "mode": a.mode, "T_stored": round(T_old, 3),
           "T_refit": round(T_new, 3), "fit_n": len(fi),
           "fit_acc": round(float((Z[fi].argmax(1) == y[fi]).mean()), 4)}
    if len(ei):
        P_old = softmax(Z[ei] / T_old)
        P_new = softmax(Z[ei] / T_new)
        out.update({"eval_n": len(ei),
                    "acc": round(float((P_old.argmax(1) == y[ei]).mean()), 4),
                    "ece_stored_T": round(ece(P_old, y[ei]), 4),
                    "ece_refit_T": round(ece(P_new, y[ei]), 4),
                    "mean_conf_stored": round(float(P_old.max(1).mean()), 4),
                    "mean_conf_refit": round(float(P_new.max(1).mean()), 4)})
    else:
        out["warn"] = "fit-frac 1.0 — T fit on all rows, no eval split"
    print(json.dumps(out))

    if a.out:
        patched = raw[:12] + struct.pack("<f", T_new) + raw[16:]
        with open(a.out, "wb") as f:
            f.write(patched)
        print(json.dumps({"wrote": a.out, "T": round(T_new, 3)}))


if __name__ == "__main__":
    main()
