#!/usr/bin/env python3
"""route_latency.py — p50/p95/p99 latency for POST /v1/route.

Run on the host serving anvil (localhost avoids network noise). Mixes
short/medium/long texts; reports client wall time and the server's own
latency_ms when present.

  python3 bench/route_latency.py --url http://localhost:8440/v1/route \
      --expert civic_fr --n 100
"""
import argparse, json, statistics, urllib.request, time

TEXTS = [
    "what is my balance",
    "il y a un nid de poule enorme devant chez moi depuis trois jours",
    "book me a flight to paris next tuesday morning and a hotel near the airport please",
    "le lampadaire de ma rue est en panne depuis une semaine et la nuit c est tres sombre pour rentrer",
    "i would like to dispute a charge on my credit card statement from last month that i do not recognize at all",
    "mon voisin fait du bruit toute la nuit avec sa perceuse et je n arrive pas a dormir",
]


def probe(url, text, expert, key=""):
    body = {"state": text}
    if expert:
        body["expert"] = expert
    t0 = time.time()
    hdr = {"content-type": "application/json"}
    if key:
        hdr["authorization"] = "Bearer " + key
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=hdr)
    r = json.loads(urllib.request.urlopen(req, timeout=30).read())
    return (time.time() - t0) * 1000, r.get("latency_ms")


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(len(xs) * p))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--expert")
    ap.add_argument("--key", default="")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--out")
    a = ap.parse_args()
    client, server = [], []
    for i in range(a.n):
        c, s = probe(a.url, TEXTS[i % len(TEXTS)], a.expert, a.key)
        client.append(c)
        server.append(s or 0)
    out = {
        "url": a.url, "expert": a.expert, "n": a.n,
        "client_ms": {"p50": round(pct(client, .5), 1), "p95": round(pct(client, .95), 1),
                      "p99": round(pct(client, .99), 1), "mean": round(statistics.mean(client), 1)},
        "server_ms": {"p50": round(pct(server, .5), 1), "p95": round(pct(server, .95), 1),
                      "p99": round(pct(server, .99), 1), "mean": round(statistics.mean(server), 1)},
    }
    print(json.dumps(out, indent=1))
    if a.out:
        json.dump(out, open(a.out, "w"), indent=1)


main()
