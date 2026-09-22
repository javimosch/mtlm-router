#!/usr/bin/env python3
# router_demo.py — dispatcher-loop demo for mtlm tool models.
# Sits in front of anvil (OpenAI-compatible, tools baked into the model):
#   user msg -> POST /v1/chat/completions -> tool_call -> ROUTES dispatch
#   -> "Tool result: ..." follow-up -> final natural-language answer.
#
# The route table is the fake-routing layer: each tool_call name maps to a
# handler of kind tool (really executed), stub (canned), assistant (fake
# specialist handoff) or escalate (would hand to a big model — here: echo).
#
# Usage: router_demo.py [--port 8097] "user message" ["msg2" ...]
#        router_demo.py --selftest            # canned multi-route scenario
import sys, json, urllib.request, ast, operator, time

BASE = "http://localhost:8097"

# ---- fake backends ----
OPS = {"+": operator.add, "-": operator.sub, "*": operator.mul, "/": operator.truediv}
def safe_calc(expr):
    """eval arithmetic only: numbers, + - * / ( ) . unary minus."""
    def ev(node):
        if isinstance(node, ast.Expression): return ev(node.body)
        if isinstance(node, ast.Num): return node.n
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)): return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in (ast.Add, ast.Sub, ast.Mult, ast.Div):
            op = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/"}[type(node.op)]
            return OPS[op](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub): return -ev(node.operand)
        raise ValueError("unsupported expr")
    return ev(ast.parse(expr, mode="eval"))

def h_calculator(a):  return json.dumps({"result": safe_calc(a["expression"])})
def h_weather(a):     return json.dumps({"temp_c": 18.5, "wind_kph": 12, "conditions": "partly cloudy", "city": a.get("city")})
def h_time(a):        return json.dumps({"time": time.strftime("%H:%M"), "tz": a.get("timezone", "UTC")})
def h_stub(name):
    return lambda a: json.dumps({"ok": True, "tool": name})
def h_assistant(name):
    # compact result (prompt+history must stay < seq_len=256), but with a
    # sentence-shaped status the small model can relay verbatim.
    def h(a):
        first = next(iter(a.values()), "")
        return json.dumps({"routed_to": name, "ok": True,
                           "status": "queued for %s as T-4471" % first})
    return h
def h_escalate(a):    return json.dumps({"escalated": True, "queue": "big-model"})

ROUTES = {
    # real tools — executed for real
    "calculator":  ("tool",      h_calculator),
    "get_time":    ("tool",      h_time),
    # canned stubs — plausible tool responses
    "get_weather": ("stub",      h_weather),
    # fake specialist assistants — the "routing" part of the demo
    "translate":   ("assistant", h_assistant("translation-assistant")),
    "send_email":  ("assistant", h_assistant("comms-assistant")),
    "web_search":  ("assistant", h_assistant("research-assistant")),
    "wikipedia":   ("assistant", h_assistant("research-assistant")),
    # everything else falls back to a generic stub; escalate exists as a target
    "escalate":    ("escalate",  h_escalate),
}

# tools are declared so anvil lifts tool_call text into structured tool_calls;
# with ANVIL_TOOLS_INJECT=0 the schemas never enter the prompt.
TOOLS = [{"type": "function", "function": {"name": n, "description": n,
         "parameters": {"type": "object", "properties": {}}}} for n in ROUTES] + [
    {"type": "function", "function": {"name": n, "description": n,
     "parameters": {"type": "object", "properties": {}}}}
    for n in ("set_reminder", "take_note", "read_file", "write_file",
              "http_get", "shell", "convert_units")]

def chat(messages):
    if not hasattr(chat, "n"): chat.n = 0
    payload = {"model": "mtlm", "messages": messages, "tools": TOOLS,
               "temperature": 0.0, "max_tokens": 96}
    chat.n += 1
    open("/tmp/router-req-%d.json" % chat.n, "w").write(json.dumps(payload))
    body = json.dumps(payload).encode()
    req = urllib.request.Request(BASE + "/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=60).read())
    except urllib.error.HTTPError as e:
        # anvil now 400s prompts >= seq_len instead of crashing — surface it
        raise RuntimeError("HTTP %d: %s" % (e.code, e.read()[:200]))

SYS = "You are a helpful assistant. You can call tools."

# ---- Jev-style decide gate ----
# One typed forward pass picks the route + confidence BEFORE any generation:
#   conf < THRESH         -> escalate (abstain-and-delegate; a router that is
#                            unsure is worse than one that hands off)
#   chat / escalate       -> short-circuit, no tool arg extraction needed
#   other route           -> generative pass produces just the args
CONF_THRESHOLD = 0.6

def decide(state, ctx=None):
    b = {"state": state}
    if ctx: b["context"] = ctx
    body = json.dumps(b).encode()
    req = urllib.request.Request(BASE + "/v1/decide", data=body,
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())

def noul(state, ctx=None):
    """Fixed-question binary head ("should this escalate?") -> p(yes), or
    None when the server has no ANVIL_NOUL loaded."""
    b = {"state": state}
    if ctx: b["context"] = ctx
    body = json.dumps(b).encode()
    req = urllib.request.Request(BASE + "/v1/noul", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=30).read())["probability"]
    except Exception:
        return None

