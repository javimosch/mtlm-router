"""render_catalog.py — regenerate site/catalog.html from mtlm-heads index.json.

Static render (no CORS, no JS fetch): the catalog page IS the funnel surface —
every lane gets a card with version, status, class count, measured metrics,
install one-liner, and the sha256 of its pack.

Usage: python3 tools/render_catalog.py [--index URL|path] [--out site/catalog.html]
"""
import argparse, json, html, urllib.request, sys

INDEX = "https://raw.githubusercontent.com/javimosch/mtlm-heads/master/index.json"

def esc(s): return html.escape(str(s), quote=True)

def card(l):
    status = l.get("status", "demo")
    badge = {"certified": ("free · certified", "text-green-300 border-green-800 bg-green-950"),
             "demo": ("free · demo", "text-amber-300 border-amber-800 bg-amber-950")}.get(
                 status, (f"free · {esc(status)}", "text-gray-300 border-gray-700 bg-gray-900"))
    if l.get("yanked"):
        badge = ("yanked", "text-red-300 border-red-800 bg-red-950")
    ver = esc(l["version"]); name = esc(l["name"])
    acc = l.get("holdout_acc")
    metrics = []
    if acc is not None:
        n = l.get("n_holdout")
        metrics.append(f"<strong>{acc*100:.1f}%</strong>" + (f" holdout (n={n})" if n else " holdout"))
    conf = l.get("conformal") or {}
    for k in ("alpha_0.05", "alpha_0.02", "selective_risk_alpha_02"):
        c = conf.get(k)
        if c and c.get("auto") is not None:
            metrics.append(f"α=.05 → {c['auto']*100:.0f}% auto @ {c.get('err',0)*100:.2f}% err")
            break
    tax = l.get("taxonomy") or []
    tline = f"{l.get('classes', len(tax))} routes" + (": " + ", ".join(esc(t) for t in tax[:8]) + ("…" if len(tax) > 8 else "") if tax else "")
    prov = esc((l.get("provenance") or "")[:220])
    pricing = (l.get("pricing") or {}).get("tier", "free")
    return f"""
  <div class="bg-gray-900 border border-gray-800 rounded-xl p-6 {'opacity-50' if l.get('yanked') else ''}">
    <div class="flex items-baseline justify-between mb-2">
      <h3 class="mono text-lg text-cyan-300">{name}<span class="text-gray-500">@{ver}</span></h3>
      <span class="mono text-xs px-2 py-1 rounded border {badge[1]}">{badge[0]}</span>
    </div>
    <p class="text-gray-400 text-sm mb-3">{tline}{' · <span class="text-gray-500">' + prov + '</span>' if prov else ''}</p>
    <div class="text-sm text-gray-300 mb-4">{' · '.join(metrics) if metrics else '<span class="text-gray-600">no holdout metrics</span>'}</div>
    <pre class="mono text-xs bg-gray-950 border border-gray-800 rounded p-3 overflow-x-auto">python3 tools/lane_install.py {name}@{ver} --apply --appliance .</pre>
    <p class="text-gray-600 text-xs mt-2 mono">sha256: {esc(l.get('sha256',''))[:24]}… · pricing: {esc(pricing)}</p>
  </div>"""

MD_START, MD_END = "<!-- lanes:start -->", "<!-- lanes:end -->"


def md_table(lanes):
    rows = ["| lane | routes | status | holdout | `oos` class | install |", "|---|---|---|---|---|---|"]
    for l in sorted(lanes, key=lambda l: (l.get("yanked", False), l["name"], l["version"])):
        if l.get("yanked"):
            continue
        name = f"{l['name']}@{l['version']}"
        status = l.get("status", "demo")
        acc = l.get("holdout_acc")
        acc_s = f"{acc*100:.1f}%" if acc is not None else "—"
        oos = "yes" if "oos" in (l.get("taxonomy") or []) else "—"
        rows.append(f"| `{name}` | {l.get('classes', len(l.get('taxonomy', [])))} | {status} | {acc_s} | {oos} | `lane_install {l['name']}` |")
    return "\n".join(rows)


