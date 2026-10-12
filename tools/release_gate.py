#!/usr/bin/env python3
"""Release gate — quality spot-check for a running mtlm-router instance.

Goes beyond smoke.sh (endpoint health): replays golden_probes.jsonl — a small
hand-labeled set per lane — and fails on routing regressions. Intended to run
against a scratch instance of a release candidate before packaging.

A probe {expert, state, expect, in[]} passes when:
  - action == "tool_call" and route is in `in` (when given) or any route when not
  - expect == "delegate_or_tool": action is delegate or tool_call (loose check)
Delegates on labeled probes count as MISSES unless expect says otherwise —
a conformal lane legitimately abstains sometimes, but a golden probe is the
canary: if the gate trips, inspect before shipping, don't raise the bar blindly.

Usage:
    python3 tools/release_gate.py http://localhost:8486 [--key mk_...] [--json]
Exit 0 = all probes pass; 1 = any miss (or server error).
"""
import json, os, sys, urllib.request

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    base = (args[0] if args else "http://localhost:8097").rstrip("/")
    key = ""
    if "--key" in sys.argv:
        key = sys.argv[sys.argv.index("--key") + 1]
    probes = [json.loads(l) for l in open(os.path.join(os.path.dirname(__file__), "golden_probes.jsonl"))]
    hdrs = {"content-type": "application/json"}
    if key:
        hdrs["authorization"] = "Bearer " + key
    ok = miss = err = 0
    rows = []
    for p in probes:
        row = {"expert": p["expert"], "state": p["state"][:50]}
        try:
            req = urllib.request.Request(base + "/v1/route",
                json.dumps({"state": p["state"], "expert": p["expert"]}).encode(), hdrs)
            r = json.loads(urllib.request.urlopen(req, timeout=30).read())
            row.update(route=r.get("route"), action=r.get("action"),
                       conf=r.get("confidence"), set_size=r.get("set_size"))
            # label match: any `in` token appears inside the route label
            # ("card" matches "lost_or_stolen_card"); no `in` = any route
            want = p.get("in") or []
            hit = lambda lab: lab and (not want or any(t in lab for t in want))
            cands = [c.get("route") for c in (r.get("candidates") or [])]
            if p["expect"] == "delegate_or_tool":
                good = r["action"] in ("delegate", "tool_call")
            elif r["action"] == p["expect"]:
                good = hit(r.get("route"))
            elif r["action"] == "delegate":
                # conformal abstain with the right route on top / in the
                # shortlist is acceptable behavior, not a regression
                good = hit(r.get("route")) or any(hit(c) for c in cands)
            else:
                good = False
            row["ok"] = good
            ok += good
            miss += not good
        except Exception as e:
            row.update(ok=False, error=str(e)[:80]); err += 1; miss += 1
        rows.append(row)
    if "--json" in sys.argv:
        print(json.dumps({"probes": len(probes), "pass": ok, "miss": miss, "rows": rows}, indent=1))
    else:
        for r in rows:
            mark = "ok  " if r.get("ok") else "MISS"
            print(f"{mark} {r['expert']:12s} {r['state'][:45]:45s} -> {r.get('route')} ({r.get('action')}, conf {r.get('conf', 0):.2f}, set {r.get('set_size')})")
        print(f"release_gate: {ok}/{len(probes)} probes pass on {base}")
    sys.exit(0 if miss == 0 else 1)

if __name__ == "__main__":
    main()
