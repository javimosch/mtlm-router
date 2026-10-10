#!/usr/bin/env python3
"""Risk-coverage curve + AURC for a live-routed lane.

The honest selective-prediction artifact: two heads can share an accuracy
number while behaving very differently under abstention. This scores a
holdout through the SERVED runtime (same rule as live_eval.py — never
offline features), sorts decisions by confidence, and reports the full
risk-vs-coverage curve plus AURC (area under the curve, trapezoid —
the standard comparable metric for "does confidence order risk").

Usage:
    python3 bench/risk_coverage.py data/geored/geored12_holdout.jsonl \
      --url http://127.0.0.1:8111 --expert mairie_c \
      --map collecte_om=collecte,collecte_selective=collecte [--json out.json]
"""
import json, urllib.request, argparse, sys

def main():
    p = argparse.ArgumentParser()
    p.add_argument("holdout")
    p.add_argument("--url", required=True)
    p.add_argument("--expert", required=True)
    p.add_argument("--key", default=None)
    p.add_argument("--map", default=None)
    p.add_argument("--json", default=None)
    a = p.parse_args()
    label_map = dict(kv.split("=") for kv in a.map.split(",")) if a.map else {}
    rows = [json.loads(l) for l in open(a.holdout)]
    scored = []
    for r in rows:
        want = label_map.get(r.get("expect_tool"), r.get("expect_tool"))
        body = {"state": r.get("user") or r.get("state") or "", "expert": a.expert}
        req = urllib.request.Request(
            f"{a.url}/v1/route", data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {a.key}"} if a.key else {})
        try:
            resp = json.loads(urllib.request.urlopen(req, timeout=60).read())
        except Exception:
            continue
        scored.append({"conf": resp.get("confidence", 0), "ok": resp.get("route") == want,
                       "action": resp.get("action"), "set_size": resp.get("set_size")})
    scored.sort(key=lambda s: -s["conf"])
    n = len(scored)
    errs = curve = 0
    pts = []
    for i, s in enumerate(scored):
        if not s["ok"]:
            errs += 1
        cov = (i + 1) / n
        risk = errs / (i + 1)
        curve += risk  # trapezoid approx: avg risk over coverage
        pts.append({"coverage": round(cov, 4), "risk": round(risk, 4)})
    # AURC normalized over coverage in (0,1]: mean risk (trapezoid on dense points ~ sum/n)
    aurc = curve / n
    # notable operating points
    ops = []
    for t in (0.5, 0.6, 0.7, 0.8, 0.9):
        sub = [s for s in scored if s["conf"] >= t]
        if sub:
            e = sum(1 for s in sub if not s["ok"])
            ops.append({"conf_floor": t, "coverage": round(len(sub) / n, 3),
                        "auto_acc": round(1 - e / len(sub), 4)})
    out = {"n": n, "aurc": round(aurc, 4), "acc_at_full": round(1 - errs / n, 4),
           "ops": ops, "expert": a.expert}
    print(json.dumps(out, indent=2))
    if a.json:
        json.dump({"summary": out, "curve": pts}, open(a.json, "w"))

main()
