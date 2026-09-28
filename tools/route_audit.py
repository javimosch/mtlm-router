#!/usr/bin/env python3
"""Route-audit report generator — the 48h lead deliverable.

Feed a prospect's real requests (one per line, or JSONL with {"state": ...})
through a live mtlm-router and produce a self-contained HTML report showing
what the router already handles, where it abstains, and what a per-client
head adds. Publishable to hart as-is.

  # generic-lanes audit (before):
  python3 tools/route_audit.py --router http://localhost:8401 \
      --requests samples.txt --company "Acme SARL" --out audit.html

  # bootstrap the client head — label the same requests, train, spawn a
  # dedicated anvil, and produce a before/after report in one run:
  python3 tools/route_audit.py --router http://localhost:8401 \
      --requests samples.txt --labels labels.txt \
      --emit-head out/acme.head --hf hf-m7router3s384 \
      --probe tools/head_probe.py \
      --anvil-serve "./anvil-serve-pinonly models/m7router3s384.bin 8407" \
      --company "Acme SARL" --use-case "shared inbox triage" --out audit.html

Labels file: one `route :: request text` per line, or JSONL
{"user": "...", "expect_tool": "..."}. Requests matching a label carry an
expected/predicted column and the report scores the draft head's accuracy.

Draft heads are emitted last-token @ layer -1 (post-norm — the feature anvil
actually serves) under --serve-system, calibrated temp (auto).
"""
import argparse, html, json, os, statistics, subprocess, sys, tempfile, time
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

def load_labels(path):
    labels = {}
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("{"):
            r = json.loads(line)
            labels[(r.get("user") or r.get("state") or "").strip()] = r.get("expect_tool") or r.get("label")
        elif "::" in line:
            lab, req = line.split("::", 1)
            labels[req.strip()] = lab.strip()
    return labels

def build_spec(labels, path):
    with open(path, "w") as f:
        for req, lab in labels.items():
            f.write(json.dumps({"user": req, "expect_tool": lab}) + "\n")

def emit_head(probe, hf, spec, out):
    cmd = [sys.executable, probe, "--hf", hf, "--train", spec, "--holdout", spec,
           "--emit", out, "--emit-layer", "-1", "--emit-pool", "last",
           "--emit-temp", "auto", "--serve-system"]
    print("emitting:", " ".join(cmd), file=sys.stderr)
    subprocess.run(cmd, check=True)

