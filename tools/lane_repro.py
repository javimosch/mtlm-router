#!/usr/bin/env python3
"""lane_repro.py — reproduce a lanepack's published eval numbers on YOUR appliance.

lane_verify.py proves the artifact is intact and honest-shaped. This tool proves
the numbers: it replays a labeled eval set through a running mtlm-router
(`/v1/route`, expert pinned to the lane) and compares measured metrics against
the pack's eval.json claims.

Sources for the eval set, in order:
  1. --eval FILE (jsonl: {"state"|"text"|"user": ..., "expect"|"route"|"label": ...})
  2. eval_sample.jsonl inside the pack (if the publisher shipped one)

Claims checked (only those present in eval.json are scored):
  holdout_acc        -> top-1 route accuracy on in-scope rows (excl. 'oos' labels)
  oos.oos_recall     -> share of oos-labeled rows routed to 'oos' or delegated
  plus verbatim per-row predictions are dumped for auditing.

Exit 0 if every measured metric is within --tol of the published claim,
1 on mismatch, 2 on usage/IO errors.

  python3 tools/lane_repro.py banking77-0.1.0.lanepack.tar.gz \
      --url http://localhost:8402 --eval bank77_test.jsonl [--tol 0.03]
"""
import argparse, json, sys, tarfile, tempfile, os, urllib.request

TOL = 0.03


def load_rows(path):
    rows = []
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        text = d.get("state") or d.get("text") or d.get("user")
        label = d.get("expect") or d.get("route") or d.get("label")
        if text and label:
            rows.append((text, label))
    return rows


def route(url, text, expert, key=None, timeout=15):
    hdrs = {"content-type": "application/json"}
    if key:
        hdrs["Authorization"] = "Bearer " + key
    req = urllib.request.Request(
        url.rstrip("/") + "/v1/route",
        data=json.dumps({"state": text, "expert": expert}).encode(),
        headers=hdrs)
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pack")
    ap.add_argument("--url", default="http://localhost:8402")
    ap.add_argument("--eval", dest="evalf")
    ap.add_argument("--expert")
    ap.add_argument("--tol", type=float, default=TOL)
    ap.add_argument("--key", help="Bearer key for gated endpoints")
    ap.add_argument("--dump", help="write per-row predictions jsonl here")
    a = ap.parse_args()

    if not tarfile.is_tarfile(a.pack):
        print(json.dumps({"ok": False, "error": "not a tar.gz"})); sys.exit(2)
    with tarfile.open(a.pack) as tf:
        members = {os.path.basename(m.name): m for m in tf.getmembers() if m.isfile()}
        man = json.loads(tf.extractfile(members["manifest.json"]).read())
        try:
            claims = json.loads(tf.extractfile(members["eval.json"]).read())
        except KeyError:
            claims = {}
        sample = None
        if not a.evalf and "eval_sample.jsonl" in members:
            tmp = tempfile.NamedTemporaryFile("wb", suffix=".jsonl", delete=False)
            tmp.write(tf.extractfile(members["eval_sample.jsonl"]).read()); tmp.close()
            sample = tmp.name
    evalf = a.evalf or sample
    if not evalf:
        print(json.dumps({"ok": False, "error": "no eval set: pass --eval or ship eval_sample.jsonl in the pack"}))
        sys.exit(2)
    rows = load_rows(evalf)
    if not rows:
        print(json.dumps({"ok": False, "error": "eval set empty"})); sys.exit(2)
    expert = a.expert or man.get("name")
    if not expert:
        print(json.dumps({"ok": False, "error": "no expert name: pass --expert"})); sys.exit(2)

    preds, n_err = [], 0
    for i, (text, label) in enumerate(rows):
        try:
            r = route(a.url, text, expert, a.key)
            preds.append({"i": i, "text": text, "label": label,
                          "route": r.get("route"), "action": r.get("action"),
                          "confidence": r.get("confidence"), "set_size": r.get("set_size")})
        except Exception as e:
            n_err += 1
            preds.append({"i": i, "text": text, "label": label, "error": str(e)[:120]})
        if (i + 1) % 50 == 0:
            print(f"scored {i+1}/{len(rows)}", file=sys.stderr)

    insc = [p for p in preds if p["label"] != "oos" and "route" in p]
    oosr = [p for p in preds if p["label"] == "oos" and "route" in p]
    acc = sum(1 for p in insc if p["route"] == p["label"]) / len(insc) if insc else None
    oos_rec = (sum(1 for p in oosr
                   if p["route"] == "oos" or p.get("action") == "delegate") / len(oosr)) if oosr else None

    measured = {"holdout_acc": acc, "oos_recall": oos_rec,
                "n": len(preds), "n_in_scope": len(insc), "n_oos": len(oosr),
                "n_errors": n_err}
    checks = []
    if acc is not None and isinstance(claims.get("holdout_acc"), (int, float)):
        d = abs(acc - claims["holdout_acc"])
        checks.append({"metric": "holdout_acc", "claimed": claims["holdout_acc"],
                       "measured": round(acc, 4), "delta": round(d, 4), "pass": d <= a.tol})
    oos_claim = (claims.get("oos") or {}).get("oos_recall") or claims.get("id_oos_recall")
    if oos_rec is not None and isinstance(oos_claim, (int, float)):
        d = abs(oos_rec - oos_claim)
        checks.append({"metric": "oos_recall", "claimed": oos_claim,
                       "measured": round(oos_rec, 4), "delta": round(d, 4), "pass": d <= a.tol})

    if a.dump:
        with open(a.dump, "w") as f:
            for p in preds:
                f.write(json.dumps(p) + "\n")

    ok = all(c["pass"] for c in checks) if checks else None
    print(json.dumps({
        "ok": ok, "pack": os.path.basename(a.pack), "lane": man.get("name"),
        "version": man.get("version"), "expert": expert, "eval_set": evalf,
        "measured": measured, "checks": checks,
        "note": None if checks else "eval.json carries no checkable claims"},
        indent=1))
    sys.exit(0 if ok else (1 if ok is False else 2))


if __name__ == "__main__":
    main()