def assess(state, ctx=None):
    """One-prefill multi-head call: /v1/assess returns decision+noul+score
    from a single forward pass. Falls back to decide+noul (two passes) when
    the server predates the endpoint."""
    b = {"state": state}
    if ctx: b["context"] = ctx
    body = json.dumps(b).encode()
    req = urllib.request.Request(BASE + "/v1/assess", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=30).read())
    except Exception:
        d = decide(state, ctx)
        py = noul(state, ctx)
        r = {"decision": {"choice": d["choice"], "confidence": d["confidence"]}}
        if py is not None:
            r["noul"] = {"answer": "yes" if py >= 0.5 else "no", "probability": py}
        return r

def ctx_of(messages, k=6):
    # prior user/assistant turns (oldest first) for the decide `context` field —
    # lets anaphoric follow-ups ("and in London?") route on the conversation,
    # not just the bare last line. Kept short: anvil 400s prompts >= seq_len.
    return [m["content"] for m in messages
            if m["role"] in ("user", "assistant") and m.get("content")][-k:]

def trim(messages, k=4):
    # keep system + last k non-system messages — tool_call JSON is verbose and
    # chained turns quickly exceed the 256-token prompt cap otherwise.
    head = [m for m in messages if m["role"] == "system"][:1]
    return head + [m for m in messages if m["role"] != "system"][-k:]

def handle_decide(user_msg, messages=None, depth=0):
    """Decide-gated dispatch turn: /v1/decide gates the route, the generative
    path is only used to fill in args or produce the chat reply."""
    if messages is None:
        messages = [{"role": "system", "content": SYS}]
    ctx = ctx_of(messages)
    messages = messages + [{"role": "user", "content": user_msg}]
    a = assess(user_msg, ctx)
    choice, conf = a["decision"]["choice"], a["decision"]["confidence"]
    py = a.get("noul", {}).get("probability")
    grade = a.get("score", {}).get("grade")
    trace = {"in": user_msg, "decide": {"choice": choice, "conf": round(conf, 3)}}
    if py is not None: trace["noul_p"] = round(py, 3)
    if grade is not None: trace["score"] = grade
    # three abstention signals, OR'd: low head confidence, escalate route,
    # or the dedicated noul boundary says escalate (it catches some prompts
    # the 16-way softmax is confident-but-wrong on)
    if conf < CONF_THRESHOLD or choice == "escalate" or (py is not None and py >= 0.5):
        trace["gated"] = conf < CONF_THRESHOLD
        trace["noul_yes"] = py is not None and py >= 0.5
        result = h_escalate({"request": user_msg,
                             "reason": "low confidence" if conf < CONF_THRESHOLD else "hard task"})
        trace.update({"route": "escalate", "target": "escalate",
                      "args": {"request": user_msg}, "tool_result": result,
                      "answer": "I've passed that to the big model; ticket T-404."})
        return trace, messages
    if choice == "chat":
        r = chat(trim(messages))   # generative path, no tool needed
        msg = r["choices"][0]["message"]
        trace.update({"route": "chat", "raw": msg.get("content") or "",
                      "answer": msg.get("content", "")})
        return trace, messages + [{"role": "assistant", "content": trace["answer"]}]
    # decided route -> generative pass to extract args (tools visible so anvil
    # lifts the tool_call; the head already chose, generation only fills args)
    t, messages = handle(user_msg, messages=[{"role": "system", "content": SYS}], depth=depth)
    t["decide"] = trace["decide"]
    t["decided_route"] = choice
    # ensemble disagreement = abstention signal: the head and the trunk disagree
    # on the route, so neither is trustworthy — hand off instead of dispatching
    # a guess. (chat in generation vs a decided tool route counts as disagree.)
    gen_route = t.get("target") or "chat"
    if gen_route != choice:
        result = h_escalate({"request": user_msg, "reason": "route disagreement"})
        t.update({"route": "escalate", "target": "escalate",
                  "args": {"request": user_msg}, "tool_result": result,
                  "answer": "I've passed that to the big model; ticket T-404.",
                  "disagreement": "%s vs %s" % (choice, gen_route)})
    return t, messages

