#!/usr/bin/env python3
"""Shadow-lane promotion report.

Reads decisions.jsonl (ANVIL_LOG) rows carrying a "shadow" object written by
ANVIL_SHADOW canary heads, and decides whether the candidate has earned
promotion to the live lane.

Gate (all three must hold to PROMOTE):
  n >= --min-n                    enough paired decisions
  agree_rate >= --agree           raw agreement with the primary route
  wilson_lb(agree) >= --lb        one-sided 95% Wilson lower bound — protects
                                  against promoting on a lucky small sample

We have no ground truth in the log, so this is an agreement gate, not an
accuracy claim: a candidate that systematically disagrees may be *better*
(check disagreements by hand) but cannot be auto-promoted — that needs
labeled eval (lane_verify / risk_coverage) or feedback joins.

Usage:
    python3 tools/shadow_report.py logs/decisions.jsonl --lane it_helpdesk
    python3 tools/shadow_report.py logs/decisions.jsonl --json
Exit 0 promote, 2 hold, 3 insufficient data.
"""
import json, sys, argparse, collections, math

def load(path):
    rows = []
    for l in open(path):
        try:
            r = json.loads(l)
        except Exception:
            continue
        if isinstance(r, dict) and isinstance(r.get("shadow"), dict):
            rows.append(r)
    return rows

def lane_of(r):
    return r.get("expert") or r.get("domain") or r.get("lane") or "default"

def wilson_lb(k, n, z=1.6449):  # one-sided 95%
    if n == 0:
        return 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    return (c - z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d

def report(rs, min_n, agree_t, lb_t):
    n = len(rs)
    agrees = sum(1 for r in rs if r["shadow"].get("agree"))
    rate = agrees / n if n else 0.0
    lb = wilson_lb(agrees, n)
    conf_gap = None
    pc = [r.get("conf") for r in rs if r.get("conf") is not None]
    sc = [r["shadow"].get("conf") for r in rs if r["shadow"].get("conf") is not None]
    if pc and sc:
        conf_gap = round(sum(sc) / len(sc) - sum(pc) / len(pc), 3)
    dis = collections.Counter()
    for r in rs:
        if not r["shadow"].get("agree"):
            dis[(r.get("route"), r["shadow"].get("route"))] += 1
    if n < min_n:
        verdict, code = "insufficient_data", 3
    elif rate >= agree_t and lb >= lb_t:
        verdict, code = "promote", 0
    else:
        verdict, code = "hold", 2
    return {
        "n": n,
        "agree": agrees,
        "agree_rate": round(rate, 4),
        "wilson_lb95": round(lb, 4),
        "conf_gap_shadow_minus_primary": conf_gap,
        "top_disagreements": [{"primary": a, "shadow": b, "n": c} for (a, b), c in dis.most_common(10)],
        "gate": {"min_n": min_n, "agree": agree_t, "lb": lb_t},
        "verdict": verdict,
    }, code

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("--lane", help="only this expert/domain (default: all lanes)")
    ap.add_argument("--min-n", type=int, default=200)
    ap.add_argument("--agree", type=float, default=0.9)
    ap.add_argument("--lb", type=float, default=0.85, help="Wilson lower-bound floor")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    rows = load(a.log)
    by = collections.defaultdict(list)
    for r in rows:
        by[lane_of(r)].append(r)
    lanes = {a.lane: by[a.lane]} if a.lane else by
    if not lanes:
        print(json.dumps({"verdict": "insufficient_data", "n": 0}))
        sys.exit(3)
    out, worst = {}, 0
    for lane, rs in lanes.items():
        rep, code = report(rs, a.min_n, a.agree, a.lb)
        out[lane] = rep
        worst = max(worst, code)
    print(json.dumps(out, indent=2))
    sys.exit(worst)

main()
