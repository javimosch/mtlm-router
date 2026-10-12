#!/usr/bin/env python3
"""lane_checklist — cross-surface drift check for catalog lanes.

A lane is wired in ~5 places and any one can be forgotten (the hosted
clinc floor gap was exactly this). Checks the local surfaces:

  index.json lane -> floors.json key            (floor decision recorded)
  index.json lane -> parity LANES alias         (offline/live gate)
  index.json lane -> README catalog table row   (public docs)

Remote surfaces it can't see (hosted unit env, meter demo whitelist,
catalog.html render) are printed as a manual checklist instead.

  python3 tools/lane_checklist.py [--heads ../mtlm-heads]
"""
import argparse, json, re, sys, os

# index lane name -> parity alias (hosted expert name). A lane can map to
# several hosted aliases (clinc150 -> clinc + clinc2 ship different heads).
ALIASES = {
    "clinc150": ["clinc", "clinc2"],
    "banking77": ["bank77"],
    "eq_tone": ["eq"],
    "helpdesk": ["helpdesk1", "helpdesk2", "it_helpdesk"],
    "civic": ["civic"],
    "civic_fr": ["civic_fr"],
    "mairie": ["mairie", "mairie_c"],
}


def parity_lanes(path):
    src = open(path).read()
    m = re.search(r'LANES\s*=\s*\{(.*?)\n\}', src, re.S)
    return set(re.findall(r'"([a-z_0-9]+)"\s*:', m.group(1))) if m else set()


def readme_lanes(path):
    rows = set()
    for line in open(path):
        m = re.match(r'\|\s*\**\s*([a-z_0-9]+)', line)
        if m and m.group(1) not in ("lane", "---"):
            rows.add(m.group(1))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--heads", default="../mtlm-heads")
    ap.add_argument("--parity", default="bench/catalog_parity.py")
    a = ap.parse_args()

    idx = json.load(open(os.path.join(a.heads, "index.json")))
    lanes = idx.get("lanes", idx if isinstance(idx, list) else [])
    names = sorted({l["name"] for l in lanes})
    floors = json.load(open(os.path.join(a.heads, "floors.json")))
    par = parity_lanes(a.parity)
    rd = readme_lanes(os.path.join(a.heads, "README.md"))

    problems, notes = [], []
    for name in names:
        if name not in floors:
            problems.append(f"{name}: not in floors.json (record min_conf or explicit null)")
        aliases = ALIASES.get(name, [name])
        hit = [al for al in aliases if al in par]
        if not hit:
            problems.append(f"{name}: no parity coverage (looked for {aliases})")
        if name not in rd:
            problems.append(f"{name}: no README catalog row")

    # latest-version check: index should mark one live pack per lane
    print(json.dumps({
        "lanes": names,
        "parity_covered": sorted(par),
        "problems": problems,
        "manual_checklist": [
            "hosted unit: ANVIL_EXPERTS has the lane + head file staged",
            "hosted unit: ANVIL_EXPERT_MINCONF carries the floors.json floor",
            "meter demo whitelist (mtl-cloud meter.src) includes the alias",
            "catalog.html regenerated + deployed (render_catalog.py)",
        ],
        "ok": not problems}, indent=1))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
