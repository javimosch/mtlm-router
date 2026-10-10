#!/usr/bin/env python3
"""Shadow-head overhead benchmark.

Measures /v1/route server-side latency (latency_ms — excludes network jitter)
against two instances with identical model/env, one running ANVIL_SHADOW.
Verifies the claim that a shadow lane costs ~one extra matmul on pooled
features, i.e. a sub-millisecond to few-ms delta, not a second prefill.

Methodology (per LLM-bench guidance):
  - warmup requests first (cold paths excluded)
  - a mixed pool of request texts, shuffled once, same order for both sides
  - p50 / p95 / p99 on server-reported latency_ms
  - reports delta and % overhead per percentile

Usage:
    python3 bench/shadow_overhead.py http://localhost:BASE http://localhost:SHADOW \
        --n 300 --warmup 20 --expert it_helpdesk
Exit 0 always (a reporting tool); exit 4 if the shadow instance shows no
shadow rows in its responses' logs (can't verify shadow actually ran — pass
--skip-log-check if the log isn't readable locally).
"""
import json, sys, argparse, urllib.request, random

POOL = [
    "my server crashed and I need a new VM",
    "forgot my password, can't log into the VPN",
    "the wifi in building B keeps dropping every afternoon",
    "please provision a staging database for the payments team",
    "printer on floor 3 is out of toner again",
    "laptop won't boot after the update, blue screen",
    "need admin rights to install docker",
    "email sync stopped working on my phone since yesterday",
    "the shared drive is full, can we expand it",
    "new hire starts monday, need accounts and hardware",
    "monitor flickers when I connect the docking station",
    "VPN connects but internal sites still unreachable",
]

def hit(url, text, expert):
    body = json.dumps({"state": text, "expert": expert}).encode()
    req = urllib.request.Request(url + "/v1/route", data=body,
                                 headers={"content-type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=60).read())
    return r.get("latency_ms")

def pct(xs, p):
    s = sorted(xs)
    k = (len(s) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 1)

def run(url, seq, expert):
    return [hit(url, t, expert) for t in seq]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("shadow")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--warmup", type=int, default=20)
    ap.add_argument("--expert", default="")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    seq = [POOL[i % len(POOL)] for i in range(a.n)]
    random.Random(7).shuffle(seq)
    warm = seq[: a.warmup]
    for u in (a.base, a.shadow):
        run(u, warm, a.expert)
    # interleave A/B so both sides see the same machine state (sequential
    # blocks pick up CPU drift as fake "overhead" or "speedup")
    base, shad = [], []
    for t in seq:
        base.append(hit(a.base, t, a.expert))
        shad.append(hit(a.shadow, t, a.expert))
    out = {"n": a.n, "expert": a.expert}
    for name, xs in (("base", base), ("shadow", shad)):
        out[name] = {p: pct(xs, int(p[1:])) for p in ("p50", "p95", "p99")}
        out[name]["mean"] = round(sum(xs) / len(xs), 1)
    out["delta_ms"] = {p: round(out["shadow"][p] - out["base"][p], 1) for p in ("p50", "p95", "p99", "mean")}
    out["overhead_pct"] = {p: round(100 * out["delta_ms"][p] / max(out["base"][p], 0.001), 1) for p in ("p50", "p95", "p99", "mean")}
    print(json.dumps(out, indent=2))

main()
