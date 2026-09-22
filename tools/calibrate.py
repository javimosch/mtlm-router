#!/usr/bin/env python3
# calibrate.py — real-traffic calibration report from anvil decision logs.
#
# Reads ANVIL_LOG JSONL rows ({ts, ep, state, choice|answer|grade, conf|p_yes})
# and reports confidence histograms per endpoint. With --labels FILE
# (JSONL: {"state": ..., "correct_choice": ...}), joins on state text to
# compute per-bucket accuracy and empirical ECE on real traffic.
#
# Usage:
#   python3 tools/calibrate.py logs/decisions.jsonl
#   python3 tools/calibrate.py logs/decisions.jsonl --labels truth.jsonl
import json, sys

BUCKETS = [0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.001]

def bucket(c):
    for i in range(len(BUCKETS) - 1):
        if BUCKETS[i] <= c < BUCKETS[i + 1]:
            return i
    return len(BUCKETS) - 2

def main():
    path = sys.argv[1]
    labels = {}
    if "--labels" in sys.argv:
        lp = sys.argv[sys.argv.index("--labels") + 1]
        for line in open(lp):
            line = line.strip()
            if line:
                r = json.loads(line)
                labels[r["state"]] = r.get("correct_choice") or r.get("correct")

    rows = []
    for line in open(path):
        line = line.strip()
        if line:
            rows.append(json.loads(line))

    by_ep = {}
    for r in rows:
        ep = r["ep"]
        c = r.get("conf", r.get("p_yes", 0))
        by_ep.setdefault(ep, []).append((r, c))

    for ep, items in sorted(by_ep.items()):
        print("== %s  (n=%d)" % (ep, len(items)))
        nb = len(BUCKETS) - 1
        n = [0] * nb; conf_sum = [0.0] * nb; acc_n = [0] * nb; acc_ok = [0] * nb
        for r, c in items:
            b = bucket(c)
            n[b] += 1; conf_sum[b] += c
            truth = labels.get(r["state"])
            if truth is not None:
                pred = r.get("choice") or ("yes" if r.get("answer") == "yes" else r.get("grade"))
                acc_n[b] += 1
                if pred == truth:
                    acc_ok[b] += 1
        ece_num = 0.0; tot = len(items)
        labeled = sum(acc_n)
        print("  bucket        count  avg_conf  accuracy")
        for i in range(nb):
            if n[i] == 0:
                continue
            ac = conf_sum[i] / n[i]
            acc = ("%.3f" % (acc_ok[i] / acc_n[i])) if acc_n[i] else "-"
            print("  [%.2f,%.2f)  %-6d %-9.3f %s" % (BUCKETS[i], BUCKETS[i + 1], n[i], ac, acc))
            if acc_n[i]:
                ece_num += acc_n[i] * abs(ac - acc_ok[i] / acc_n[i])
        if labeled:
            print("  empirical ECE (labeled rows): %.4f  (n_labeled=%d)" % (ece_num / labeled, labeled))
        else:
            print("  (no labels — pass --labels truth.jsonl for accuracy/ECE)")
        print()

if __name__ == "__main__":
    main()
