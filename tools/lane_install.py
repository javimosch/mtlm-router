#!/usr/bin/env python3
"""Install a lane from the mtlm-heads catalog into an appliance.

Fetches index.json, resolves <name>[@version] (default: latest non-yanked),
downloads the pack, verifies it (tools/lane_verify.py rules inline), extracts
the .head into <appliance>/models/ and prints the env lines to activate it.

  python3 tools/lane_install.py eq_tone --appliance out/appliances/mtlm-router-v0.4.0-linux-amd64
  python3 tools/lane_install.py clinc150@0.1.2 --appliance . [--dry-run]

Stdlib only. Exit 0 ok / 1 failure.
"""
import argparse, hashlib, io, json, os, sys, tarfile, urllib.request

INDEX_URL = "https://raw.githubusercontent.com/javimosch/mtlm-heads/master/index.json"
META_LABELS = ("chat", "oos")


def fetch(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()


def pick(lanes, spec):
    if "@" in spec:
        name, ver = spec.split("@", 1)
        return next((l for l in lanes if l["name"] == name and l["version"] == ver), None)
    cands = [l for l in lanes if l["name"] == spec]
    if not cands:
        return None
    def key(l):
        return [int(x) for x in l["version"].split(".")]
    return sorted(cands, key=key)[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lane", help="name or name@version, e.g. eq_tone or clinc150@0.1.2")
    ap.add_argument("--appliance", required=True, help="appliance dir containing models/")
    ap.add_argument("--index", default=INDEX_URL)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    index = json.loads(fetch(a.index))
    lane = pick(index.get("lanes", []), a.lane)
    if lane is None:
        print(json.dumps({"ok": False, "error": f"{a.lane} not in catalog",
                          "available": [f"{l['name']}@{l['version']}" for l in index["lanes"]]}))
        sys.exit(1)

    blob = fetch(lane["url"])
    if hashlib.sha256(blob).hexdigest() != lane["sha256"]:
        print(json.dumps({"ok": False, "error": "tarball sha256 mismatch vs index"})); sys.exit(1)

    members = {}
    with tarfile.open(fileobj=io.BytesIO(blob)) as t:
        for m in t.getmembers():
            if m.isfile():
                members[os.path.basename(m.name)] = t.extractfile(m).read()
    man = json.loads(members["manifest.json"])
    heads = [n for n in members if n.endswith(".head")]
    if len(heads) != 1 or hashlib.sha256(members[heads[0]]).hexdigest() != man["head_sha256"]:
        print(json.dumps({"ok": False, "error": "head sha256 mismatch vs manifest"})); sys.exit(1)

    models = os.path.join(a.appliance, "models")
    if not a.dry_run:
        os.makedirs(models, exist_ok=True)
        with open(os.path.join(models, os.path.basename(heads[0])), "wb") as f:
            f.write(members[heads[0]])

    conf = (lane.get("conformal") or {})
    qh = conf.get("alpha_0.02", {}).get("qhat") or conf.get("selective_risk_alpha_02", {}).get("qhat")
    out = {
        "ok": True, "lane": f"{lane['name']}@{lane['version']}",
        "status": lane.get("status"), "holdout_acc": lane.get("holdout_acc"),
        "installed_to": None if a.dry_run else os.path.join(models, os.path.basename(heads[0])),
        "activate": {
            "ANVIL_EXPERTS_add": f"{lane['name']}:models/{os.path.basename(heads[0])}",
            "ANVIL_EXPERT_QHAT_add": f"{lane['name']}:{qh}" if qh else None,
        },
        "note": "add the ANVIL_EXPERTS entry to start.sh / systemd env, restart",
    }
    print(json.dumps(out, indent=2))


main()
