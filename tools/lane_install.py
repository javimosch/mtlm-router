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
    live = [l for l in cands if not l.get("yanked")]
    if not live:
        return None
    def key(l):
        return [int(x) for x in l["version"].split(".")]
    return sorted(live, key=key)[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lane", nargs="?", help="name or name@version, e.g. eq_tone or clinc150@0.1.2")
    ap.add_argument("--appliance", required=True, help="appliance dir containing models/")
    ap.add_argument("--index", default=INDEX_URL)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true",
                    help="also patch <appliance>/start.sh with a managed env block (idempotent)")
    ap.add_argument("--list", action="store_true",
                    help="list lanes recorded in the appliance's managed block")
    ap.add_argument("--uninstall", metavar="NAME",
                    help="remove lane NAME from the managed block and delete its head")
    ap.add_argument("--check", action="store_true",
                    help="compare managed-block versions against the catalog index; "
                         "exit 1 if any installed lane is outdated (pip --outdated style)")
    a = ap.parse_args()

    start_sh = os.path.join(a.appliance, "start.sh")
    if a.list:
        text = open(start_sh).read() if os.path.exists(start_sh) else ""
        lanes = read_lanes(text)
        print(json.dumps({"ok": True, "lanes": [
            {"name": n, "head": kv.get("head"), "qhat": kv.get("qhat"),
             "ver": kv.get("ver"),
             "head_present": os.path.exists(os.path.join(a.appliance, kv.get("head", "")))}
            for n, kv in sorted(lanes.items())]}, indent=2))
        sys.exit(0)
    if a.uninstall:
        text = open(start_sh).read() if os.path.exists(start_sh) else ""
        lanes = read_lanes(text)
        if a.uninstall not in lanes:
            print(json.dumps({"ok": False, "error": f"{a.uninstall} not in managed block",
                              "installed": sorted(lanes)})); sys.exit(1)
        head = lanes.pop(a.uninstall)["head"]
        newtext = text
        if BEGIN in text and END in text:
            pre, rest = text.split(BEGIN, 1)
            _, post = rest.split(END, 1)
            newtext = pre + post.lstrip("\n")
            # regenerate via apply for remaining lanes
            open(start_sh, "w").write(newtext)
            for n, kv in list(lanes.items()):
                apply_env_block(start_sh, n, kv["head"],
                                None if kv.get("qhat") in (None, "-") else kv["qhat"],
                                kv.get("ver", "-"),
                                None if kv.get("minconf") in (None, "-") else kv["minconf"])
        hp = os.path.join(a.appliance, head)
        if os.path.exists(hp):
            os.remove(hp)
        print(json.dumps({"ok": True, "uninstalled": a.uninstall,
                          "removed_head": head, "remaining": sorted(lanes)}))
        sys.exit(0)

    if a.check:
        text = open(start_sh).read() if os.path.exists(start_sh) else ""
        installed = read_lanes(text)
        if not installed:
            print(json.dumps({"ok": True, "lanes": [], "note": "no managed lanes"})); sys.exit(0)
        index = json.loads(fetch(a.index))
        latest, latest_lane, by_nv = {}, {}, {}
        for l in index.get("lanes", []):
            by_nv[f"{l['name']}@{l['version']}"] = l
            if l.get("yanked"):
                continue
            cur = latest.get(l["name"])
            if cur is None or [int(x) for x in l["version"].split(".")] > [int(x) for x in cur.split(".")]:
                latest[l["name"]] = l["version"]
                latest_lane[l["name"]] = l
        rows, outdated = [], False
        for n, kv in sorted(installed.items()):
            inst, avail = kv.get("ver") or "-", latest.get(n)
            inst_lane = by_nv.get(f"{n}@{inst}")
            yanked = bool(inst_lane and inst_lane.get("yanked"))
            st = "not-in-catalog" if avail is None else (
                "unknown" if inst == "-" else
                ("outdated" if yanked or
                 [int(x) for x in inst.split(".")] < [int(x) for x in avail.split(".")]
                 else "current"))
            outdated = outdated or st == "outdated"
            row = {"lane": n, "installed": inst, "latest": avail, "status": st}
            if yanked:
                row["installed_yanked"] = True
                if inst_lane.get("superseded_by"):
                    row["superseded_by"] = inst_lane["superseded_by"]
            ll = latest_lane.get(n) or {}
            if ll.get("holdout_acc") is not None:
                row["latest_holdout_acc"] = ll["holdout_acc"]
            oo = ll.get("oos") or {}
            if oo.get("oos_recall") is not None:
                row["latest_oos_recall"] = oo["oos_recall"]
            row["latest_has_oos_class"] = "oos" in (ll.get("taxonomy") or [])
            row["latest_live_verified"] = bool(ll.get("live_verified"))
            rows.append(row)
        print(json.dumps({"ok": not outdated, "lanes": rows}, indent=2))
        sys.exit(1 if outdated else 0)

    if not a.lane:
        ap.error("lane required (or use --list/--uninstall/--check)")
    index = json.loads(fetch(a.index))
    lane = pick(index.get("lanes", []), a.lane)
    if lane is None:
        print(json.dumps({"ok": False, "error": f"{a.lane} not in catalog",
                          "available": [f"{l['name']}@{l['version']}" for l in index["lanes"]]}))
        sys.exit(1)

    def vkey(v):
        return [int(x) for x in v.split(".")]
    sibs = [l for l in index["lanes"] if l["name"] == lane["name"] and not l.get("yanked")]
    newest = max(sibs, key=lambda l: vkey(l["version"]))
    warnings = []
    if lane.get("yanked"):
        warnings.append(f"{lane['name']}@{lane['version']} is yanked"
                        + (f" — superseded by {lane['superseded_by']}" if lane.get("superseded_by") else "")
                        + (f": {lane['yank_reason']}" if lane.get("yank_reason") else ""))
    if newest["version"] != lane["version"]:
        warnings.append(f"newer version available: {lane['name']}@{newest['version']} "
                        f"(installing {lane['version']})")
    installed = read_lanes(open(start_sh).read()) if os.path.exists(start_sh) else {}
    if installed:
        cur = {n: kv.get("ver") for n, kv in installed.items()}
        old = cur.get(lane["name"])
        if old and old != "-" and old != lane["version"]:
            warnings.append(f"replaces installed {lane['name']}@{old}"
                            + (" (upgrade)" if vkey(lane["version"]) > vkey(old) else " (downgrade!)"))

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
    mc = (lane.get("operating") or {}).get("min_conf")
    head_rel = "models/" + os.path.basename(heads[0])

    applied = None
    if a.apply and not a.dry_run:
        applied = apply_env_block(os.path.join(a.appliance, "start.sh"),
                                  lane["name"], head_rel, qh, lane["version"], mc)
    out = {
        "ok": True, "lane": f"{lane['name']}@{lane['version']}",
        "status": lane.get("status"), "holdout_acc": lane.get("holdout_acc"),
        "installed_to": None if a.dry_run else os.path.join(models, os.path.basename(heads[0])),
        "activate": {
            "ANVIL_EXPERTS_add": f"{lane['name']}:models/{os.path.basename(heads[0])}",
            "ANVIL_EXPERT_QHAT_add": f"{lane['name']}:{qh}" if qh else None,
            "ANVIL_EXPERT_MINCONF_add": f"{lane['name']}:{mc}" if mc else None,
        },
        "applied_to": applied,
        "warnings": warnings,
        "note": "restart to activate" if applied else
                "add the ANVIL_EXPERTS entry to start.sh / systemd env (or re-run with --apply), restart",
    }
    print(json.dumps(out, indent=2))


