#!/usr/bin/env python3
"""Confusion-cluster analysis for a conformal lane — the hierarchical-routing probe.

Question it answers: when the lane abstains with a multi-member prediction
set, are the members semantically adjacent (one confusion cluster) or spread
across the taxonomy? If abstentions are mostly intra-cluster, a two-level
router (coarse cluster -> fine route, or "route to the cluster's shared
handler") can automate at the parent level for most of today's abstains.

Method: build a co-occurrence graph over the cached conformal_eval --probs
output; keep only edges seen >= --min-edge times in multi-member sets (the
weight floor prevents transitive chaining from collapsing everything into
one component); connected components = empirical confusion clusters. Report
the share of multi-sets that live entirely inside one cluster.

Usage:
    python3 tools/set_cluster.py /tmp/c2probs.json --qhat 0.95 [--min-edge 5]
"""
import json, sys, argparse
from collections import Counter

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("probs")
    ap.add_argument("--qhat", type=float, default=0.95)
    ap.add_argument("--min-edge", type=int, default=5)
    a = ap.parse_args()
    d = json.load(open(a.probs))
    thr = 1 - a.qhat
    edges = Counter(); multisets = []; autos = empty = 0
    for y, p in d:
        S = [k for k, v in p.items() if v >= thr]
        if len(S) == 1: autos += 1; continue
        if len(S) == 0: empty += 1; continue
        if len(S) <= 8:
            multisets.append(S)
            for i in range(len(S)):
                for j in range(i + 1, len(S)):
                    edges[tuple(sorted((S[i], S[j])))] += 1
    par = {}
    def find(x):
        while par.setdefault(x, x) != x:
            par[x] = par[par[x]]; x = par[x]
        return x
    for e, c in edges.items():
        if c < a.min_edge: continue
        ra, rb = find(e[0]), find(e[1])
        if ra != rb: par[rb] = ra
    comps = {}
    for m in par: comps.setdefault(find(m), []).append(m)
    intra = sum(1 for S in multisets
                if all(m in par for m in S) and len({find(m) for m in S}) == 1)
    out = {
        "rows": len(d), "auto_singleton_pct": round(autos / len(d) * 100, 1),
        "empty_pct": round(empty / len(d) * 100, 1),
        "multi_sets": len(multisets),
        "intra_cluster": intra,
        "intra_pct": round(intra / max(len(multisets), 1) * 100, 1),
        "clusters": len(comps),
        "cluster_sizes": sorted((len(v) for v in comps.values()), reverse=True),
    }
    print(json.dumps(out, indent=1))
    for c in sorted(comps.values(), key=len, reverse=True)[:10]:
        print(f"  [{len(c)}] {sorted(c)[:20]}")

if __name__ == "__main__":
    main()
