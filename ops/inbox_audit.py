#!/usr/bin/env python3
"""Zero-shot inbox audit for a prospect: classify their emails into THEIR categories via d1
/v1/systemone (choice question), then write a French markdown report.

  python3 inbox_audit.py --emails mails.jsonl --cats cats.json --company "X" --out report.md
      [--endpoint http://localhost:8410/v1/systemone] [--threshold 0.6]

mails.jsonl: one {"text": "...", "label": "optional expected category"} per line (anonymized).
cats.json:   {"devis": "demande de prix", "suivi": "où en est une livraison", ...}
Run on rbm21 (d1 listens on localhost:8410). Labels, when given, produce an accuracy figure.
"""
import argparse, json, urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("--emails", required=True); ap.add_argument("--cats", required=True)
ap.add_argument("--company", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--endpoint", default="http://localhost:8410/v1/systemone")
ap.add_argument("--threshold", type=float, default=0.6)
a = ap.parse_args()
cats = json.load(open(a.cats))
mails = [json.loads(l) for l in open(a.emails) if l.strip()]

rows = []
for m in mails:
    body = {"state": m["text"][:1500], "questions": {"cat": {"type": "choice",
            "instructions": "Which category does this email received by the company belong to?",
            "criteria": cats}}}
    req = urllib.request.Request(a.endpoint, json.dumps(body).encode(), {"content-type": "application/json"})
    ans = json.load(urllib.request.urlopen(req, timeout=60))["answers"]["cat"]
    rows.append((m, ans["choice"], ans["confidence"]))

auto = [r for r in rows if r[2] >= a.threshold]
labeled = [r for r in rows if r[0].get("label")]
auto_lab = [r for r in auto if r[0].get("label")]
ok = lambda rs: sum(1 for m, c, _ in rs if m["label"] == c)

L = [f"# Audit de tri — {a.company}", "",
     f"{len(rows)} emails analysés, catégories : {', '.join(cats)}. Aucun entraînement sur vos données à ce stade.", "",
     f"- **Triés automatiquement** (confiance ≥ {a.threshold:.0%}) : {len(auto)}/{len(rows)}",
     f"- **Mis de côté pour un humain** : {len(rows) - len(auto)}/{len(rows)}"]
if labeled:
    L.append(f"- **Exactitude sur les emails triés automatiquement** : {ok(auto_lab)}/{len(auto_lab)}")
    L.append(f"- Exactitude brute (tous emails, sans mise de côté) : {ok(labeled)}/{len(labeled)}")
L += ["", "| # | extrait | catégorie proposée | confiance | décision |" + (" attendu |" if labeled else ""),
      "|---|---|---|---|---|" + ("---|" if labeled else "")]
for i, (m, c, p) in enumerate(rows, 1):
    ex = m["text"][:70].replace("|", "/").replace("\n", " ")
    dec = "auto" if p >= a.threshold else "humain"
    L.append(f"| {i} | {ex}… | {c} | {p:.0%} | {dec} |" + (f" {m.get('label','')} |" if labeled else ""))
L += ["", "## Et ensuite",
      "Ce résultat est obtenu **sans entraînement**. Le pilote 30 jours (490 € HT) entraîne un modèle sur",
      "quelques centaines de vos emails, ce qui augmente la part triée automatiquement. Les emails douteux",
      "restent mis de côté plutôt que mal classés. Hébergé en France ou installé chez vous, aucune donnée",
      "envoyée à un service tiers."]
open(a.out, "w").write("\n".join(L) + "\n")
print(json.dumps({"n": len(rows), "auto": len(auto), "acc_auto": ok(auto_lab) if labeled else None, "out": a.out}))
