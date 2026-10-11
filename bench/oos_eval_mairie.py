"""mairie head OOS probe — offline vs live parity verified 2026-10-11.

Uses tools/head_io.load_head — the canonical mhd parser. Taps come from the
header (mairie: 3x max at layers 2,4,3 -> hf -4,-2,-3); never assume civic's
mean taps. Runs on rbm21 (/root/mtlm).
"""
import sys
sys.path.insert(0, "/root/mtlm/tools")
import json
import numpy as np
import head_probe as hp
import head_io

h = head_io.load_head("/root/mtlm/hosted/models/mairie_mt3.head")
print("taps resolved:", h["taps"], file=sys.stderr)
labels = h["labels"]

texts_in = ["1ere dotation bac verre", "changement bac casse", "ramassage encombrants",
            "depot illicite canape", "collecte bio quand ca passe", "sacs jaunes distribution",
            "point apport verre plein", "dechetterie horaires"]
texts_oos = ["carte identite renouvellement", "mariage rendez vous", "stationnement payant",
             "nid de poule rue des fleurs", "bruit voisinage nuit", "bus 42 en retard",
             "cantine scolaire inscription", "taxe fonciere augmentation", "lampadaire clignotant",
             "mariage civil dossier", "permis de construire", "passage pieton efface"]

rows = [(hp.DECIDE_SYS, [], t, "in") for t in texts_in] + \
       [(hp.DECIDE_SYS, [], t, "oos") for t in texts_oos]
F = hp.features("/root/mtlm/hf/router3s384", rows)
X = np.concatenate([F[t] for t in h["taps"]], axis=1)
P = head_io.probs(h, X)

nin = len(texts_in)
out = {"in": [], "oos": []}
for t, i in zip(texts_in, range(nin)):
    j = P[i].argmax()
    out["in"].append({"text": t, "route": labels[j], "conf": round(float(P[i, j]), 3)})
for k, t in enumerate(texts_oos):
    i = nin + k
    j = P[i].argmax()
    out["oos"].append({"text": t, "route": labels[j], "conf": round(float(P[i, j]), 3)})

mp_in, mp_oos = P[:nin].max(1), P[nin:].max(1)
esc = labels.index("escalate")
out["summary"] = {
    "in_scope_median": float(np.median(mp_in)),
    "oos_median": float(np.median(mp_oos)),
    "oos_escalate_share": float((P[nin:].argmax(1) == esc).mean()),
    "oos_leak_05": float((mp_oos >= 0.5).mean()),
    "oos_leak_07": float((mp_oos >= 0.7).mean()),
}
print(json.dumps(out, indent=1, ensure_ascii=False))
