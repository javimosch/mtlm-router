#!/usr/bin/env python3
"""Reference client: act on /v1/route decisions, ask when torn, hand off when not.

    python3 examples/clarify_loop.py http://127.0.0.1:8097 mairie_c "bruit la nuit" [--key mk_...]

Policy (all fields are in the response contract, see openapi.yaml):
  tool_call + margin >= MARGIN   -> execute route
  delegate + candidates[]        -> ask the user to pick one, then execute it
  delegate, reason route_oos/escalate/conformal_abstain w/o candidates -> human handoff
"""
import json, sys, urllib.request

MARGIN = 0.3

def route(base, expert, text, key=""):
    h = {"content-type": "application/json", **({"authorization": "Bearer " + key} if key else {})}
    req = urllib.request.Request(base.rstrip("/") + "/v1/route",
        json.dumps({"state": text, "expert": expert}).encode(), h)
    return json.loads(urllib.request.urlopen(req, timeout=30).read())

def decide(r):
    if r["action"] == "tool_call" and r.get("margin", 1) >= MARGIN:
        return ("execute", r["route"])
    if r["action"] == "tool_call":
        return ("confirm", r["route"])
    if r.get("candidates"):
        return ("clarify", [c["route"] for c in r["candidates"]])
    return ("handoff", r.get("reason"))

if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    key = sys.argv[sys.argv.index("--key") + 1] if "--key" in sys.argv else ""
    base, expert, text = a[0], a[1], a[2]
    kind, val = decide(route(base, expert, text, key))
    if kind == "clarify":
        print("Did you mean:")
        for i, c in enumerate(val, 1): print(f"  {i}. {c}")
        pick = val[int(input("> ")) - 1]
        print("execute:", pick)
    else:
        print(kind, val)
