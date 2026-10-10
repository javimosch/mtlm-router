#!/usr/bin/env python3
"""conformal_eval.py — coverage-guaranteed abstention for a served head.

Scores a holdout through the live runtime (/v1/decide gives the full
probability vector), splits it cal/eval, and reports, per alpha:
- qhat: the conformal nonconformity threshold (1 - p_true)
- auto%: rows where the prediction set is a singleton (auto-answerable)
- err_auto: error rate among auto-answered rows
- coverage/avgset/empty%: set statistics

The product claim: pick an error budget alpha -> get a guaranteed-max
operating point, instead of hand-tuning min_conf on a curve. Compare
against the raw-confidence floor printed below for the same eval split.

Usage:
  python3 tools/conformal_eval.py --holdout ../mtl-data/geored/geored12_holdout.jsonl \
      --url http://127.0.0.1:8398 --map collecte_om=collecte,collecte_selective=collecte
  (--probs scored.json to reuse a cached score pass)
"""
import argparse, json, random, sys, urllib.request

import numpy as np


def score(url, state):
    r = urllib.request.urlopen(urllib.request.Request(
        url + "/v1/decide", data=json.dumps({"state": state}).encode(),
        headers={"content-type": "application/json"}), timeout=15)
    return json.loads(r.read())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--holdout")
    p.add_argument("--url", default="http://127.0.0.1:8398")
    p.add_argument("--map", default=None)
    p.add_argument("--probs", default=None, help="cached [[label, probs], ...] json")
    p.add_argument("--save-probs", default=None)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--mondrian", action="store_true", help="class-conditional per-route qhat report")
    a = p.parse_args()

    lmap = dict(kv.split("=") for kv in a.map.split(",")) if a.map else {}
    if a.probs:
        scored = json.load(open(a.probs))
    else:
        rows = [json.loads(l) for l in open(a.holdout)]
        scored, skipped = [], 0
        for r in rows:
            try:
                d = score(a.url, r["user"])
                scored.append([lmap.get(r.get("expect_tool"), r.get("expect_tool")), d["probabilities"]])
            except urllib.error.HTTPError:
                skipped += 1
        print(f"{len(scored)} scored, {skipped} skipped (too-long)", file=sys.stderr)
        if a.save_probs:
            json.dump(scored, open(a.save_probs, "w"))

    random.seed(a.seed)
    random.shuffle(scored)
    n = len(scored)
    cal, ev = scored[:n // 2], scored[n // 2:]

    s = sorted(1 - p.get(y, 0.0) for y, p in cal)
    print(f"== conformal abstention ({len(ev)}-row eval, cal={len(cal)}) ==")
    print(f"{'alpha':>6} {'qhat':>6} {'auto%':>6} {'err_auto':>9} {'coverage':>9} {'avgset':>7} {'empty%':>7}")
    for alpha in [0.01, 0.02, 0.05, 0.10, 0.15, 0.20]:
        k = min(len(s), int(np.ceil((len(s) + 1) * (1 - alpha))))
        q = s[k - 1]
        auto = err = cov = ssz = empty = 0
        for y, pr in ev:
            S = [k2 for k2, v in pr.items() if v >= 1 - q]
            if len(S) == 1:
                auto += 1
                err += S[0] != y
            cov += y in S
            ssz += len(S)
            empty += len(S) == 0
        N = len(ev)
        print(f"{alpha:>6} {q:>6.3f} {auto / N * 100:>6.1f} {err / max(auto, 1) * 100:>9.2f} {cov / N * 100:>9.1f} {ssz / N:>7.2f} {empty / N * 100:>7.1f}")

    # Selective-risk control: bound the error rate AMONG AUTOMATED answers.
    # For a candidate threshold, the calibration split gives n_auto accepted
    # rows with k errors; the Clopper-Pearson upper bound says the true error
    # rate on automated traffic is <= ub at confidence 1-delta. Pick the most
    # permissive threshold whose bound fits the error budget — finite-sample,
    # no distribution assumption beyond exchangeable calibration traffic.
    def cp_upper(k, n, delta=0.05):
        # P(X<=k | n, p) = delta  ->  solve p via bisection on the binomial cdf
        from math import comb, exp, lgamma
        def cdf(k, n, p):
            # regularized incomplete beta via sum is unstable; use logs
            s = 0.0
            for i in range(k + 1):
                s += exp(lgamma(n + 1) - lgamma(i + 1) - lgamma(n - i + 1)
                         + i * np.log(p) + (n - i) * np.log(1 - p))
            return s
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = (lo + hi) / 2
            if cdf(k, n, mid) > delta: lo = mid
            else: hi = mid
        return hi

    print("\n== selective risk control (error bound among automated, 95% conf) ==")
    print(f"{'alpha':>6} {'qhat*':>6} {'auto%_eval':>10} {'ub95_cal':>9} {'err_eval':>8}")
    grid = np.linspace(0.05, 0.95, 19)
    for alpha in [0.01, 0.02, 0.05, 0.10]:
        best = None
        for q in grid:
            auto = err = 0
            for y, pr in cal:
                S = [k2 for k2, v in pr.items() if v >= 1 - q]
                if len(S) == 1:
                    auto += 1; err += S[0] != y
            if auto == 0: continue
            ub = cp_upper(int(err), auto)
            if ub <= alpha:
                aev = eev = 0
                for y, pr in ev:
                    S = [k2 for k2, v in pr.items() if v >= 1 - q]
                    if len(S) == 1:
                        aev += 1; eev += S[0] != y
                if best is None or q > best[0]:
                    best = (q, aev / len(ev) * 100, eev / max(aev, 1) * 100, ub)
        if best:
            print(f"{alpha:>6} {best[0]:>6.3f} {best[1]:>10.1f} {best[3] * 100:>9.2f} {best[2]:>8.2f}")
        else:
            print(f"{alpha:>6} {'none':>6} {'—':>6} {'—':>8} {'—':>8}")

    if a.mondrian:
        # Class-conditional (Mondrian) conformal: calibrate qhat PER TRUE LABEL.
        # Marginal coverage can hide a minority route that never gets auto-
        # answered; per-class qhat guarantees each route its own error budget.
        # Set rule at eval: include class c if p_c >= 1 - qhat_c.
        import collections
        byc = collections.defaultdict(list)
        for y, p in cal:
            byc[y].append(1 - p.get(y, 0.0))
        print("\n== mondrian (per-class qhat, class-conditional coverage) ==")
        for alpha in [0.02, 0.05, 0.10]:
            qc = {}
            for c, sc in byc.items():
                sc.sort()
                k = min(len(sc), int(np.ceil((len(sc) + 1) * (1 - alpha))))
                qc[c] = sc[k - 1]
            # eval: singleton if exactly one class passes ITS OWN threshold
            auto = err = 0
            per = collections.defaultdict(lambda: [0, 0, 0])  # class -> n, auto, err
            for y, pr in ev:
                S = [c for c, v in pr.items() if c in qc and v >= 1 - qc[c]]
                per[y][0] += 1
                if len(S) == 1:
                    auto += 1; per[y][1] += 1
                    if S[0] != y: err += 1; per[y][2] += 1
            N = len(ev)
            worst_cov = min((v[1] / v[0] for v in per.values() if v[0] >= 5), default=0)
            print(f"alpha={alpha}: auto={auto / N * 100:.1f}% err_auto={err / max(auto, 1) * 100:.2f}% "
                  f"worst-class auto={worst_cov * 100:.1f}% classes={len(qc)}")

    print("\n== raw-confidence floor (same eval split) ==")
    print(f"{'tau':>5} {'auto%':>6} {'err_auto':>9}")
    for t in [0.9, 0.8, 0.7, 0.55, 0.5, 0.4, 0.3, 0.2]:
        auto = err = 0
        for y, pr in ev:
            k2, v = max(pr.items(), key=lambda kv: kv[1])
            if v >= t:
                auto += 1
                err += k2 != y
        print(f"{t:>5} {auto / len(ev) * 100:>6.1f} {err / max(auto, 1) * 100:>9.2f}")


if __name__ == "__main__":
    main()
