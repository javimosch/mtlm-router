#!/usr/bin/env python3
"""moe_route.py — mixture-of-experts routing shim.

Two /v1/assess calls on one anvil instance implement expert routing with
zero serving changes: a gate head (its "routes" are domain names) selects
the expert, then a second assess under that expert's tenant key scores the
domain routes. One trunk prefill powers both — heads are ~7KB softmax
reads of the same hidden state.

Serve it like this (anvil-serve-v6+):

    ANVIL_HEAD=models/m7router3s384.head \
    ANVIL_NOUL=models/m7router3s384.noul.head \
    ANVIL_SCORE=models/m7router3s384.score.head \
    ANVIL_KEYS="gate,helpdesk,fleet,rpg,default" \
    ANVIL_TENANTS="gate:moe_gate.head,helpdesk:helpdesk.head,fleet:fleet_gate.head,rpg:rpg.head" \
    ./anvil-serve models/m7router3s384.bin 8400

Domain -> tenant-key map below must mirror ANVIL_TENANTS. Gate labels
"tools"/"chat" fall through to the unmapped key -> ANVIL_HEAD (the generic
router is itself the tools expert; chat is one of its routes).

Failure mode worth knowing: when the gate picks the wrong domain, the
generic head tends to 'escalate' rather than misroute — a wrong gate
degrades to delegate, not to a wrong action.

Usage:
    python3 tools/moe_route.py --state "reset my password" \
        [--base http://localhost:8400] [--json]
"""
import argparse, json, sys, urllib.request

DOMAIN_KEY = {
    "it_helpdesk": "helpdesk",
    "fleet_gate": "fleet",
    "rpg": "rpg",
    "tools": "default",
    "chat": "default",
}


def assess(base, key, state, context=None):
    body = {"state": state}
    if context:
        body["context"] = context
    req = urllib.request.Request(
        base.rstrip("/") + "/v1/assess",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def route(base, state, context=None):
    gate = assess(base, "gate", state, context)
    dom = gate["decision"]["choice"]
    key = DOMAIN_KEY.get(dom, "default")
    expert = assess(base, key, state, context)
    return {
        "state": state,
        "expert": dom,
        "gate_confidence": gate["decision"]["confidence"],
        "route": expert["decision"]["choice"],
        "route_confidence": expert["decision"]["confidence"],
        "expert_assess": expert,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True)
    ap.add_argument("--base", default="http://localhost:8400")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    out = route(a.base, a.state)
    if a.json:
        print(json.dumps(out))
    else:
        print(f"gate:    {out['expert']} (conf {out['gate_confidence']:.3f})")
        print(f"route:   {out['route']} (conf {out['route_confidence']:.3f})")


if __name__ == "__main__":
    main()
