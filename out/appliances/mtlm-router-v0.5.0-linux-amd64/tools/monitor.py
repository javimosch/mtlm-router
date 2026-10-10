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
        out[lane] = {
            "n": len(rs),
            "auto_pct": round(len(autos) / len(rs) * 100, 1) if rs else 0,
            "set_size_mean": round(statistics.mean(sets), 3) if sets else None,
            "conf_mean": round(statistics.mean(confs), 3) if confs else None,
        }
    return out

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
    report, drift = {"baseline": base, "recent": recent, "drift": []}, []
    for lane, r in recent.items():
        b = base.get(lane)
        if not b or not r.get("set_size_mean") or not b.get("set_size_mean"):
            continue
        ss_shift = (r["set_size_mean"] - b["set_size_mean"]) / max(b["set_size_mean"], 1e-9)
        auto_shift = (r["auto_pct"] - b["auto_pct"]) / max(b["auto_pct"], 1e-9)
        d = {"lane": lane, "set_size_shift": round(ss_shift, 3), "auto_shift": round(auto_shift, 3)}
        if ss_shift > a.tol or auto_shift < -a.tol:
            d["drifted"] = True
            drift.append(lane)
        report["drift"].append(d)
    report["ok"] = not drift
    print(json.dumps(report, indent=2))
    sys.exit(1 if drift else 0)

main()
