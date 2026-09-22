#!/usr/bin/env python3
# eval_agree.py — head/trunk route agreement rate on an eval spec.
# For each probe: POST /v1/decide (typed head) AND /v1/chat/completions
# (generative trunk), then compare both to expect_tool and to each other.
# The agreement rate is the ensemble signal router_demo --decide gates on:
# disagreement -> abstain/escalate. A trunk that has absorbed the corpus
# (e.g. m7router2) should push agreement toward head_acc.
#
# Usage: eval_agree.py [spec.jsonl] [port]
import json, urllib.request, re, sys

SPEC = sys.argv[1] if len(sys.argv) > 1 else "data/holdout_head4.jsonl"
BASE = "http://localhost:%s" % (sys.argv[2] if len(sys.argv) > 2 else "8098")
SYS = "You are a helpful assistant. You can call tools."

def decide(state):
    req = urllib.request.Request(BASE + "/v1/decide",
        data=json.dumps({"state": state}).encode(),
        headers={"content-type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())

def gen_route(state):
    # generative path: does the trunk emit a tool_call, and which?
    payload = {"model": "mtlm", "messages": [
        {"role": "system", "content": SYS},
        {"role": "user", "content": state}], "temperature": 0.0, "max_tokens": 80}
    req = urllib.request.Request(BASE + "/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=60).read())
    msg = r["choices"][0]["message"]
    calls = msg.get("tool_calls") or []
    if calls: return calls[0]["function"]["name"]
    c = msg.get("content") or ""
    m = re.search(r'"tool_call"\s*:\s*\{\s*"name"\s*:\s*"([a-z_]+)"', c)
    return m.group(1) if m else "chat"

probes = [json.loads(l) for l in open(SPEC)]
agree = head_ok = gen_ok = both_ok = n = 0
disagree_pairs = {}
for d in probes:
    n += 1
    expect = d["expect_tool"] or "chat"
    hd = decide(d["user"])["choice"]
    gr = gen_route(d["user"])
    if hd == expect: head_ok += 1
    if gr == expect: gen_ok += 1
    if hd == expect and gr == expect: both_ok += 1
    if hd == gr: agree += 1
    else:
        k = "%s|%s" % (hd, gr); disagree_pairs[k] = disagree_pairs.get(k, 0) + 1
    if n % 100 == 0: print("...", n, "agree=%.3f" % (agree / n), flush=True)
print(json.dumps({"n": n, "agreement": round(agree / n, 4),
    "head_acc": round(head_ok / n, 4), "gen_acc": round(gen_ok / n, 4),
    "both_correct": round(both_ok / n, 4),
    "top_disagreements": sorted(disagree_pairs.items(), key=lambda x: -x[1])[:10]}))
