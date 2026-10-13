#!/usr/bin/env python3
"""Reference client: the full clarify→act→handoff loop over /v1/route.

    python3 examples/clarify_loop.py http://127.0.0.1:8097 mairie_c "bruit la nuit" [--key mk_...]

Policy (all fields are in the response contract, see openapi.yaml):
  tool_call + margin >= MARGIN        -> execute route
  tool_call + margin < MARGIN         -> confirm with the user, then execute
  delegate + candidates[]             -> ask "did you mean…" (most-probable first),
                                          execute the pick; user may pick none
  delegate + route_oos                -> polite rejection: lane can't help, don't retry
  delegate, no candidates             -> human handoff

Loop discipline (HAX pattern 10A):
  - Ask at most MAX_CLARIFY clarifying questions, then hand off. An agent that
    keeps asking trains the user to ignore it; a wrong automated route is worse
    than a handoff.
  - Show candidates in the order returned — the router sorts them by
    probability, most-probable first.
  - set_size=0 candidates are best guesses with NO coverage claim: fine for a
    pick-list, never auto-execute them.
"""
import json, sys, urllib.request

MARGIN = 0.3
MAX_CLARIFY = 1


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
    if r.get("reason") == "route_oos":
        return ("reject", r["route"])
    if r.get("candidates"):
        return ("clarify", r["candidates"])
    return ("handoff", r.get("reason"))


def run(base, expert, text, key=""):
    asks = 0
    r = route(base, expert, text, key)
    while True:
        kind, val = decide(r)
        if kind == "execute":
            print("execute:", val)
            return val
        if kind == "confirm":
            a = input(f"I think you mean '{val}' — go ahead? [y/n] ")
            print("execute:", val) if a.lower().startswith("y") else print("handoff: user declined")
            return val if a.lower().startswith("y") else None
        if kind == "reject":
            print(f"sorry, that's outside this lane's scope (route={val}) — handing to a human")
            return None
        if kind == "clarify" and asks < MAX_CLARIFY:
            asks += 1
            print("Did you mean:")
            for i, c in enumerate(val, 1):
                print(f"  {i}. {c['route']}  ({c['confidence']:.0%})")
            print(f"  {len(val)+1}. none of these")
            pick = input("> ")
            if not pick.isdigit() or not (1 <= int(pick) <= len(val)):
                print("handoff: no candidate chosen")
                return None
            chosen = val[int(pick) - 1]["route"]
            print("execute:", chosen)
            return chosen
        print("handoff:", val if isinstance(val, str) else "repeated abstention")
        return None


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    key = sys.argv[sys.argv.index("--key") + 1] if "--key" in sys.argv else ""
    base, expert, text = a[0], a[1], a[2]
    run(base, expert, text, key)
