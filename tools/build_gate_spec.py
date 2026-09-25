#!/usr/bin/env python3
# build_gate_spec.py — assemble the MoE gate training spec on rbm21.
# Output rows: {system, user, expect_tool: <domain>} — the head spec format
# train_head.py already consumes. Domain balance is deliberate: generic
# "tools" is the busiest lane in real traffic, rpg/helpdesk are distinct
# vocab, fleet_gate is the dogfood lane, chat is the no-action sink.
import json, random, sys

random.seed(42)
GATE_SYS = ("You are a request dispatcher. Classify each request into the "
            "specialist domain that should handle it: tools (general assistant "
            "tasks — email, reminders, files, web, code, scheduling), "
            "it_helpdesk (IT support — passwords, tickets, VMs, access), "
            "fleet_gate (GitHub issue triage — fit/skip prospects), "
            "rpg (game commands — move, attack, loot, inspect), "
            "chat (conversation, questions, no action needed).")

def rows_for(domain, user_texts):
    return [{"system": GATE_SYS, "user": u, "expect_tool": domain}
            for u in user_texts if u and len(u.strip()) > 3]

# --- generic tools + chat: from tools6 message corpus ----------------------
tools_rows, chat_rows = [], []
for line in open("/root/mtlm/data/tools6.jsonl"):
    try:
        m = json.loads(line)["messages"]
    except Exception:
        continue
    user = next((x["content"] for x in m if x["role"] == "user"), "")
    asst = next((x["content"] for x in m if x["role"] == "assistant"), "")
    if asst.strip().startswith("{"):
        tools_rows.append(user)
    else:
        chat_rows.append(user)
random.shuffle(tools_rows); random.shuffle(chat_rows)
print(f"tools6: {len(tools_rows)} tool, {len(chat_rows)} chat", file=sys.stderr)

# --- it_helpdesk -----------------------------------------------------------
hd = [json.loads(l)["user"] for l in open("/root/mtlm/data/train_helpdesk.jsonl")]
random.shuffle(hd)

# --- fleet_gate ------------------------------------------------------------
fg = [json.loads(l)["user"] for l in open("/root/mtlm/data/machinfit_real.jsonl")]
random.shuffle(fg)

# --- rpg: real logged game states ------------------------------------------
rpg = list(dict.fromkeys(
    json.loads(l)["state"] for l in open("/root/mtlm/logs/rpg-decisions.jsonl")
    if json.loads(l).get("state")))
random.shuffle(rpg)

sources = {
    "tools":       tools_rows[:450],
    "chat":        chat_rows[:200],
    "it_helpdesk": hd[:350],
    "fleet_gate":  fg,           # all real rows (~90)
    "rpg":         rpg,          # all unique logged (~64)
}
allrows = []
for dom, texts in sources.items():
    r = rows_for(dom, texts)
    print(f"{dom}: {len(r)} rows", file=sys.stderr)
    allrows += r
random.shuffle(allrows)

# 85/15 stratified-ish split: mark holdout by keeping domain mix via index
n_hold = max(1, int(len(allrows) * 0.15))
hold, train = allrows[:n_hold], allrows[n_hold:]
with open("/root/mtlm/data/moe_gate_train.jsonl", "w") as f:
    for r in train: f.write(json.dumps(r) + "\n")
with open("/root/mtlm/data/moe_gate_holdout.jsonl", "w") as f:
    for r in hold: f.write(json.dumps(r) + "\n")
print(f"train {len(train)} holdout {len(hold)}", file=sys.stderr)
