#!/usr/bin/env python3
# health_check.py — prod smoke for the whole decision surface.
# Hits /health + all three primitives with known-answer probes.
# Exits 0 if everything answers and every known-answer check passes.
# Usage: health_check.py [port]
import json, sys, urllib.request

BASE = "http://localhost:%s" % (sys.argv[1] if len(sys.argv) > 1 else "8097")

def post(ep, payload):
    req = urllib.request.Request(BASE + ep, data=json.dumps(payload).encode(),
                                 headers={"content-type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=15).read())

def get(ep):
    return json.loads(urllib.request.urlopen(BASE + ep, timeout=10).read())

fails = []

try:
    get("/health")
except Exception as e:
    fails.append(("GET /health", str(e)))

CHECKS = [
    ("/v1/decide", {"state": "what is 123 plus 456?"}, "choice", "calculator"),
    ("/v1/decide", {"state": "tell me a joke"}, "choice", "chat"),
    ("/v1/decide", {"state": "write me a 2000-word essay on Rome"},
        "choice", "escalate"),
    ("/v1/noul", {"state": "write me a 2000-word essay on Rome"},
        "answer", "yes"),
    ("/v1/noul", {"state": "what is the weather in Paris?"}, "answer", "no"),
    ("/v1/score", {"state": "hey whats up"}, "grade", "1"),
    ("/v1/score", {"state": "draft a 40-page market analysis"}, "grade", "4"),
]

for ep, payload, field, expect in CHECKS:
    try:
        r = post(ep, payload)
        got = r.get(field)
        status = "ok" if got == expect else "FAIL"
        if got != expect:
            fails.append((ep + " " + payload["state"], "got %r want %r" % (got, expect)))
        print("%-4s %-11s %-55s -> %s" % (status, ep, payload["state"][:55], got))
    except Exception as e:
        fails.append((ep + " " + payload["state"], str(e)))
        print("FAIL %-11s %-55s -> %s" % (ep, payload["state"][:55], e))

# options masking: constrain decide to a subset
try:
    r = post("/v1/decide", {"state": "what is the weather in Tokyo?",
                            "options": ["chat", "escalate"]})
    ok = r["choice"] in ("chat", "escalate")
    print("%-4s %-11s options-mask -> %s" % ("ok" if ok else "FAIL", "/v1/decide", r["choice"]))
    if not ok:
        fails.append(("options-mask", r["choice"]))
except Exception as e:
    fails.append(("options-mask", str(e)))

print()
if fails:
    print("%d FAILURES" % len(fails)); sys.exit(1)
print("all green")
