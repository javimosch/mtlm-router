#!/usr/bin/env python3
"""Assemble a certified lane pack (*.lanepack.tar.gz).

A lane pack is the sellable unit: head weights + manifest (taxonomy,
measured metrics, conformal operating point, license) + eval report +
labels. "Certified" = the manifest carries a holdout eval and a conformal
qhat computed on a calibration split — not just an accuracy claim.

Usage:
    python3 tools/lane_pack.py \
        --head data/clinc150_mt3.head --name clinc150 --version 0.1.0 \
        --labels bench/clinc_labels.txt \
        --eval-json eval/clinc150_eval.json \
        --license Apache-2.0 \
        --provenance "CLINC150 public dataset (OOS subset), Apache-2.0" \
        --out out/lanes/
"""
import json, tarfile, hashlib, argparse, os, tempfile, shutil, time

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--head", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--labels", required=True, help="name :: description lines")
    p.add_argument("--eval-json", required=True, help='{"holdout_acc":..,"n":..,"oos_auroc":..,"qhat":..,"ops":[...]}')
    p.add_argument("--license", required=True)
    p.add_argument("--status", required=True, choices=["certified", "demo"],
                   help="certified = leak-free holdout eval stands behind it; demo = illustrative only")
    p.add_argument("--provenance", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    ev = json.load(open(a.eval_json))
    h = open(a.head, "rb").read()
    manifest = {
        "format": "lanepack/1",
        "name": a.name,
        "version": a.version,
        "created": int(time.time()),
        "head_sha256": hashlib.sha256(h).hexdigest(),
        "taxonomy": [l.split("::")[0].strip() for l in open(a.labels) if "::" in l],
        "metrics": ev,
        "status": a.status,
        "provenance": a.provenance,
        "license": a.license,
        "runtime": "anvil-serve >= v0.3.0 (ANVIL_EXPERTS=<lane>:<head>, ANVIL_EXPERT_QHAT if provided)",
    }
    os.makedirs(a.out, exist_ok=True)
    dst = os.path.join(a.out, f"{a.name}-{a.version}.lanepack.tar.gz")
    tmp = tempfile.mkdtemp()
    try:
        head_name = os.path.basename(a.head)
        shutil.copy(a.head, os.path.join(tmp, head_name))
        shutil.copy(a.labels, os.path.join(tmp, "labels.txt"))
        json.dump(manifest, open(os.path.join(tmp, "manifest.json"), "w"), indent=2)
        json.dump(ev, open(os.path.join(tmp, "eval.json"), "w"), indent=2)
        open(os.path.join(tmp, "LICENSE.txt"), "w").write(a.license + "\n")
        with tarfile.open(dst, "w:gz") as t:
            for f in os.listdir(tmp):
                t.add(os.path.join(tmp, f), arcname=f)
        print(json.dumps({"pack": dst, "bytes": os.path.getsize(dst), "sha256": manifest["head_sha256"]}))
    finally:
        shutil.rmtree(tmp)

main()
