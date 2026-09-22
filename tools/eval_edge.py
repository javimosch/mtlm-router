#!/usr/bin/env python3
# eval_edge.py — adversarial/edge probes through /v1/assess.
# edge_probes.json rows are [state, expected_choice|null] or
# [state, expected_choice|null, context[]]; null = observe-only.
# Expected a dispatcher to reject, abstain, or route sanely — never crash and
# never confident-wrong on garbage. Usage: eval_edge.py [port]
import json, os, urllib.request, sys

BASE = "http://localhost:%s" % (sys.argv[1] if len(sys.argv) > 1 else "8097")
probes = json.load(open(os.path.join(os.path.dirname(__file__), "edge_probes.json")))
ok = miss = obs = err = 0
for row in probes:
    text, expect = row[0], row[1]
    ctx = row[2] if len(row) > 2 else None
    try:
        body = {"state": text}
        if ctx: body["context"] = ctx
        req = urllib.request.Request(BASE + "/v1/assess",
            data=json.dumps(body).encode(),
            headers={"content-type": "application/json"})
        r = json.loads(urllib.request.urlopen(req, timeout=15).read())
        ch, cf = r["decision"]["choice"], r["decision"]["confidence"]
        nl = r.get("noul", {}).get("probability", 0)
        tag = repr(text[:40])
        if expect is None:
            print("OBS  %-42s -> %s @%.2f noul %.2f" % (tag, ch, cf, nl)); obs += 1
        elif ch == expect:
            print("ok   %-42s -> %s @%.2f" % (tag, ch, cf)); ok += 1
        else:
            print("MISS %-42s -> %s @%.2f (want %s) noul %.2f" % (tag, ch, cf, expect, nl)); miss += 1
    except Exception as e:
        # a 400 reject is correct behavior for empty/overlong/binary states
        if expect is None or "400" in str(e):
            print("REJ  %-42r -> %s" % (text[:40], e)); obs += 1
        else:
            print("ERR  %-42r -> %s" % (text[:40], e)); err += 1
print(json.dumps({"ok": ok, "miss": miss, "observed": obs, "err": err}))
