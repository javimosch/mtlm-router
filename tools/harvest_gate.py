#!/usr/bin/env python3
"""Harvest labeled gate rows from live router decisions.

The serving log (ANVIL_LOG) writes one JSONL row per /v1/route call:
{"ts","ep","state","action","route","conf","reason","domain","gate_conf"}.
Rows where the gate was confident AND the expert agreed (action != delegate)
are self-consistent — auto-label them with the chosen domain and append to
the gate corpus. Confident-but-delegated or low-confidence rows go to a
review file: those are exactly the requests the gate is weak on, the most
valuable labels once judged.

  python3 tools/harvest_gate.py \
    --decisions /root/mtlm/logs/gate-decisions.jsonl \
    --out /root/mtlm/data/gate_harvest.jsonl \
    --review /root/mtlm/data/gate_review.jsonl \
    --seen /root/mtlm/data/gate_seen.txt --min-conf 0.90

Idempotent: --seen tracks normalized state hashes across runs, so the log
can be re-read from byte 0 every time. Review rows are written fresh each
run (they shrink as auto-accepted domains thicken).
"""
import argparse, hashlib, json, sys

GATE_SYS = ("You are a request dispatcher. Classify each request into the "
            "specialist domain that should handle it: tools (general assistant "
            "tasks — email, reminders, files, web, code, scheduling), "
            "it_helpdesk (IT support — passwords, tickets, VMs, access), "
            "fleet_gate (GitHub issue triage — fit/skip prospects), "
            "rpg (game commands — move, attack, loot, inspect), "
            "chat (conversation, questions, no action needed).")

def key(text):
    return hashlib.sha1(" ".join(text.lower().split()).encode()).hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--decisions", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--review", required=True)
    ap.add_argument("--seen", required=True)
    ap.add_argument("--min-conf", type=float, default=0.90)
    a = ap.parse_args()

    try:
        seen = set(open(a.seen).read().split())
    except FileNotFoundError:
        seen = set()

    accepted, review = [], []
    try:
        lines = open(a.decisions)
    except FileNotFoundError:
        print(f"no decisions log at {a.decisions}", file=sys.stderr)
        return 0

    for line in lines:
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("ep") != "route" or not r.get("domain") or not r.get("state"):
            continue
        k = key(r["state"])
        if k in seen:
            continue
        seen.add(k)
        dom, gc = r["domain"], float(r.get("gate_conf") or 0)
        if r.get("action") != "delegate" and gc >= a.min_conf:
            accepted.append({"system": GATE_SYS, "user": r["state"],
                             "expect_tool": dom, "src": "harvest",
                             "conf": round(gc, 4)})
        else:
            review.append({"state": r["state"], "domain": dom,
                           "gate_conf": gc, "action": r.get("action"),
                           "route": r.get("route"), "reason": r.get("reason")})

    if accepted:
        with open(a.out, "a") as f:
            for row in accepted:
                f.write(json.dumps(row) + "\n")
    with open(a.review, "w") as f:
        for row in review:
            f.write(json.dumps(row) + "\n")
    with open(a.seen, "w") as f:
        f.write("\n".join(sorted(seen)))

    by = {}
    for row in accepted:
        by[row["expect_tool"]] = by.get(row["expect_tool"], 0) + 1
    print(json.dumps({"accepted": len(accepted), "by_domain": by,
                      "review": len(review), "seen_total": len(seen)}))
    return 0

if __name__ == "__main__":
    sys.exit(main())
