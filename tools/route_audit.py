#!/usr/bin/env python3
"""Route-audit report generator — the 48h lead deliverable.

Feed a prospect's real requests (one per line, or JSONL with {"state": ...})
through a live mtlm-router and produce a self-contained HTML report showing
what the router already handles, where it abstains, and what a per-client
head would add. Publishable to hart as-is.

  python3 tools/route_audit.py --router http://localhost:8401 \
      --requests samples.txt --company "Acme SARL" \
      --use-case "shared support inbox triage" --lang en --out audit.html

Input lines are plain request text. JSONL input accepts {"state"} or
{"user"} keys. Blank lines and #-comments are skipped.
"""
import argparse, html, json, statistics, subprocess, sys, time
from collections import Counter

def route(router, state, expert=None):
    body = {"state": state}
    if expert:
        body["expert"] = expert
    try:
        p = subprocess.run(
            ["curl", "-s", "-m", "15", "-X", "POST", router.rstrip("/") + "/v1/route",
             "-H", "content-type: application/json",
             "-d", json.dumps(body)],
            capture_output=True, text=True, timeout=20)
        return json.loads(p.stdout)
    except Exception as e:
        return {"error": str(e)}

def load_requests(path, maxc):
    rows = []
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("{"):
            r = json.loads(line)
            line = r.get("state") or r.get("user") or ""
        if line:
            rows.append(line[:maxc] if maxc else line)
    return rows

I18N = {
    "en": {"title": "Route audit", "subtitle": "how mtlm-router handles your real requests",
           "req": "request", "domain": "domain", "route": "route", "conf": "conf",
           "action": "action", "handled": "handled", "abstained": "abstained",
           "median_conf": "median confidence", "coverage": "coverage",
           "domains": "domain distribution", "routes": "top routes",
           "verdict": "verdict", "footer": "mtlm-router route audit · each request scored live against a 7M-parameter decision layer"},
    "fr": {"title": "Audit de routage", "subtitle": "comment mtlm-router traite vos vraies requêtes",
           "req": "requête", "domain": "domaine", "route": "route", "conf": "conf",
           "action": "action", "handled": "traitées", "abstained": "abstentions",
           "median_conf": "confiance médiane", "coverage": "couverture",
           "domains": "répartition par domaine", "routes": "routes principales",
           "verdict": "verdict", "footer": "audit mtlm-router · chaque requête notée en direct par une couche de décision de 7M paramètres"},
}

def verdict(lang, cov, total):
    if lang == "fr":
        if cov >= 0.8:
            return f"{cov:.0%} de vos requêtes sont déjà routées correctement par les lanes génériques. Une tête entraînée sur votre vocabulaire (~1 000 exemples) couvrirait le reste."
        if cov >= 0.5:
            return f"{cov:.0%} couvertes aujourd'hui — un perimetre métier dédié (tête ~7 Ko) transformerait les abstentions en routes typées."
        return f"{cov:.0%} couvertes par les lanes génériques : vos requêtes sont un domaine nouveau. C'est exactement le cas où une tête par client s'impose."
    if cov >= 0.8:
        return f"{cov:.0%} of your requests already route correctly through the generic lanes. A head trained on your vocabulary (~1k examples) would cover the rest."
    if cov >= 0.5:
        return f"{cov:.0%} covered today — a dedicated business head (~7KB) would turn the abstentions into typed routes."
    return f"{cov:.0%} covered by generic lanes: your requests are a new domain. Exactly the case a per-client head is built for."

