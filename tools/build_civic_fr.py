#!/usr/bin/env python3
"""Build the civic_fr demo corpus: real DansMaRue (Paris) taxonomy phrases
slot-filled into French citizen-report templates.

DansMaRue publishes type/soustype labels (ODbL) but NO free text — so utterances
are synthetic over the real taxonomy. Honest demo lane; certified numbers need
real signalement text (client export).

Output: data/civic_fr/{train,holdout}.jsonl rows {"text","route"}.
"""
import json, random, re

random.seed(23)

ROUTES = {
    "objets_encombrants": [
        "un canapé abandonné", "un matelas jeté", "des gravats de chantier",
        "des cartons et des sacs de déchets", "un meuble encombrant",
        "une commode abandonnée", "un frigo déposé", "des objets encombrants",
        "un sommier", "des déchets divers en vrac", "un bac roulant abandonné",
        "une épave de caddie", "des barrières de chantier",
    ],
    "graffiti_affiches": [
        "un graffiti sur le mur", "des tags sur la façade", "des affiches sauvages",
        "des autocollants sur le panneau", "un tag sur le rideau métallique",
        "des graffitis sur la boîte aux lettres", "une affiche agrafée",
        "de la peinture sur le trottoir", "un tag sur la poubelle",
        "des affiches collées sur le mur", "un graffiti sur le pont",
    ],
    "proprete_dechets": [
        "des déjections canines", "des mégots par terre", "une poubelle débordante",
        "des déchets et salissures", "un épanchement d'urine",
        "une poubelle de rue sale", "des feuilles mortes accumulées",
        "un bac à ordures débordant", "des salissures au pied d'un arbre",
        "des bouteilles de gaz hilarant", "de la saleté sur le trottoir",
        "un dépôt sauvage près du point tri",
    ],
    "stationnement_epaves": [
        "une voiture en stationnement gênant", "un scooter garé sur le trottoir",
        "une épave de vélo", "une trottinette abandonnée",
        "un véhicule épave", "une moto abandonnée depuis des semaines",
        "une voiture sur la place handicapé", "un vélib vandalisé",
        "un deux-roues qui bloque le passage", "une épave de scooter",
    ],
    "voirie_trottoir": [
        "un trou dans la chaussée", "un affaissement du trottoir",
        "un pavé arraché", "une bosse sur la route", "un nid-de-poule",
        "un panneau routier endommagé", "un panneau mal orienté",
        "un revêtement de trottoir manquant", "une fissure dans la chaussée",
        "un trou dangereux sur la voie",
    ],
    "mobilier_urbain": [
        "un potelet détérioré", "une barrière cassée", "un banc public cassé",
        "une poubelle de rue dégradée", "un garde-corps détérioré",
        "un abribus endommagé", "une grille d'arbre cassée",
        "du mobilier urbain détérioré",
    ],
    "eclairage": [
        "un lampadaire éteint", "un réverbère qui ne marche plus",
        "un éclairage public éteint la nuit", "un lampadaire qui clignote",
        "une rue plongée dans le noir", "une lumière publique en panne",
        "un candélabre cassé",
    ],
    "arbres_vegetation": [
        "un arbre dangereux", "une branche qui menace de tomber",
        "des herbes éparses", "un arbre en mauvais état",
        "une haie qui envahit le trottoir", "une branche sur les câbles",
        "un arbre affaissé", "des branchages à ramasser",
    ],
    "eau": [
        "une fuite d'eau", "un écoulement d'eau permanent", "une bouche d'égout bouchée",
        "une flaque stagnante", "un appareil hydraulique qui fuit",
        "une canalisation cassée", "un débordement d'eau",
    ],
    "activites_commerciales": [
        "un étalage excessif", "une terrasse qui gêne la circulation",
        "des nuisances sonores du bar", "un commerce qui bloque le trottoir",
        "des encombrants de marché", "une terrasse non autorisée",
        "le restaurant laisse ses poubelles dehors",
    ],
    "autre": [
        "un problème de voirie", "un souci sur l'espace public",
        "un dysfonctionnement à signaler", "un problème dans la rue",
        "quelque chose d'anormal", "un incident sur la voie publique",
    ],
}

TPL = [
    "il y a {x} {loc}",
    "il y a {x} {loc}, c'est dangereux",
    "{x} {loc}",
    "je signale {x} {loc}",
    "signalement : {x} {loc}",
    "bonjour, {x} {loc} depuis plusieurs jours",
    "ça fait une semaine qu'il y a {x} {loc}",
    "urgent : {x} {loc}",
    "merci de faire quelque chose, {x} {loc}",
    "je voudrais signaler {x} {loc}",
    "depuis ce matin il y a {x} {loc}",
    "encore {x} {loc}, ras le bol",
    "{x} {loc}. merci d'intervenir",
    "anomalie {loc} : {x}",
    "y a-t-il moyen d'agir ? {x} {loc}",
    "{x} {loc}, risque d'accident",
    "à signaler {loc} : {x}",
    "problème récurrent : {x} {loc}",
    "{x} {loc} depuis des semaines",
    "des riverains se plaignent : {x} {loc}",
]
LOCS = [
    "devant chez moi", "rue de la République", "avenue de Paris", "sur le trottoir",
    "au coin de la rue", "place du marché", "devant l'école", "près du parc",
    "dans ma rue", "à côté de la boulangerie", "sur la chaussée", "devant le portail",
    "boulevard central", "impasse des Lilas", "près de l'arrêt de bus",
    "au pied de l'immeuble", "rue Victor Hugo", "face au métro", "dans l'allée",
    "juste devant la mairie", "",
]

def gen(route, phrases, n):
    out = []
    seen = set()
    tries = 0
    while len(out) < n and tries < n * 40:
        tries += 1
        t = random.choice(TPL).format(x=random.choice(phrases), loc=random.choice(LOCS))
        t = re.sub(r"\s+", " ", t).strip(" ,.")
        if t not in seen:
            seen.add(t)
            out.append({"text": t, "route": route})
    return out

corpus = []
for route, phrases in ROUTES.items():
    corpus += gen(route, phrases, 150)
random.shuffle(corpus)
by = {}
for r in corpus:
    by.setdefault(r["route"], []).append(r)
tr, hold = [], []
for k, rs in by.items():
    n = int(len(rs) * 0.8)
    tr += rs[:n]; hold += rs[n:]
random.shuffle(tr); random.shuffle(hold)
import os
os.makedirs("data/civic_fr", exist_ok=True)
w = lambda rs, p: open(p, "w").write("\n".join(json.dumps(r, ensure_ascii=False) for r in rs))
w(tr, "data/civic_fr/train.jsonl")
w(hold, "data/civic_fr/holdout.jsonl")
print(json.dumps({"routes": len(ROUTES), "train": len(tr), "holdout": len(hold),
                  "per_route": {k: len(v) for k, v in by.items()}}, ensure_ascii=False))
