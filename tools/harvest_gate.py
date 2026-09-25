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

Idempotent: --seen tracks hashes of RESOLVED states (auto-accepted or
judged). Review rows are deliberately NOT marked seen — the review file
is rewritten each run as a persistent queue: a row stays in review until
it is judged (its key added to --seen) or a future accept qualifies it.

Rows logged without domain fields (older builds) are replayed against
--router (e.g. http://rbm4:8401) to recover gate/expert predictions —
real states are too valuable to drop just because the log predates the
logging patch.
"""
import argparse, hashlib, json, subprocess, sys

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
    ap.add_argument("--router", default="",
                    help="router URL to replay domain-less rows against")
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

    def replay(state):
        try:
            p = subprocess.run(
                ["curl", "-s", "-m", "15", "-X", "POST",
                 a.router + "/v1/route",
                 "-H", "content-type: application/json",
                 "-d", json.dumps({"state": state})],
                capture_output=True, text=True, timeout=20)
            return json.loads(p.stdout) if p.stdout.strip() else None
        except Exception:
            return None

    for line in lines:
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("ep") != "route" or not r.get("state"):
            continue
        k = key(r["state"])
        if k in seen:
            continue
        if r.get("domain"):
            dom, gc = r["domain"], float(r.get("gate_conf") or 0)
            action, route, reason = (r.get("action"), r.get("route"),
                                     r.get("reason"))
        elif a.router:
            rep = replay(r["state"])
            if not rep:
                continue
            dom, gc = rep.get("domain"), float(rep.get("gate_confidence") or 0)
            action, route, reason = (rep.get("action"), rep.get("route"),
                                     rep.get("reason"))
        else:
            continue
        if not dom:
            continue
        if action != "delegate" and gc >= a.min_conf:
            seen.add(k)
            accepted.append({"system": GATE_SYS, "user": r["state"],
                             "expect_tool": dom, "src": "harvest",
                             "conf": round(gc, 4)})
        else:
            review.append({"state": r["state"], "domain": dom,
                           "gate_conf": gc, "action": action,
                           "route": route, "reason": reason})

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
