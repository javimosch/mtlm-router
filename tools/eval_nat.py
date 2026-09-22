#!/usr/bin/env python3
# eval_nat.py — handwritten off-template probes through /v1/decide.
# The honest generalization check: none of these phrasings are in the
# synthetic corpus. Usage: eval_nat.py [port]
import json, os, urllib.request, sys

BASE = "http://localhost:%s" % (sys.argv[1] if len(sys.argv) > 1 else "8097")
probes = json.load(open(os.path.join(os.path.dirname(__file__), "nat_probes.json")))
ok = 0; misses = []; conf_sum = 0
for text, expect in probes:
    req = urllib.request.Request(BASE + "/v1/decide",
        data=json.dumps({"state": text}).encode(),
        headers={"content-type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=10).read())
    conf_sum += r["confidence"]
    if r["choice"] == expect: ok += 1
    else: misses.append((text, expect, r["choice"], round(r["confidence"], 3)))
print(json.dumps({"n": len(probes), "acc": round(ok / len(probes), 4),
    "mean_conf": round(conf_sum / len(probes), 3), "n_miss": len(misses)}))
for m in misses: print("MISS", m)
