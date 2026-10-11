#!/usr/bin/env python3
"""gen_speed.py — decode throughput for /v1/chat/completions.

Route latency (~39ms) is mostly prefill; this measures the generation
phase the router story never quotes: tokens/sec while the trunk decodes.

  python3 bench/gen_speed.py --url http://localhost:8317 [--n 8] [--max-tokens 64]

Reports per-request completion_tokens / wall_ms → tok/s, then p50 decode
rate across n requests (warmup excluded). Methodology note: decode is
memory-bound and serialized per request — wall/per-token is ITL.
"""
import argparse, json, time, urllib.request, statistics

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8317")
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--max-tokens", type=int, default=64)
    a = ap.parse_args()

    body = json.dumps({
        "messages": [{"role": "user", "content": "List twenty French town hall services, one per line."}],
        "max_tokens": a.max_tokens,
    }).encode()
    rates = []
    for i in range(a.n + 1):
        t0 = time.time()
        r = json.loads(urllib.request.urlopen(
            urllib.request.Request(f"{a.url}/v1/chat/completions", data=body,
                                   headers={"content-type": "application/json"}), timeout=120).read())
        wall = time.time() - t0
        ct = r["usage"]["completion_tokens"]
        rate = ct / wall
        if i:  # skip warmup
            rates.append(rate)
            print(f"[{i}] {ct} tok in {wall*1000:.0f}ms -> {rate:.1f} tok/s")
    rates.sort()
    print(json.dumps({
        "requests": len(rates), "max_tokens": a.max_tokens,
        "decode_toks_p50": round(statistics.median(rates), 1),
        "decode_toks_min": round(rates[0], 1),
        "decode_toks_max": round(rates[-1], 1),
    }))

if __name__ == "__main__":
    main()