BEGIN = "# >>> mtlm-lanes (managed by lane_install.py — do not edit)"
END = "# <<< mtlm-lanes <<<"


def read_lanes(text):
    """Parse `# lane` records out of a managed block. Each record:
    # lane <name> head=<rel> qhat=<v|-> ver=<semver|->"""
    lanes = {}
    if BEGIN in text and END in text:
        rest = text.split(BEGIN, 1)[1].split(END, 1)[0]
        for line in rest.splitlines():
            if line.startswith("# lane "):
                kv = dict(p.split("=", 1) for p in line.split(" ")[3:] if "=" in p)
                lanes[line.split(" ")[2]] = kv
    return lanes


def apply_env_block(start_sh, name, head_rel, qhat, ver, minconf=None):
    """Idempotently merge a lane env block into start.sh (marker-delimited,
    Ansible-blockinfile style). Re-running replaces the whole managed block
    regenerated from its own `# lane` records — multiple lanes accumulate."""
    if not os.path.exists(start_sh):
        return None
    text = open(start_sh).read()
    lanes = read_lanes(text)
    if BEGIN in text and END in text:
        pre, rest = text.split(BEGIN, 1)
        _, post = rest.split(END, 1)
        text = pre + post.lstrip("\n")
    lanes[name] = {"head": head_rel, "qhat": str(qhat) if qhat else "-",
                   "minconf": str(minconf) if minconf else "-", "ver": ver}
    block = [BEGIN]
    for lname, kv in sorted(lanes.items()):
        block.append(f"# lane {lname} head={kv['head']} qhat={kv.get('qhat','-')} "
                     f"minconf={kv.get('minconf','-')} ver={kv.get('ver','-')}")
        block.append(f'export ANVIL_EXPERTS="${{ANVIL_EXPERTS:+${{ANVIL_EXPERTS}},}}{lname}:{kv["head"]}"')
        if kv.get("qhat") not in (None, "", "-"):
            block.append(f'export ANVIL_EXPERT_QHAT="${{ANVIL_EXPERT_QHAT:+${{ANVIL_EXPERT_QHAT}},}}{lname}:{kv["qhat"]}"')
        if kv.get("minconf") not in (None, "", "-"):
            block.append(f'export ANVIL_EXPERT_MINCONF="${{ANVIL_EXPERT_MINCONF:+${{ANVIL_EXPERT_MINCONF}},}}{lname}:{kv["minconf"]}"')
    block.append(END)
    block = "\n".join(block) + "\n"
    lines = text.splitlines(keepends=True)
    for i, l in enumerate(lines):
        if l.startswith("exec "):
            lines.insert(i, block)
            break
    else:
        lines.append("\n" + block)
    open(start_sh, "w").write("".join(lines))
    return start_sh


main()