def render_readme(readme_path, lanes):
    src = open(readme_path).read()
    if MD_START not in src or MD_END not in src:
        return src, False
    pre, rest = src.split(MD_START, 1)
    _, post = rest.split(MD_END, 1)
    new = pre + MD_START + "\n" + md_table(lanes) + "\n" + MD_END + post
    return new, new != src


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default=INDEX)
    ap.add_argument("--out", default="site/catalog.html")
    ap.add_argument("--readme", default="README.md")
    ap.add_argument("--check", action="store_true",
                    help="do not write; exit 1 if --out differs from fresh render")
    a = ap.parse_args()
    raw = urllib.request.urlopen(a.index).read() if a.index.startswith("http") else open(a.index, "rb").read()
    lanes = json.loads(raw)["lanes"]
    cards = "\n".join(card(l) for l in sorted(lanes, key=lambda l: (l.get("yanked", False), l["name"], l["version"])))
    page = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lane catalog — mtlm-router</title><script src="https://cdn.tailwindcss.com"></script>
<style>.mono{{font-family:ui-monospace,monospace}}body{{background:#030712;color:#d1d5db}}</style></head>
<body class="max-w-4xl mx-auto px-6 py-14">
<p class="mono text-xs text-gray-500 mb-2"><a href="/" class="text-cyan-400 hover:underline">mtlm-router</a> / catalog</p>
<h1 class="text-3xl font-bold mb-2">Lane catalog</h1>
<p class="text-gray-400 text-sm mb-2">{len(lanes)} packs · every tarball sha256-pinned · <span class="mono">lane_install</span> verifies before installing.</p>
<p class="text-gray-500 text-sm mb-10">Certified = leak-free holdout eval stands behind the number. Demo = synthetic/partial corpus, live-verified but not a production claim. Generated from <a href="{INDEX}" class="text-cyan-400 hover:underline mono">index.json</a> — regenerated, never hand-edited.</p>
<div class="space-y-4">{cards}
</div>
<div class="mt-10 bg-gray-900 border border-cyan-800 rounded-xl p-6">
  <div class="mono text-cyan-300 text-sm mb-1">CUSTOM LANE — paid</div>
  <p class="text-gray-400 text-sm mb-4">None of these routes are yours? Send your route table (names + a few phrasings each): you get a ~7KB <span class="mono">.head</span> trained and calibrated on your corpus — eval report, abstention threshold, one free re-train after a week of shadow traffic. €149 / domain, one-off, 3 business days.</p>
  <a href="mailto:javi@intrane.fr?subject=mtlm-router%20custom%20head&body=Routes%20(name%3A%20example%20phrasings)%3A%0A%0A" class="inline-block bg-gray-800 border border-gray-700 text-gray-200 px-5 py-2 rounded-lg text-sm font-medium hover:bg-gray-700">Send your routes</a>
</div>
<p class="text-center text-gray-600 text-xs mt-14">generated by tools/render_catalog.py</p>
</body></html>"""
    if a.check:
        stale = []
        try:
            if open(a.out).read() != page:
                stale.append(a.out)
        except FileNotFoundError:
            stale.append(a.out + " (missing)")
        try:
            _, changed = render_readme(a.readme, lanes)
            if changed:
                stale.append(a.readme)
        except FileNotFoundError:
            pass
        print(json.dumps({"fresh": not stale, "stale": stale, "lanes": len(lanes)}))
        if stale:
            print("stale — run: python3 tools/render_catalog.py", file=sys.stderr)
            sys.exit(1)
        return
    open(a.out, "w").write(page)
    new_readme, changed = render_readme(a.readme, lanes)
    if changed:
        open(a.readme, "w").write(new_readme)
    print(json.dumps({"lanes": len(lanes), "out": a.out, "readme_updated": changed}))

if __name__ == "__main__":
    main()
