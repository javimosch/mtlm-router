#!/usr/bin/env python3
# jev_demo.py — one-shot demo of the Jev-style decision surface on anvil.
# Hits all three primitives + the router gate on live prompts.
# Usage: jev_demo.py [--port 8097]
import json, sys, urllib.request

PORT = "8097"
args = sys.argv[1:]
if "--port" in args:
    i = args.index("--port"); PORT = args[i + 1]
BASE = "http://localhost:%s" % PORT

def post(ep, payload):
    req = urllib.request.Request(BASE + ep, data=json.dumps(payload).encode(),
                                 headers={"content-type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())

PROMPTS = [
    "what's the weather like in Paris right now?",
    "quick maths: 47 times 23",
    "remind me to water the plants tomorrow",
    "write me a long essay on the Roman Empire",
    "lol that's hilarious",
    "what is the meaning of life, the universe and everything?",
]

print("== /v1/decide (choice) + /v1/noul (escalate?) + /v1/score (complexity)")
print("%-58s %-12s %-6s %-5s %-6s" % ("state", "route", "conf", "noul", "grade"))
for s in PROMPTS:
    d = post("/v1/decide", {"state": s})
    n = post("/v1/noul", {"state": s})
    sc = post("/v1/score", {"state": s})
    print("%-58s %-12s %-6s %-5s %-6s" % (
        s[:56], d["choice"], round(d["confidence"], 3),
        "%.2f" % n["probability"], sc["grade"]))

print()
print("== options masking (Jev question constraint)")
d = post("/v1/decide", {"state": "what's the weather like in Paris right now?",
                        "options": ["chat", "get_weather", "escalate"]})
print(json.dumps({k: d[k] for k in ("choice", "confidence")}))
