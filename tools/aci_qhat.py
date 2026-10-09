#!/usr/bin/env python3
"""ACI-style online qhat controller for anvil-serve conformal gates.

Reads newly labeled outcomes for a conformal lane, updates the lane's qhat
with an adaptive-conformal step, and pushes it to the running server via
POST /_qhat (no restart — the gate picks it up on the next request).

Label contract — JSONL, one line per graded decision:
    {"expert": "mairie_c", "correct": 1}        # automated answer was right
    {"expert": "mairie_c", "correct": 0}        # automated answer was wrong
    (rows without "correct" or for other lanes are ignored)

Update rule (Gibbs & Candès ACI, applied to the singleton-set threshold):
    err_rate = fraction of automated answers marked wrong in the window
    qhat' = clamp(qhat - gamma * (err_rate - alpha), qmin, qmax)
        err_rate > alpha  -> qhat shrinks -> set threshold 1-qhat rises
                          -> fewer singletons -> more abstention
        err_rate < alpha  -> qhat grows   -> more singletons -> more coverage
This is the direct analog of alpha_{t+1} = alpha_t + gamma*(alpha - err_t):
our "miscoverage" event is a wrong automated answer, and qhat plays the
quantile-level role (lower qhat = more conservative).

Usage:
    aci_qhat.py --labels labels.jsonl --router http://127.0.0.1:8402 \
        --expert mairie_c --alpha 0.02 --gamma 0.5 \
        [--key $KEY] [--state aci_state.json] [--dry-run]

State file keeps per-expert {qhat, consumed line count} so each run only
scores labels appended since the previous run.
"""
import argparse, json, os, sys, urllib.request

def load_jsonl(path):
    rows = []
    if not os.path.exists(path):
        return rows
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows

def get_qhat(router, key):
    req = urllib.request.Request(router.rstrip("/") + "/_qhat",
                                 headers={"authorization": "Bearer " + key} if key else {})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

def set_qhat(router, key, expert, qhat):
    req = urllib.request.Request(router.rstrip("/") + "/_qhat", method="POST",
                                 data=json.dumps({"expert": expert, "qhat": qhat}).encode(),
                                 headers={"content-type": "application/json",
                                          **({"authorization": "Bearer " + key} if key else {})})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", required=True)
    ap.add_argument("--router", default="http://127.0.0.1:8402")
    ap.add_argument("--expert", required=True)
    ap.add_argument("--alpha", type=float, default=0.02)
    ap.add_argument("--gamma", type=float, default=0.5)
    ap.add_argument("--qmin", type=float, default=0.05)
    ap.add_argument("--qmax", type=float, default=0.95)
    ap.add_argument("--key", default=os.environ.get("ANVIL_KEY", ""))
    ap.add_argument("--state", default="aci_state.json")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    rows = load_jsonl(a.labels)
    state = {}
    if os.path.exists(a.state):
        state = json.load(open(a.state))
    st = state.get(a.expert, {"consumed": 0})
    new = [r for r in rows[st["consumed"]:] if r.get("expert") == a.expert and "correct" in r]
    st["consumed"] = len(rows)

    if not new:
        print(json.dumps({"ok": True, "expert": a.expert, "new_labels": 0, "action": "noop"}))
        state[a.expert] = st
        json.dump(state, open(a.state, "w"), indent=2)
        return

    err = sum(1 for r in new if not r["correct"]) / len(new)
    cur = get_qhat(a.router, a.key)
    qhat = cur.get("experts", {}).get(a.expert)
    if qhat is None:
        qhat = cur.get("default", 0.0)
    if not qhat:
        print(json.dumps({"ok": False, "error": "no qhat configured for " + a.expert}))
        sys.exit(1)

    qhat_new = min(a.qmax, max(a.qmin, qhat - a.gamma * (err - a.alpha)))
    res = {"ok": True, "expert": a.expert, "new_labels": len(new),
           "err_rate": round(err, 4), "alpha": a.alpha,
           "qhat": round(qhat, 4), "qhat_new": round(qhat_new, 4),
           "direction": "tighten" if qhat_new < qhat else ("loosen" if qhat_new > qhat else "hold")}
    if not a.dry_run and qhat_new != qhat:
        res["push"] = set_qhat(a.router, a.key, a.expert, qhat_new)
    state[a.expert] = st
    json.dump(state, open(a.state, "w"), indent=2)
    print(json.dumps(res))

if __name__ == "__main__":
    main()
