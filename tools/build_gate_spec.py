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

# --- rpg: logged game states + expert-spec phrasings ------------------------
# The rpg expert spec (/data/pooled/rpg_train.jsonl on rbm4, synced to
# /root/mtlm/data/rpg_expert_train.jsonl) contains the natural phrasings the
# gate must recognize as game intents — its user texts are the ideal rpg
# domain rows. Logged decisions add real-play variety.
rpg_logged = list(dict.fromkeys(
    json.loads(l)["state"] for l in open("/root/mtlm/logs/rpg-decisions.jsonl")
    if json.loads(l).get("state")))
rpg_expert = []
try:
    rpg_expert = list(dict.fromkeys(
        json.loads(l)["user"] for l in open("/root/mtlm/data/rpg_expert_train.jsonl")
        if json.loads(l).get("user")))
except FileNotFoundError:
    print("warn: no rpg_expert_train.jsonl — sync from rbm4 pooled spec", file=sys.stderr)
rpg = rpg_logged + [u for u in rpg_expert if u not in rpg_logged]
random.shuffle(rpg)

sources = {
    "tools":       tools_rows[:450],
    "chat":        chat_rows[:200],
    "it_helpdesk": hd[:350],
    "fleet_gate":  fg,           # all real rows (~90)
    "rpg":         rpg[:220],    # logged + expert phrasings
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

# harvested live-traffic rows (harvest_gate.py / judged_review.py):
# spec-format but auto-labeled or human-judged — train only, never holdout,
# or the eval would grade the gate against non-blind labels. Dedup against
# the corpus AND itself: retries log the same state twice.
import hashlib
def skey(t):
    return hashlib.sha1(" ".join(t.lower().split()).encode()).hexdigest()
corpus_keys = {skey(r["user"]) for r in allrows}
try:
    hv = [json.loads(l) for l in open("/root/mtlm/data/gate_harvest.jsonl")]
except FileNotFoundError:
    hv = []
merged = 0
for r in hv:
    if not (r.get("expect_tool") and r.get("user")):
        continue
    k = skey(r["user"])
    if k in corpus_keys:
        continue
    corpus_keys.add(k)
    train.append({"system": GATE_SYS, "user": r["user"],
                  "expect_tool": r["expect_tool"]})
    merged += 1
if hv:
    print(f"harvest: {merged}/{len(hv)} live-labeled rows merged into train",
          file=sys.stderr)
with open("/root/mtlm/data/moe_gate_train.jsonl", "w") as f:
    for r in train: f.write(json.dumps(r) + "\n")
with open("/root/mtlm/data/moe_gate_holdout.jsonl", "w") as f:
    for r in hold: f.write(json.dumps(r) + "\n")
print(f"train {len(train)} holdout {len(hold)}", file=sys.stderr)