def handle(user_msg, messages=None, depth=0):
    """One dispatch turn. Returns dict describing what happened."""
    if messages is None:
        messages = [{"role": "system", "content": SYS}]
    messages = messages + [{"role": "user", "content": user_msg}]
    r = chat(trim(messages))
    msg = r["choices"][0]["message"]
    calls = msg.get("tool_calls") or []
    trace = {"in": user_msg, "raw": msg.get("content") or ""}
    if not calls:
        trace["route"] = "chat"
        trace["answer"] = msg.get("content", "")
        return trace, messages + [{"role": "assistant", "content": msg.get("content", "")}]
    tc = calls[0]["function"]
    name, args_raw = tc["name"], tc["arguments"]
    try: args = json.loads(args_raw)
    except Exception: args = {"_raw": args_raw}
    kind, handler = ROUTES.get(name, ("stub", h_stub(name)))
    # guard: don't execute or echo truncated/malformed args back to the model
    if "_raw" in args:
        trace.update({"route": kind, "target": name, "args": args,
                      "error": "malformed args_json — not replayed"})
        return trace, messages
    result = handler(args)
    trace.update({"route": kind, "target": name, "args": args, "tool_result": result})
    # follow-up turn: proper OpenAI tool_calls format
    # (anvil 400s prompts >= seq_len=256 — keep history short)
    a_msg = {"role": "assistant", "content": None,
             "tool_calls": [{"id": "c1", "type": "function",
                             "function": {"name": name, "arguments": args_raw}}]}
    messages += [a_msg, {"role": "tool", "tool_call_id": "c1", "content": result}]
    try:
        r2 = chat(trim(messages))
        trace["answer"] = r2["choices"][0]["message"].get("content", "")
    except Exception as e:
        trace["answer"] = "<follow-up request failed: %s>" % e
    return trace, messages + [{"role": "assistant", "content": trace["answer"]}]

def main():
    global BASE, CONF_THRESHOLD
    args = sys.argv[1:]
    if "--port" in args:
        i = args.index("--port"); BASE = "http://localhost:%s" % args[i+1]; del args[i:i+2]
    use_decide = "--decide" in args
    if use_decide: args.remove("--decide")
    if "--threshold" in args:
        i = args.index("--threshold"); CONF_THRESHOLD = float(args[i+1]); del args[i:i+2]
    if args and args[0] == "--selftest":
        prompts = [
            "what is 123 times 456?",
            "what is the weather in Tokyo?",
            "translate 'good morning' to French",
            "send an email to bob@corp.io with subject deploy saying the deploy is done",
            "write a 500-word essay about the French Revolution",
            "tell me a joke",
        ]
    else:
        prompts = [a for a in args if not a.startswith("--")]
    if not prompts: sys.exit('usage: router_demo.py [--selftest] "msg" ...')
    n_disp = n_chat = 0
    msgs = None  # chained across prompts — follow-ups route on prior turns
    for p in prompts:
        t, msgs = (handle_decide if use_decide else handle)(p, msgs)
        if "decide" in t:
            print("DECIDE %s conf=%s%s%s%s" % (t["decide"]["choice"], t["decide"]["conf"],
                  " (gated->escalate)" if t.get("gated") else "",
                  " (noul:yes %.2f)" % t["noul_p"] if t.get("noul_yes") else "",
                  " (disagree: %s)" % t["disagreement"] if "disagreement" in t else ""))
        if t["route"] == "chat":
            n_chat += 1
            print("CHAT   %r -> %s" % (p, t["answer"]))
        else:
            n_disp += 1
            print("%s %-12s args=%s" % (t["route"].upper(), t["target"], json.dumps(t["args"])))
            if "error" in t: print("       ERROR=%s" % t["error"])
            if "tool_result" in t: print("       result=%s" % t["tool_result"][:120])
            if "answer" in t: print("       answer=%s" % t["answer"])
    print(json.dumps({"dispatched": n_disp, "chat": n_chat}))

if __name__ == "__main__":
    main()
