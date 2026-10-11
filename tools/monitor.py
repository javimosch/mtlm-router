#!/usr/bin/env python3
"""Label-free drift monitor for conformal lanes.

Reads a decisions.jsonl (ANVIL_LOG) and reports, per lane and window:
  auto%      — fraction of decisions that answered (action != delegate)
  set_size   — mean/median prediction-set size among conformal decisions
  conf       — mean confidence of automated answers

The signal: set_size drifting upward or auto% drifting downward over time =
model uncertainty rising = calibration aging, BEFORE any labels arrive
(labels lag; this doesn't). Compare the last window against a baseline
window (first --baseline rows) and flag drift when set_size moves by more
than --tol of the baseline.

Usage:
    python3 tools/monitor.py logs/decisions.jsonl
    python3 tools/monitor.py logs/decisions.jsonl --window 500 --baseline 500 --tol 0.25 --json
Exit 1 on drift (for alerting hooks).
"""
import json, sys, argparse, statistics, collections

def load(path):
    rows = []
    for l in open(path):
        try:
            r = json.loads(l)
        except Exception:
            continue
        if isinstance(r, dict) and ("route" in r or "action" in r):
            rows.append(r)
    return rows

def lane_of(r):
    return r.get("expert") or r.get("domain") or r.get("lane") or "default"

def auto(r):
    return r.get("action") not in ("delegate", "abstain")

def summarize(rows):
    out = {}
    by = collections.defaultdict(list)
    for r in rows:
        by[lane_of(r)].append(r)
    for lane, rs in by.items():
        autos = [r for r in rs if auto(r)]
        sets = [r["set_size"] for r in rs if r.get("set_size") is not None]
        confs = [r.get("confidence", r.get("conf")) for r in autos if r.get("confidence", r.get("conf")) is not None]
        shad = [r["shadow"] for r in rs if isinstance(r.get("shadow"), dict)]
        agrees = [1 if s.get("agree") else 0 for s in shad]
        out[lane] = {
            "n": len(rs),
            "auto_pct": round(len(autos) / len(rs) * 100, 1) if rs else 0,
            "set_size_mean": round(statistics.mean(sets), 3) if sets else None,
            "conf_mean": round(statistics.mean(confs), 3) if confs else None,
            "shadow_n": len(shad),
            "shadow_agree_pct": round(statistics.mean(agrees) * 100, 1) if agrees else None,
        }
    return out

def ks2samp(xs, ys):
    """Two-sample Kolmogorov–Smirnov on conf distributions: D = max|F1-F2|,
    flagged when D exceeds the alpha=0.01 critical value
    c = 1.63 * sqrt((n+m)/(nm)). Label-free covariate-shift signal — the score
    distribution moving before any ground truth exists."""
    n, m = len(xs), len(ys)
    if n < 30 or m < 30:
        return None
    xs, ys = sorted(xs), sorted(ys)
    i = j = D = 0
    while i < n and j < m:
        if xs[i] <= ys[j]:
            i += 1
        else:
            j += 1
        D = max(D, abs(i / n - j / m))
    crit = 1.63 * ((n + m) / (n * m)) ** 0.5
    return {"D": round(D, 3), "crit": round(crit, 3), "shifted": D > crit}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("--window", type=int, default=500)
    ap.add_argument("--baseline", type=int, default=500)
    ap.add_argument("--tol", type=float, default=0.25, help="fractional set_size/auto drift tolerated")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    rows = load(a.log)
    if len(rows) < a.window + 20:
        print(json.dumps({"ok": True, "note": f"only {len(rows)} decisions — too few to judge"}))
        return
    base = summarize(rows[: a.baseline])
    recent = summarize(rows[-a.window:])
    # per-lane conf samples for the KS test (score-distribution shift)
    def confs_of(rs):
        by = collections.defaultdict(list)
        for r in rs:
            c = r.get("confidence", r.get("conf"))
            if c is not None:
                by[lane_of(r)].append(c)
        return by
    base_confs, rec_confs = confs_of(rows[: a.baseline]), confs_of(rows[-a.window:])
    report, drift = {"baseline": base, "recent": recent, "drift": []}, []
    for lane, r in recent.items():
        b = base.get(lane)
        ks = ks2samp(base_confs.get(lane, []), rec_confs.get(lane, []))
        if not b or not r.get("set_size_mean") or not b.get("set_size_mean"):
            d = {"lane": lane}
            if ks:
                d.update({"conf_ks_D": ks["D"], "conf_ks_crit_0.01": ks["crit"],
                          "conf_dist_shifted": ks["shifted"]})
                if ks["shifted"]:
                    d["drifted"] = True
                    drift.append(lane)
                    report["drift"].append(d)
            continue
        ss_shift = (r["set_size_mean"] - b["set_size_mean"]) / max(b["set_size_mean"], 1e-9)
        auto_shift = (r["auto_pct"] - b["auto_pct"]) / max(b["auto_pct"], 1e-9)
        d = {"lane": lane, "set_size_shift": round(ss_shift, 3), "auto_shift": round(auto_shift, 3)}
        if ks:
            d["conf_ks_D"] = ks["D"]
            d["conf_ks_crit_0.01"] = ks["crit"]
            d["conf_dist_shifted"] = ks["shifted"]
        if ss_shift > a.tol or auto_shift < -a.tol or (ks and ks["shifted"]):
            d["drifted"] = True
            drift.append(lane)
        report["drift"].append(d)
    report["ok"] = not drift
    print(json.dumps(report, indent=2))
    sys.exit(1 if drift else 0)

main()
