#!/usr/bin/env python3
"""probe_gate.py — regression gate for the router head.

Runs the natural + edge probe suites against a live anvil and exits non-zero
if accuracy drops below thresholds. Use in CI after head retraining or anvil
changes:

    python3 tools/probe_gate.py --url http://localhost:8097
    python3 tools/probe_gate.py --url http://localhost:8097 --min-nat 0.90 --min-edge-ok 10

Thresholds default to the router3 baselines (nat 0.88, edge-ok 9). Edge probes
score "ok" when the dispatcher abstains/escalates sanely on adversarial input —
a miss is a confidently-wrong route, which is what the gate exists to catch.
"""
import json, os, sys, urllib.request

BASE = "http://localhost:8097"
MIN_NAT = 0.88
MIN_EDGE_OK = 9

def post(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                 headers={"content-type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=15).read())

def run_nat():
    probes = json.load(open(os.path.join(os.path.dirname(__file__), "nat_probes.json")))
    ok, misses = 0, []
    for text, want in probes:
        r = post("/v1/decide", {"state": text})
        got = r.get("choice") or r.get("route")
        if got == want:
            ok += 1
        else:
            misses.append((text[:50], want, got, round(r.get("confidence", 0), 3)))
    return ok, len(probes), misses

def run_edge():
    probes = json.load(open(os.path.join(os.path.dirname(__file__), "edge_probes.json")))
    ok, misses = 0, []
    for row in probes:
        text, want = row[0], row[1]
        r = post("/v1/route", {"state": text})
        got = r.get("route") or r.get("choice")
        safe = got == want or r.get("action") == "delegate" or got == "escalate"
        if safe:
            ok += 1
        else:
            misses.append((text[:50], want, got, round(r.get("confidence", 0), 3)))
    return ok, len(probes), misses

if __name__ == "__main__":
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--url": BASE = args[i + 1]
        if a == "--min-nat": MIN_NAT = float(args[i + 1])
        if a == "--min-edge-ok": MIN_EDGE_OK = int(args[i + 1])
    nat_ok, nat_n, nat_miss = run_nat()
    edge_ok, edge_n, edge_miss = run_edge()
    print(json.dumps({"nat": {"ok": nat_ok, "n": nat_n, "acc": round(nat_ok / nat_n, 3)},
                      "edge": {"ok": edge_ok, "n": edge_n}}))
    for m in nat_miss: print("nat-miss", m)
    for m in edge_miss: print("edge-miss", m)
    fail = nat_ok / nat_n < MIN_NAT or edge_ok < MIN_EDGE_OK
    print("GATE:", "FAIL" if fail else "PASS")
    sys.exit(1 if fail else 0)
