#!/usr/bin/env python3
# gen_routespec.py — turn a customer route table (JSON config) into a labeled
# decision-head spec. THIS is the product loop: routes are config, not data
# labeling. Output rows are eval_exact-format (expect_tool = route name) so
# train_head.py consumes them directly.
#
# Config: {"system": "...", "routes": {"<name>": ["stem", ...]}, ...}
# Usage: gen_routespec.py config.json N > spec.jsonl
import json, random, sys

cfg = json.load(open(sys.argv[1]))
n = int(sys.argv[2])
seed = int(sys.argv[3]) if len(sys.argv) > 3 else 7
random.seed(seed)

SYS = cfg.get("system", "You are a helpful assistant. You can call tools. When a tool is needed, reply with only the JSON tool call. Otherwise answer in plain English.")
routes = cfg["routes"]            # name -> [stems with {slots}]
slots = cfg.get("slots", {})      # slot -> [values]

PRE = ["", "", "", "hey ", "please ", "can you ", "could you ", "hi, ", "pls ", "ok so ", "i need to "]
SUF = ["", "", "", " please", " thanks", "?", " now", " for me", " asap"]

def fill(stem):
    out = stem
    for k, vals in slots.items():
        while "{" + k + "}" in out:
            out = out.replace("{" + k + "}", random.choice(vals), 1)
    lo, hi = cfg.get("_num_range", [100, 9999])
    while "{num}" in out:
        out = out.replace("{num}", str(random.randint(lo, hi)), 1)
    return out

names = list(routes)
rows = []
for i in range(n):
    name = random.choice(names)
    stem = fill(random.choice(routes[name]))
    if random.random() < 0.6:
        stem = random.choice(PRE) + stem + random.choice(SUF)
    if random.random() < 0.4:
        stem = stem[0].lower() + stem[1:]
    if random.random() < 0.12:
        stem = stem.rstrip("?.!")
    rows.append({"system": SYS, "user": stem, "call": "", "tool_result": "",
                 "expect_tool": name, "expect_args": None, "expect_values": []})

for r in rows:
    print(json.dumps(r))