def render(lang, meta, results):
    t = I18N[lang]
    dom = Counter(r.get("domain") or "—" for r in results)
    routes = Counter(r.get("route") or "—" for r in results if r.get("action") == "tool_call")
    abst = [r for r in results if r.get("action") == "delegate" or r.get("reason", "").startswith("low") or r.get("route") == "escalate"]
    confs = [r.get("confidence", 0) for r in results if "confidence" in r]
    med = statistics.median(confs) if confs else 0
    cov = 1 - len(abst) / max(len(results), 1)
    rows = ""
    for r in results:
        ab = r.get("action") == "delegate" or r.get("route") == "escalate"
        cls = ' style="color:#f59e0b"' if ab else ''
        rows += (f'<tr><td class="req">{html.escape(r["state"][:120])}</td>'
                 f'<td{cls}>{html.escape(str(r.get("domain","—")))}</td>'
                 f'<td{cls}>{html.escape(str(r.get("route","—")))}</td>'
                 f'<td class="num">{r.get("confidence","—")}</td>'
                 f'<td class="mono">{html.escape(str(r.get("action","—")))}</td></tr>')
    dom_rows = "".join(f'<tr><td>{html.escape(k)}</td><td class="num">{v}</td><td class="num">{v/len(results):.0%}</td></tr>'
                       for k, v in dom.most_common())
    route_rows = "".join(f'<tr><td class="mono">{html.escape(k)}</td><td class="num">{v}</td></tr>'
                         for k, v in routes.most_common(10)) or f'<tr><td class="dim">—</td><td></td></tr>'
    return f'''<!doctype html>
<html lang="{lang}"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{t["title"]} — {html.escape(meta["company"] or "mtlm-router")}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0b0f17;color:#d9e2ec;font-family:-apple-system,'Segoe UI',system-ui,sans-serif;font-size:14px;line-height:1.55;padding:40px 24px}}
.c{{max-width:900px;margin:0 auto}}
h1{{font-size:24px;color:#f0f4f8}} .sub{{color:#6b7d94;font-size:13px;margin-bottom:24px}}
h2{{font-size:13px;color:#06b6d4;letter-spacing:.06em;text-transform:uppercase;font-family:ui-monospace,monospace;margin:28px 0 10px}}
.card{{background:#111827;border:1px solid #1e293b;border-radius:8px;padding:16px 18px;margin-bottom:14px}}
table{{width:100%;border-collapse:collapse;font-size:12.5px}}
th{{text-align:left;color:#6b7d94;font-weight:500;padding:6px 10px 6px 0;border-bottom:1px solid #1e293b;font-family:ui-monospace,monospace;font-size:10px;text-transform:uppercase}}
td{{padding:7px 10px 7px 0;border-bottom:1px solid #1e293b;vertical-align:top}}
.req{{max-width:340px}} .num{{font-variant-numeric:tabular-nums;text-align:right}} .mono{{font-family:ui-monospace,monospace}} .dim{{color:#6b7d94}}
.stats{{display:flex;gap:12px;flex-wrap:wrap;margin:14px 0}}
.stat{{background:#111827;border:1px solid #1e293b;border-radius:8px;padding:12px 18px;min-width:120px}}
.stat .v{{font-size:22px;font-weight:700;color:#06b6d4;font-variant-numeric:tabular-nums}}
.stat .k{{font-size:10px;color:#6b7d94;text-transform:uppercase;letter-spacing:.05em}}
.vd{{background:#0c1a24;border:1px solid #164e63;border-radius:8px;padding:16px 18px;color:#a5f3fc}}
.ft{{margin-top:30px;font-size:11px;color:#6b7d94;border-top:1px solid #1e293b;padding-top:12px}}
</style></head><body><div class="c">
<h1>{t["title"]}{f' — {html.escape(meta["company"])}' if meta["company"] else ''}</h1>
<p class="sub">{t["subtitle"]}{f' · {html.escape(meta["use_case"])}' if meta["use_case"] else ''} · {time.strftime("%Y-%m-%d")}</p>
<div class="stats">
<div class="stat"><div class="v">{len(results)}</div><div class="k">{t["req"]}</div></div>
<div class="stat"><div class="v">{len(results)-len(abst)}</div><div class="k">{t["handled"]}</div></div>
<div class="stat"><div class="v">{len(abst)}</div><div class="k">{t["abstained"]}</div></div>
<div class="stat"><div class="v">{med:.2f}</div><div class="k">{t["median_conf"]}</div></div>
<div class="stat"><div class="v">{cov:.0%}</div><div class="k">{t["coverage"]}</div></div>
</div>
<h2>{t["verdict"]}</h2><div class="vd">{verdict(lang, cov, len(results))}</div>
<h2>{t["req"]}</h2>
<div class="card"><table><thead><tr><th>{t["req"]}</th><th>{t["domain"]}</th><th>{t["route"]}</th><th class="num">{t["conf"]}</th><th>{t["action"]}</th></tr></thead><tbody>{rows}</tbody></table></div>
<h2>{t["domains"]}</h2>
<div class="card"><table><thead><tr><th>{t["domain"]}</th><th class="num">n</th><th class="num">%</th></tr></thead><tbody>{dom_rows}</tbody></table></div>
<h2>{t["routes"]}</h2>
<div class="card"><table><tbody>{route_rows}</tbody></table></div>
<p class="ft">{t["footer"]} · {html.escape(meta["router"])}</p>
</div></body></html>'''

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--router", required=True)
    ap.add_argument("--requests", required=True)
    ap.add_argument("--company", default="")
    ap.add_argument("--use-case", default="")
    ap.add_argument("--expert", default=None, help="pin an expert lane for every request")
    ap.add_argument("--lang", choices=["en", "fr"], default="en")
    ap.add_argument("--maxc", type=int, default=450, help="truncate requests to N chars (384-tok ctx)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--json-out", default=None)
    a = ap.parse_args()

    reqs = load_requests(a.requests, a.maxc)
    if not reqs:
        print("no requests parsed", file=sys.stderr); sys.exit(1)
    results = []
    for s in reqs:
        r = route(a.router, s, a.expert)
        r["state"] = s
        results.append(r)
    out = render(a.lang, {"company": a.company, "use_case": a.use_case, "router": a.router}, results)
    with open(a.out, "w") as f:
        f.write(out)
    if a.json_out:
        json.dump(results, open(a.json_out, "w"), indent=1)
    n_delegate = sum(1 for r in results if r.get("action") == "delegate")
    print(json.dumps({"requests": len(results), "delegated": n_delegate,
                      "coverage": round(1 - n_delegate / len(results), 3), "out": a.out}))

if __name__ == "__main__":
    main()
