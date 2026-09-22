#!/usr/bin/env python3
"""Held-out exactness eval for the MTLM tool model (verification oracle — lives in
tools/ per AGENTS.md; the model binary does all inference, this only drives + scores).

Per probe in the spec (data/eval_exact.jsonl from `synth_tools.py --eval`), two phases:
  dispatch : [system, user]                     -> mtlm sample -> emitted tool_call must
                                                 match expect_tool + expect_args exactly
  followup : [system, user, call, tool_result]  -> mtlm sample -> every expect_values
                                                 string must appear verbatim in the text

Spec line shape:
  {"system": str, "user": str, "call": str, "tool_result": str,
   "expect_tool": str, "expect_args": obj, "expect_values": [str, ...]}

Usage:
  python3 tools/eval_exact.py --spec data/eval_exact.jsonl --model models/m7tool2.mtlm \
      --tok models/tok4096.bin --mtlm ./mtlm --out logs/eval_exact.jsonl [--n 80 --temp 0.3 --seed 7]
Summary JSON on stdout; one JSON record per probe appended to --out (progress log).
"""
import argparse, json, os, re, subprocess, sys, tempfile, time

def probe_msgs(p):
    # spec `context` is alternating user/assistant turns (oldest first), rendered
    # before the current user turn — same layout anvil's head_prefill builds.
    m = [{"role": "system", "content": p["system"]}]
    m += [{"role": "user" if i % 2 == 0 else "assistant", "content": c}
          for i, c in enumerate(p.get("context") or [])]
    m.append({"role": "user", "content": p["user"]})
    return m

def chat_file(msgs):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps({"messages": msgs}) + "\n")
    return path

def sample(mtlm, model, tok, path, n, temp, seed):
    p = subprocess.run([mtlm, "sample", "--model", model, "--tok", tok,
                        "--chat-file", path, "--n", str(n), "--temp", str(temp),
                        "--seed", str(seed)],
                       capture_output=True, text=True, timeout=600)
    lines = [l for l in p.stdout.strip().split("\n") if l.strip()]
    if not lines:
        return "__NO_OUTPUT__:" + p.stderr[-200:]
    try:
        return json.loads(lines[-1])["gen"]
    except Exception:
        return "__PARSE_FAIL__:" + lines[-1][:200]

def parse_call(gen):
    """Extract (name, args-dict) from generated text; (None, None) if it isn't a tool_call."""
    g = gen.strip()
    i = g.find("{")
    if i < 0:
        return None, None
    o = None
    for cand in (g[i:], g[i:g.rfind("}") + 1]):
        try:
            o = json.loads(cand)
            break
        except Exception:
            continue
    if not isinstance(o, dict):
        # truncated gen (--n too small for long args): salvage the route name so
        # name_acc isn't corrupted by token-budget artifacts
        m = re.search(r'"name"\s*:\s*"([a-z_]+)"', g)
        return (m.group(1), None) if m else (None, None)
    tc = o.get("tool_call")
    if not isinstance(tc, dict):
        return None, None
    args = tc.get("arguments")
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            pass
    return tc.get("name"), args

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default="data/eval_exact.jsonl")
    ap.add_argument("--model", required=True)
    ap.add_argument("--tok", default="models/tok4096.bin")
    ap.add_argument("--mtlm", default="./mtlm")
    ap.add_argument("--out", default="logs/eval_exact.jsonl")
    ap.add_argument("--n", type=int, default=80)
    ap.add_argument("--temp", type=float, default=0.3)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()

    probes = [json.loads(l) for l in open(a.spec) if l.strip()]
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    log = open(a.out, "a")

    per_tool = {}
    confusion = {}  # expected route -> actual route -> count (the routing metric)
    n_ok_name = n_ok_args = n_ok_call = 0
    val_hits = val_total = 0
    n_val_probes = 0
    t0 = time.time()

    for idx, p in enumerate(probes):
        # phase 1: dispatch
        f1 = chat_file(probe_msgs(p))
        g1 = sample(a.mtlm, a.model, a.tok, f1, a.n, a.temp, a.seed)
        os.unlink(f1)
        name, args = parse_call(g1)
        name_ok = name == p["expect_tool"]
        args_ok = name_ok and args == p["expect_args"]
        call_ok = name_ok and args_ok

        # phase 2: follow-up — the assistant turn is the canonical call text and the
        # tool turn is the result the client would send, exactly as anvil renders it.
        # Chat probes (expect_tool null) have no follow-up: routing decision is the test.
        if p["expect_tool"] is None:
            g2, ev, hits, val_ok = "", [], [], True
        else:
            f2 = chat_file(probe_msgs(p) + [{"role": "assistant", "content": p["call"]},
                                            {"role": "tool", "content": p["tool_result"]}])
            g2 = sample(a.mtlm, a.model, a.tok, f2, a.n, a.temp, a.seed)
            os.unlink(f2)
            ev = p["expect_values"]
            hits = [v for v in ev if v in g2]
            val_ok = len(hits) == len(ev)

        n_ok_name += name_ok
        n_ok_args += args_ok
        n_ok_call += call_ok
        if ev:
            n_val_probes += 1
            val_hits += len(hits)
            val_total += len(ev)

        t = p["expect_tool"]
        confusion.setdefault(t or "chat", {}).setdefault(name or "(none)", 0)
        confusion[t or "chat"][name or "(none)"] += 1
        st = per_tool.setdefault(t or "chat", {"n": 0, "name": 0, "args": 0, "call": 0, "val_hits": 0, "val_total": 0, "val_ok": 0})
        st["n"] += 1
        st["name"] += name_ok
        st["args"] += args_ok
        st["call"] += call_ok
        st["val_hits"] += len(hits)
        st["val_total"] += len(ev)
        st["val_ok"] += val_ok

        rec = {"i": idx, "tool": t, "name_ok": name_ok, "args_ok": args_ok,
               "gen_call": g1[:300], "missing": [v for v in ev if v not in g2],
               "gen_followup": g2[:300]}
        log.write(json.dumps(rec) + "\n")
        log.flush()
        if (idx + 1) % 10 == 0:
            print(f"progress {idx+1}/{len(probes)} name={n_ok_name} call={n_ok_call} val={val_hits}/{val_total}",
                  file=sys.stderr, flush=True)

    n = len(probes)
    summary = {
        "probes": n,
        "name_acc": round(n_ok_name / n, 4),
        "args_acc": round(n_ok_args / n, 4),
        "call_ok": round(n_ok_call / n, 4),
        "value_acc": round(val_hits / val_total, 4) if val_total else None,
        "followup_ok": None,
        "elapsed_s": round(time.time() - t0, 1),
        "per_tool": {str(t): {"n": s["n"],
                         "name_acc": round(s["name"] / s["n"], 3),
                         "args_acc": round(s["args"] / s["n"], 3),
                         "call_ok": round(s["call"] / s["n"], 3),
                         "value_acc": round(s["val_hits"] / s["val_total"], 3) if s["val_total"] else None,
                         "followup_ok": round(s["val_ok"] / s["n"], 3)}
                     for t, s in sorted(per_tool.items(), key=lambda kv: str(kv[0]))},
        "confusion": confusion,
    }
    # followup_ok overall: fraction of probes where ALL expected values appeared
    log.write(json.dumps({"summary": summary}) + "\n")
    log.close()
    print(json.dumps(summary))

if __name__ == "__main__":
    main()