def spawn_anvil(spec_cmd, head):
    # spec_cmd: "BIN MODEL PORT" — run in its cwd; expert = "audit"
    parts = spec_cmd.split()
    env = dict(os.environ, ANVIL_EXPERTS=f"audit:{head}", ANVIL_HEAD=head)
    proc = subprocess.Popen(parts, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    router = f"http://localhost:{parts[2]}"
    for _ in range(120):
        if proc.poll() is not None:
            raise RuntimeError("anvil exited early")
        r = route(router, "health probe", "audit")
        if r.get("route"):
            return proc, router
        time.sleep(0.5)
    proc.kill()
    raise RuntimeError("anvil never answered")

def audit(router, reqs, expert=None):
    out = []
    for s in reqs:
        r = route(router, s, expert)
        r["state"] = s
        out.append(r)
    return out

def abstained(r):
    return r.get("action") == "delegate" or r.get("route") == "escalate" or r.get("reason", "").startswith("low")

I18N = {
    "en": {"title": "Route audit", "subtitle": "how mtlm-router handles your real requests",
           "req": "request", "domain": "domain", "route": "route", "conf": "conf", "action": "action",
           "expected": "expected", "ok": "ok",
           "handled": "handled", "abstained": "abstained", "median_conf": "median conf", "coverage": "coverage",
           "before": "generic lanes", "after": "your draft head",
           "verdict": "verdict", "labels": "label accuracy",
           "footer": "mtlm-router route audit · each request scored live against a 7M-parameter decision layer"},
    "fr": {"title": "Audit de routage", "subtitle": "comment mtlm-router traite vos vraies requêtes",
           "req": "requête", "domain": "domaine", "route": "route", "conf": "conf", "action": "action",
           "expected": "attendu", "ok": "ok",
           "handled": "traitées", "abstained": "abstentions", "median_conf": "confiance médiane", "coverage": "couverture",
           "before": "lanes génériques", "after": "votre tête brouillon",
           "verdict": "verdict", "labels": "précision sur vos labels",
           "footer": "audit mtlm-router · chaque requête notée en direct par une couche de décision de 7M paramètres"},
}

def stats(rs):
    ab = sum(1 for r in rs if abstained(r))
    confs = [r.get("confidence", 0) for r in rs if "confidence" in r]
    return {"n": len(rs), "abst": ab, "cov": 1 - ab / max(len(rs), 1),
            "med": statistics.median(confs) if confs else 0}

def verdict(lang, s_gen, s_exp):
    if s_exp is None:
        cov = s_gen["cov"]
        if lang == "fr":
            if cov >= 0.8: return f"{cov:.0%} de vos requêtes sont déjà couvertes par les lanes génériques."
            return f"{cov:.0%} couvertes par les lanes génériques : vos requêtes forment un domaine nouveau — le cas exact d'une tête par client (~7 Ko)."
        if cov >= 0.8: return f"{cov:.0%} of your requests are already covered by the generic lanes."
        return f"{cov:.0%} covered by generic lanes: your requests are a new domain — exactly the case a per-client head (~7KB) is built for."
    if lang == "fr":
        return (f"Lanes génériques : {s_gen['cov']:.0%} couvertes. Avec une tête brouillon entraînée sur "
                f"{s_exp['n']} de vos exemples : {s_exp['cov']:.0%}. Une tête affinée sur ~1 000 lignes "
                f"labellisées pousse cette couverture en production.")
    return (f"Generic lanes: {s_gen['cov']:.0%} covered. A draft head trained on "
            f"{s_exp['n']} of your examples: {s_exp['cov']:.0%}. A head refined on ~1k "
            f"labeled rows pushes this to production coverage.")

def render(lang, meta, gen, exp, labels):
    t = I18N[lang]
    sg = stats(gen)
    se = stats(exp) if exp else None
    blocks = []

    def statrow(s):
        return (f'<div class="stat"><div class="v">{s["n"]}</div><div class="k">{t["req"]}</div></div>'
                f'<div class="stat"><div class="v">{s["n"]-s["abst"]}</div><div class="k">{t["handled"]}</div></div>'
                f'<div class="stat"><div class="v">{s["abst"]}</div><div class="k">{t["abstained"]}</div></div>'
                f'<div class="stat"><div class="v">{s["med"]:.2f}</div><div class="k">{t["median_conf"]}</div></div>'
                f'<div class="stat"><div class="v">{s["cov"]:.0%}</div><div class="k">{t["coverage"]}</div></div>')

    def table(rs, with_labels):
        rows = ""
        correct = 0; nl = 0
        for r in rs:
            ab = abstained(r)
            cls = ' style="color:#f59e0b"' if ab else ''
            lab_col = ""
            if with_labels:
                lab = labels.get(r["state"])
                if lab:
                    nl += 1
                    match = (r.get("route") == lab and not ab)
                    if match: correct += 1
                    mark = "✓" if match else "✗"
                    mc = "#10b981" if match else "#ef4444"
                    lab_col = f'<td class="mono">{html.escape(lab)}</td><td style="color:{mc}">{mark}</td>'
                else:
                    lab_col = '<td class="dim">—</td><td></td>'
            rows += (f'<tr><td class="req">{html.escape(r["state"][:120])}</td>'
                     f'<td{cls}>{html.escape(str(r.get("domain","—")))}</td>'
                     f'<td{cls}>{html.escape(str(r.get("route","—")))}</td>'
                     f'<td class="num">{r.get("confidence","—")}</td>'
                     f'<td class="mono">{html.escape(str(r.get("action","—")))}</td>{lab_col}</tr>')
        head = (f'<tr><th>{t["req"]}</th><th>{t["domain"]}</th><th>{t["route"]}</th>'
                f'<th class="num">{t["conf"]}</th><th>{t["action"]}</th>' +
                (f'<th>{t["expected"]}</th><th>{t["ok"]}</th>' if with_labels else '') + '</tr>')
        acc = f' · {t["labels"]}: {correct}/{nl} ({correct/nl:.0%})' if nl else ''
        return f'<div class="card"><table><thead>{head}</thead><tbody>{rows}</tbody></table></div>', acc

    table_gen, acc_gen = table(gen, bool(labels))
    blocks.append(f'<h2>{t["before"]}</h2><div class="stats">{statrow(sg)}</div>{table_gen}')
    if exp:
        table_exp, acc_exp = table(exp, bool(labels))
        caveat = ("<p class='dim'>draft head trained on the labeled sample itself — this proves the "
                  "mechanism, not production accuracy; a real head needs ~1k examples</p>"
                  if lang == "en" else
                  "<p class='dim'>tête brouillon entraînée sur l'échantillon labellisé lui-même — cela prouve "
                  "le mécanisme, pas la précision en production ; une vraie tête demande ~1 000 exemples</p>")
        blocks.append(f'<h2>{t["after"]}</h2><div class="stats">{statrow(se)}</div>{table_exp}{caveat}')

    return f'''<!doctype html>
<html lang="{lang}"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{t["title"]} — {html.escape(meta["company"] or "mtlm-router")}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0b0f17;color:#d9e2ec;font-family:-apple-system,'Segoe UI',system-ui,sans-serif;font-size:14px;line-height:1.55;padding:40px 24px}}
.c{{max-width:980px;margin:0 auto}}
h1{{font-size:24px;color:#f0f4f8}} .sub{{color:#6b7d94;font-size:13px;margin-bottom:24px}}
h2{{font-size:13px;color:#06b6d4;letter-spacing:.06em;text-transform:uppercase;font-family:ui-monospace,monospace;margin:28px 0 10px}}
.card{{background:#111827;border:1px solid #1e293b;border-radius:8px;padding:16px 18px;overflow-x:auto}}
table{{width:100%;border-collapse:collapse;font-size:12.5px}}
th{{text-align:left;color:#6b7d94;font-weight:500;padding:6px 10px 6px 0;border-bottom:1px solid #1e293b;font-family:ui-monospace,monospace;font-size:10px;text-transform:uppercase}}
td{{padding:7px 10px 7px 0;border-bottom:1px solid #1e293b;vertical-align:top}}
.req{{max-width:340px}} .num{{font-variant-numeric:tabular-nums;text-align:right}} .mono{{font-family:ui-monospace,monospace}} .dim{{color:#6b7d94}}
.stats{{display:flex;gap:12px;flex-wrap:wrap;margin:14px 0}}
.stat{{background:#111827;border:1px solid #1e293b;border-radius:8px;padding:12px 18px;min-width:110px}}
.stat .v{{font-size:22px;font-weight:700;color:#06b6d4;font-variant-numeric:tabular-nums}}
.stat .k{{font-size:10px;color:#6b7d94;text-transform:uppercase;letter-spacing:.05em}}
.vd{{background:#0c1a24;border:1px solid #164e63;border-radius:8px;padding:16px 18px;color:#a5f3fc}}
.ft{{margin-top:30px;font-size:11px;color:#6b7d94;border-top:1px solid #1e293b;padding-top:12px}}
</style></head><body><div class="c">
<h1>{t["title"]}{f' — {html.escape(meta["company"])}' if meta["company"] else ''}</h1>
<p class="sub">{t["subtitle"]}{f' · {html.escape(meta["use_case"])}' if meta["use_case"] else ''} · {time.strftime("%Y-%m-%d")}</p>
<h2>{t["verdict"]}</h2><div class="vd">{verdict(lang, sg, se)}</div>
{''.join(blocks)}
<p class="ft">{t["footer"]} · {html.escape(meta["router"])}</p>
</div></body></html>'''

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--router", required=True, help="generic-lane router for the 'before' run")
    ap.add_argument("--requests", required=True)
    ap.add_argument("--labels", default=None, help="route :: request lines, or JSONL {user,expect_tool}")
    ap.add_argument("--emit-head", default=None, help="train a draft head from --labels (needs --hf, --probe)")
    ap.add_argument("--hf", default=None)
    ap.add_argument("--probe", default=None, help="path to head_probe.py")
    ap.add_argument("--anvil-serve", default=None,
                    help="'BIN MODEL PORT' — spawn a pinned instance for the 'after' audit")
    ap.add_argument("--anvil-head", default=None,
                    help="head file the spawned instance serves as expert 'audit' (defaults to --emit-head)")
    ap.add_argument("--expert", default=None, help="pin this expert on --router for the 'after' run")
    ap.add_argument("--company", default="")
    ap.add_argument("--use-case", default="")
    ap.add_argument("--lang", choices=["en", "fr"], default="en")
    ap.add_argument("--maxc", type=int, default=450)
    ap.add_argument("--out", required=True)
    ap.add_argument("--json-out", default=None)
    a = ap.parse_args()

    reqs = load_requests(a.requests, a.maxc)
    if not reqs:
        print("no requests parsed", file=sys.stderr); sys.exit(1)
    labels = load_labels(a.labels) if a.labels else {}

    gen = audit(a.router, reqs)

    exp = None
    proc = None
    expert_router = a.router
    expert_name = a.expert
    try:
        if a.emit_head:
            if not (a.hf and a.probe):
                print("--emit-head needs --hf and --probe", file=sys.stderr); sys.exit(1)
            spec = tempfile.mktemp(suffix=".jsonl")
            build_spec(labels, spec)
            emit_head(a.probe, a.hf, spec, a.emit_head)
            os.unlink(spec)
        if a.anvil_serve:
            head_path = a.emit_head or a.anvil_head
            if not head_path:
                print("--anvil-serve needs --emit-head or --anvil-head", file=sys.stderr); sys.exit(1)
            proc, expert_router = spawn_anvil(a.anvil_serve, head_path)
            expert_name = "audit"
        if expert_name:
            exp = audit(expert_router, reqs, expert_name)
    finally:
        if proc:
            proc.terminate()

    out = render(a.lang, {"company": a.company, "use_case": a.use_case,
                          "router": a.router}, gen, exp, labels)
    with open(a.out, "w") as f:
        f.write(out)
    if a.json_out:
        json.dump({"generic": gen, "expert": exp}, open(a.json_out, "w"), indent=1)
    print(json.dumps({"requests": len(reqs), "generic": stats(gen),
                      "expert": stats(exp) if exp else None, "out": a.out}))

if __name__ == "__main__":
    main()
