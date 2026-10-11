#!/usr/bin/env python3
"""Lane-count scaling: memory + latency as ANVIL_EXPERTS grows (N heads, one trunk).

Measured on rbm21, anvil-serve-mixed, m7router3s384 trunk (2026-10-11):
  1 lane  -> VmRSS 5524 kB, startup 2ms, route p50 38-39ms
  5 lanes -> VmRSS 6956 kB (+1.4MB, ~360KB/lane incl runtime bookkeeping),
             startup 5ms, route p50 39ms (identical)

Why flat: only the routed expert's matmul is scored per request
(+ optional ANVIL_SHADOW heads). Lanes cost ~file-size KB resident each and
~0 latency when not routed. "Many lanes on one frozen trunk" is effectively
free at catalog scale; the prefill dominates every request.

Method: two instances, 1 vs 5 experts; RSS from /proc; interleaved route
requests with pinned expert= so every call scores a head; server-side
latency_ms. Reproduce:
  ANVIL_EXPERTS=a:h1,b:h2,... ./anvil-serve-mixed model.bin PORT
then interleave /v1/route calls per instance and read latency_ms.
"""
import json
RESULT = {
  "date": "2026-10-11", "trunk": "m7router3s384", "method": "interleaved, expert-pinned, server latency_ms",
  "rss_kb": {"1_lane": 5524, "5_lanes": 6956, "per_lane_delta": 358},
  "startup_ms": {"1_lane": 2, "5_lanes": 5},
  "route_latency_ms": {"1_lane":  {"p50": 39.0, "p95": 41.0, "mean": 39.1},
                       "5_lanes": {"p50": 39.0, "p95": 45.0, "mean": 39.3}},
  "verdict": "lanes are ~360KB resident each and ~0 added latency; scales to catalog-size lane sets on one trunk",
}
if __name__ == "__main__":
    print(json.dumps(RESULT, indent=2))
