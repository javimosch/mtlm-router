#!/usr/bin/env python3
"""Leak-free live eval: score a head through the SERVED runtime, never offline
features. The head under test must have been emitted from train rows only —
evaluating an all-rows fit on its own holdout inflates the number (proven
2026-10: 99.5%/100% published figures were all-rows artifacts; honest values
were 98.4/99.4/98.8/98.7).

Two more traps this tool exists to catch (both burned us):
- offline feature files extracted under a system prompt different from the
  served decide_sys produce heads whose offline acc does not transfer
  (geo_feats.npz vs geo_ssfull_feats.npz: merged municipal 92.1% offline vs
  79.8% live; re-emit on aligned features -> 91.15/90.68 parity)
- emitted feature taps the runtime cannot express silently score wrong
  (kind-0 "last" is the final-layer snapshot only)

Usage:
  python3 tools/live_eval.py --holdout holdout.jsonl --url http://host:port \
      [--endpoint route|decide] [--expert mairie] [--key mk_...] [--map a=b,c=d]

Row format: {"user": str, "expect_tool": str, "context": [...]?, "state"?}
--map rewrites expected labels (e.g. merged-taxonomy eval:
  collecte_om=collecte,collecte_selective=collecte).
"""
import argparse, json, sys, urllib.request


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--holdout", required=True)
    p.add_argument("--url", required=True)
    p.add_argument("--endpoint", default="route", choices=["route", "decide"])
    p.add_argument("--expert", default=None)
    p.add_argument("--key", default=None)
    p.add_argument("--map", default=None)
    p.add_argument("--conf-wrong", type=float, default=0.7)
    a = p.parse_args()
    label_map = dict(kv.split("=") for kv in a.map.split(",")) if a.map else {}
    rows = [json.loads(l) for l in open(a.holdout)]
    ok = rej = cw = 0
    fails = []
    for i, r in enumerate(rows):
        want = label_map.get(r.get("expect_tool"), r.get("expect_tool"))
        body = {"state": r.get("user") or r.get("state") or "",
                "context": r.get("context") or []}
        if a.expert:
            body["expert"] = a.expert
        req = urllib.request.Request(
            f"{a.url}/v1/{a.endpoint}", data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {a.key}"} if a.key else {})
        try:
            resp = json.loads(urllib.request.urlopen(req, timeout=60).read())
        except Exception:
            rej += 1
            continue
        got = resp.get("route") or resp.get("choice")
        if got == want:
            ok += 1
        else:
            conf = resp.get("confidence", 0)
            if conf >= a.conf_wrong:
                cw += 1
            fails.append({"i": i, "want": want, "got": got, "conf": conf,
                          "text": body["state"][:80]})
    n = len(rows)
    print(json.dumps({"acc": round(ok / n, 4), "n": n, "ok": ok,
                      "rejects": rej, "conf_wrong": cw,
                      "endpoint": a.endpoint, "expert": a.expert}))
    for f in fails[:20]:
        print(json.dumps(f, ensure_ascii=False))


if __name__ == "__main__":
    main()
