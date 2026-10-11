#!/usr/bin/env python3
"""bench/oos_eval.py — generic OOS probe for any .head file.

Usage:
  python3 bench/oos_eval.py --head /path/x.head \
      --in-scope probes_in.jsonl --oos probes_oos.jsonl \
      [--abstain escalate,oos] [--hf /root/mtlm/hf/router3s384]

Probe files: jsonl, one {"user"|"text": "..."} per line.
Abstain classes (default: oos,escalate) count as "not leaking" — everything
else is a misroute. Reports per-probe routing + a leak-vs-confidence curve.
Exit 0 always; this is a measurement, not a gate (thresholds are per-lane).
"""
import sys, json, argparse
sys.path.insert(0, "/root/mtlm/tools")
import numpy as np, head_probe as hp, head_io

ap = argparse.ArgumentParser()
ap.add_argument("--head", required=True)
ap.add_argument("--in-scope", required=True)
ap.add_argument("--oos", required=True)
ap.add_argument("--abstain", default="oos,escalate")
ap.add_argument("--hf", default="/root/mtlm/hf/router3s384")
a = ap.parse_args()


def load(p):
    out = []
    for l in open(p):
        r = json.loads(l)
        out.append(r.get("user", r.get("text")))
    return out


texts_in, texts_oos = load(a.in_scope), load(a.oos)
abstain = set(a.abstain.split(","))
h = head_io.load_head(a.head)
rows = [(hp.DECIDE_SYS, [], t[:300], "in") for t in texts_in] + \
       [(hp.DECIDE_SYS, [], t[:300], "oos") for t in texts_oos]
F = hp.features(a.hf, rows)
X = np.concatenate([F[t] for t in h["taps"]], axis=1)
P = head_io.probs(h, X)
nin, labels = len(texts_in), h["labels"]
am, mp = P.argmax(1), P.max(1)
abs_idx = {labels.index(x) for x in abstain if x in labels}

out = {"head": a.head, "labels": labels, "abstain_classes": sorted(abstain & set(labels)),
       "n_in": nin, "n_oos": len(texts_oos)}
leak = np.array([am[i] not in abs_idx for i in range(nin, len(rows))])
out["summary"] = {
    "in_scope_median_conf": float(np.median(mp[:nin])),
    "oos_median_conf": float(np.median(mp[nin:])),
    "oos_abstain_share": float((~leak).mean()),
    "leak_curve": {str(t): float((leak & (mp[nin:] >= t)).mean()) for t in (.3, .5, .7, .9)},
    # coverage[t] = share of in-scope probes still routed (conf >= t) — the
    # deployment cost of gating at t: abstain = 1 - coverage
    "coverage_curve": {str(t): float((mp[:nin] >= t).mean()) for t in (.3, .5, .7, .9)},
}
preds = np.bincount(am[nin:], minlength=len(labels))
out["oos_pred_dist"] = {labels[i]: int(preds[i]) for i in preds.argsort()[::-1] if preds[i]}
out["probes"] = [{"text": t, "route": labels[am[nin + i]], "conf": round(float(mp[nin + i]), 3),
                  "leak": bool(leak[i])} for i, t in enumerate(texts_oos)]
print(json.dumps(out, indent=1, ensure_ascii=False))
