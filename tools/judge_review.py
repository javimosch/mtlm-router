#!/usr/bin/env python3
"""Judge review-queue rows into labeled gate corpus entries.

harvest_gate.py writes uncertain rows to gate_review.jsonl. Judging means a
human (or a stronger model) reads them and supplies the correct domain.
Verdicts are rules applied to the review file:

  verdicts.jsonl rows:
    {"match": "substring of state", "domain": "fleet_gate"}
    {"match": "*", "domain": "skip"}          # drop matching rows (won't train)
  Every unskipped review row MUST match a verdict or it stays in the queue —
  the tool refuses to silently drain it.

Judged rows append to the harvest corpus (train-only, same as auto-accepts)
and their state keys are written to --seen so harvest stops re-queueing them.

  python3 tools/judge_review.py \
    --review gate_review.jsonl --verdicts verdicts.jsonl \
    --out gate_harvest.jsonl --seen gate_seen.txt
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
    ap.add_argument("--review", required=True)
    ap.add_argument("--verdicts", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seen", required=True)
    a = ap.parse_args()

    verdicts = [json.loads(l) for l in open(a.verdicts) if l.strip()]
    seen = set(open(a.seen).read().split()) if _exists(a.seen) else set()

    judged, unresolved, skipped = [], [], 0
    for line in open(a.review):
        r = json.loads(line)
        verdict = next((v["domain"] for v in verdicts
                        if v["match"] == "*" or v["match"] in r["state"]), None)
        if verdict is None:
            unresolved.append(r)
            continue
        seen.add(key(r["state"]))
        if verdict == "skip":
            skipped += 1
            continue
        judged.append({"system": GATE_SYS, "user": r["state"],
                       "expect_tool": verdict, "src": "judged"})

    with open(a.out, "a") as f:
        for row in judged:
            f.write(json.dumps(row) + "\n")
    with open(a.seen, "w") as f:
        f.write("\n".join(sorted(seen)))

    by = {}
    for row in judged:
        by[row["expect_tool"]] = by.get(row["expect_tool"], 0) + 1
    print(json.dumps({"judged": len(judged), "by_domain": by,
                      "skipped": skipped,
                      "unresolved": len(unresolved)}))
    if unresolved:
        for r in unresolved:
            print("UNRESOLVED:", r["state"][:80], file=sys.stderr)
        return 1
    return 0

def _exists(p):
    try:
        open(p); return True
    except OSError:
        return False

if __name__ == "__main__":
    sys.exit(main())
