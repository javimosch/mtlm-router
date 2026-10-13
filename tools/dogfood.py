#!/usr/bin/env python3
"""dogfood.py — replay real logged traffic through the live conformal gates.

Reads production decision logs (anvil ANVIL_LOG jsonl), dedupes states,
re-issues each through /v1/route on a live instance, and reports what the
conformal gates would do with that traffic TODAY: automation rate, abstention
mix (set_size 0 / multi / oversized), delegate reasons, candidate availability,
margin distribution, latency percentiles — plus a decision-diff vs whatever
the log recorded at the time (a cheap drift signal).

Run on the router host (localhost) or anywhere that can reach the API.

Usage:
    python3 tools/dogfood.py --log /root/mtlm/logs/hosted-decisions.jsonl \
        --url http://127.0.0.1:8402 --key mk_... [--max 2000] \
        --out bench/dogfood_report.json --evidence /tmp/dogfood_evidence.jsonl
"""
import argparse, collections, json, sys, time, urllib.request


def route(url, state, expert, key, timeout=30):
    body = {"state": state}
    if expert and expert != "default":
        body["expert"] = expert
    req = urllib.request.Request(url + "/v1/route", data=json.dumps(body).encode(),
                                 headers={"content-type": "application/json"})
    if key:
        req.add_header("authorization", "Bearer " + key)
    t0 = time.time()
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    except Exception as e:
        return {"error": str(e)}, (time.time() - t0) * 1000
    return d, (time.time() - t0) * 1000


def pct(v, p):
    if not v:
        return None
    v = sorted(v)
    return round(v[min(len(v) - 1, int(len(v) * p))], 1)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--log", required=True, action="append")
    p.add_argument("--url", default="http://127.0.0.1:8402")
    p.add_argument("--key", default="")
    p.add_argument("--max", type=int, default=2000)
    p.add_argument("--out", default=None)
    p.add_argument("--evidence", default=None)
    a = p.parse_args()

    seen, rows = set(), []
    for path in a.log:
        for l in open(path):
            try:
                r = json.loads(l)
            except json.JSONDecodeError:
                continue
            st = r.get("state")
            if not st or len(st) < 3 or st in seen:
                continue
            seen.add(st)
            rows.append({"state": st[:500], "expert": r.get("expert") or r.get("domain"),
                         "old_action": r.get("action"), "old_route": r.get("route")})
    rows = rows[:a.max]
    print(f"{len(rows)} unique states to replay", file=sys.stderr)

    ev = open(a.evidence, "w") if a.evidence else None
    per = collections.defaultdict(lambda: {
        "n": 0, "tool_call": 0, "delegate": 0, "error": 0,
        "set0": 0, "set1": 0, "set2_8": 0, "set9": 0,
        "candidates": 0, "route_oos": 0, "confident_oos_toolcall": 0,
        "route_changed": 0, "action_changed": 0,
        "lat": [], "margin": [], "conf": []})
    for i, r in enumerate(rows):
        d, lat = route(a.url, r["state"], r["expert"], a.key)
        lane = r["expert"] or "default"
        s = per[lane]
        s["n"] += 1
        s["lat"].append(lat)
        rec = {"ts": int(time.time() * 1000), "state": r["state"][:300],
               "expert": lane, "latency_ms": round(lat, 1),
               "old_action": r["old_action"], "old_route": r["old_route"]}
        if "error" in d:
            s["error"] += 1
            rec["error"] = d["error"]
        else:
            act, rt = d.get("action"), d.get("route")
            s[act] = s.get(act, 0) + 1
            ss = d.get("set_size")
            if ss == 0:
                s["set0"] += 1
            elif ss == 1:
                s["set1"] += 1
            elif ss and ss <= 8:
                s["set2_8"] += 1
            elif ss:
                s["set9"] += 1
            if d.get("candidates"):
                s["candidates"] += 1
            if d.get("reason") == "route_oos":
                s["route_oos"] += 1
            if act == "tool_call" and rt == "oos" and d.get("confidence", 0) > 0.9:
                s["confident_oos_toolcall"] += 1
            if r["old_route"] and rt and rt != r["old_route"]:
                s["route_changed"] += 1
            if r["old_action"] and act and act != r["old_action"]:
                s["action_changed"] += 1
            if d.get("margin") is not None:
                s["margin"].append(d["margin"])
            if d.get("confidence") is not None:
                s["conf"].append(d["confidence"])
            rec.update(action=act, route=rt, confidence=d.get("confidence"),
                       set_size=ss, reason=d.get("reason"), margin=d.get("margin"),
                       n_candidates=len(d.get("candidates") or []))
        if ev:
            ev.write(json.dumps(rec) + "\n")
        if (i + 1) % 200 == 0:
            print(f"  {i+1}/{len(rows)}", file=sys.stderr)
    if ev:
        ev.close()

    report = {"generated": int(time.time()), "url": a.url, "states": len(rows), "lanes": {}}
    for lane, s in sorted(per.items()):
        n = s["n"]
        report["lanes"][lane] = {
            "n": n,
            "tool_call_pct": round(100 * s["tool_call"] / n, 1),
            "delegate_pct": round(100 * s["delegate"] / n, 1),
            "errors": s["error"],
            "set_size_0_pct": round(100 * s["set0"] / n, 1),
            "singleton_pct": round(100 * s["set1"] / n, 1),
            "set_2_8_pct": round(100 * s["set2_8"] / n, 1),
            "set_9plus_pct": round(100 * s["set9"] / n, 1),
            "with_candidates_pct": round(100 * s["candidates"] / n, 1),
            "route_oos": s["route_oos"],
            "confident_oos_toolcall": s["confident_oos_toolcall"],
            "route_changed_vs_log": s["route_changed"],
            "action_changed_vs_log": s["action_changed"],
            "lat_p50_ms": pct(s["lat"], 0.5), "lat_p95_ms": pct(s["lat"], 0.95),
            "conf_p50": pct(s["conf"], 0.5), "margin_p50": pct(s["margin"], 0.5),
            "margin_p10": pct(s["margin"], 0.1)}
    js = json.dumps(report, indent=1)
    print(js)
    if a.out:
        open(a.out, "w").write(js)


if __name__ == "__main__":
    main()
