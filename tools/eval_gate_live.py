#!/usr/bin/env python3
"""Per-domain gate eval through the LIVE serving path.

Aggregate holdout accuracy hides per-lane regressions — a gate that improved
rpg while breaking tools still wins the aggregate if tools is the smaller
lane. This posts every holdout row to a running router and reports
per-domain accuracy + confusions, so a retrain is judged lane by lane.

  python3 tools/eval_gate_live.py --router http://rbm4:8401 \
      --holdout /root/mtlm/data/moe_gate_holdout.jsonl
"""
import argparse, json, subprocess, sys
from collections import Counter

def route(router, state):
    try:
        p = subprocess.run(
            ["curl", "-s", "-m", "15", "-X", "POST", router + "/v1/route",
             "-H", "content-type: application/json",
             "-d", json.dumps({"state": state})],
            capture_output=True, text=True, timeout=20)
        return json.loads(p.stdout)
    except Exception:
        return {}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--router", required=True)
    ap.add_argument("--holdout", required=True)
    a = ap.parse_args()

    rows = [json.loads(l) for l in open(a.holdout) if l.strip()]
    per_dom = Counter(); per_dom_ok = Counter(); confusions = Counter()
    misses = []
    for r in rows:
        want, state = r.get("expect_tool"), r.get("user") or ""
        if not want or not state:
            continue
        got = route(a.router, state).get("domain") or "(none)"
        per_dom[want] += 1
        if got == want:
            per_dom_ok[want] += 1
        else:
            confusions[(want, got)] += 1
            misses.append({"want": want, "got": got, "state": state[:90]})

    total, ok = sum(per_dom.values()), sum(per_dom_ok.values())
    print(json.dumps({"aggregate": round(ok / max(total, 1), 4),
                      "n": total, "per_domain": {
                          d: f"{per_dom_ok[d]}/{per_dom[d]}"
                          for d in sorted(per_dom)}}))
    for (w, g), n in confusions.most_common():
        print(f"  confuse {w}->{g}: {n}")
    for m in misses[:12]:
        print(f"    {m['want']}->{m['got']}  {m['state']}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
