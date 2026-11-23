#!/usr/bin/env python3
"""Generate the MTLM S2D site (s2d.intrane.fr): EN index.html + FR fr.html, robots, sitemap.

  python3 tools/build_s2d.py      -> writes s2d-site/

S2D = speech-to-decision: a micro model that decides what to do with a call straight from the audio,
no transcript, on a plain CPU. Part of the MTLM family (Router, Voice). Reuses the MTLM Voice styling.
Every number here must match a measurement (see memgraph project mtlm: s2d-v1-encoder, s2d-cascade,
s2d-front-gate, s2d-competitors). Competitor facts: only what their own pages/papers say; "not
published" when unknown; no disparaging wording.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_voice as BV  # noqa: E402  (CSS + samples shared with MTLM Voice)

OUT = os.path.join(HERE, "..", "s2d-site")
SITE = "https://s2d.intrane.fr"
API = "https://api.mtlm-router.intrane.fr/demo/voice"
FR_SAMPLES = [s for s in BV.SAMPLES if s["lang"] == "fr"]
CONTACT = "https://www.linkedin.com/in/arancibiajav/"

# Competitor rows: (name, url, what, runs_on, size, french, calib, licence) — EN, FR
COMP = {
 "en": [
  ("S2D (MTLM)", None, "Fixed decisions trained per use case", "Plain CPU, your servers", "~88M (encoder) + tiny head", "Yes — measured on real calls", "Threshold set on real outcomes", "Self-host, commercial"),
  ("Hume Audio Decision API", "https://dev.hume.ai/audio-decisions/docs/overview", "Any question about an audio file", "Hume cloud only", "Not published", "Not published", "Agreement with human raters (70.7%)", "Paid API"),
  ("DuplexJev", "https://docs.pipecat.ai/api-reference/server/extensions/pipecat-duplexjev", "Multiple-choice decisions for voice agents", "GPU (vLLM)", "4B / 32B", "Not published", "Not published", "Open weights; reported non-commercial"),
  ("AudioJev", "https://arxiv.org/abs/2610.01293", "Any question, 2–36 answers", "GPU", "~3–5B (Qwen2.5-Omni)", "Not stated", "Answer-order consistency only", "Qwen research licence"),
  ("Qwen-Audio-Jev", "https://arxiv.org/abs/2610.21614", "Choice / yes-no / score head on an audio LLM", "Not stated", "Audio LLM", "Not stated", "Not stated", "Not stated"),
  ("marimba", "https://arxiv.org/abs/2611.18330", "Typed speech decisions (turn end, language, terms)", "Not stated", "0.6B (Qwen3-ASR)", "No (pt-BR, English)", "AUROC on research sets", "CC BY 4.0"),
 ],
 "fr": [
  ("S2D (MTLM)", None, "Décisions fixes, entraînées par cas d'usage", "CPU standard, vos serveurs", "~88M (encodeur) + mini-tête", "Oui — mesuré sur de vrais appels", "Seuil fixé sur des résultats réels", "Auto-hébergé, commercial"),
  ("Hume Audio Decision API", "https://dev.hume.ai/audio-decisions/docs/overview", "N'importe quelle question sur un audio", "Cloud Hume uniquement", "Non publié", "Non publié", "Accord avec des annotateurs (70,7 %)", "API payante"),
  ("DuplexJev", "https://docs.pipecat.ai/api-reference/server/extensions/pipecat-duplexjev", "Choix multiples pour agents vocaux", "GPU (vLLM)", "4B / 32B", "Non publié", "Non publié", "Poids ouverts ; non commercial (rapporté)"),
  ("AudioJev", "https://arxiv.org/abs/2610.01293", "N'importe quelle question, 2–36 réponses", "GPU", "~3–5B (Qwen2.5-Omni)", "Non précisé", "Cohérence d'ordre des réponses seulement", "Licence recherche Qwen"),
  ("Qwen-Audio-Jev", "https://arxiv.org/abs/2610.21614", "Tête choix / oui-non / score sur un LLM audio", "Non précisé", "LLM audio", "Non précisé", "Non précisé", "Non précisé"),
  ("marimba", "https://arxiv.org/abs/2611.18330", "Décisions typées (fin de tour, langue, termes)", "Non précisé", "0,6B (Qwen3-ASR)", "Non (pt-BR, anglais)", "AUROC sur jeux de recherche", "CC BY 4.0"),
 ],
}

T = {
 "en": dict(
  lang="en", file="index.html", other="/fr", other_label="Français",
  title="MTLM S2D — decide from the voice, skip the transcript",
  desc="S2D is a micro speech-to-decision model: it routes, hands off or blocks a call straight from the audio, in ~0.4 s on a plain CPU. Part of the MTLM family.",
  nav=[("#demo", "Demo"), ("#how", "How it works"), ("#numbers", "Numbers"), ("#market", "Landscape")], nav_cta="Pilot S2D",
  eyebrow="MTLM family · Speech-to-decision · Micro model on CPU",
  h1="Decide from the voice.<br>Skip the transcript.",
  sub="S2D listens to the caller and decides what to do — route the intent, hand off to a human, block a robocall — without writing a single word of transcript. A micro model, ~0.4 s on a plain CPU, on your own servers.",
  cta1="Hear it decide", cta2="Pilot S2D on your calls",
  proof=["No GPU", "No transcript, no LLM call", "French today, English in training"],
  msgs=[("Fast", "~0.4 s", "per call on a plain CPU, vs ~11 s for speech-to-text + decision on the same box."),
        ("Accurate", "84% alone · 89% in cascade", "on 269 real French bank calls (MInDS-14), cascade = S2D first, transcript only when unsure."),
        ("Careful", "Acts only when sure", "Below a calibrated bar it hands over to the speech-to-text chain instead of guessing."),
        ("Micro", "~88M parameters", "A speech encoder plus a tiny decision layer. Not an audio LLM.")],
  demo_h="Hear it decide", demo_p="French sample calls (synthetic voices, phone-band audio). Each one goes to S2D first; the panel shows whether S2D decided on its own or handed over to the transcript chain, and how long it took.",
  demo_more="Record your own call, or try English, on the full MTLM Voice demo →", wait="S2D is listening…", err="The demo is busy, try again in a minute.", lim="Demo limit reached for now — try again later.",
  pick="Pick a call on the left.", a={"route": "Route", "handoff": "Hand off to a human", "block": "Block", "clarify": "Ask again", "confirm": "Confirm with caller"},
  s2d_yes="⚡ Decided by S2D, from the audio", s2d_no="S2D unsure → speech-to-text chain decided", guess="S2D guessed", bar="its bar", no_tx="(none — S2D never writes the text)",
  heard="Transcript", m_s2d="S2D", m_total="speech-to-text", m_conf="confidence",
  how_h="How it works", how_p="Most voice stacks transcribe every call, then send the text to a model to decide. S2D removes the middle step for the calls it is sure about.",
  steps=[("1 · Listen", "The call audio goes through a speech encoder (Whisper-small class, CPU, fp32). No text is produced."),
         ("2 · Decide", "A tiny decision layer reads the encoder's summary and outputs one decision per intent, with a probability."),
         ("3 · Act or hand over", "Above a calibrated bar, S2D acts at once. Below it, your existing speech-to-text + decision chain takes the call — nothing is lost.")],
  num_h="Measured, not promised", num_p="All on one 6-core CPU. Real calls = MInDS-14 French (PolyAI, real bank customers), report half: 269 calls never used for training.",
  nums=[("S2D alone", "84.0%", "right, ~0.4 s per call"), ("Cascade", "88.9%", "right · 66.5% decided by S2D · 2 wrong"), ("Transcript chain alone", "85.9%", "right, ~11 s per call"),
        ("Front-desk intents", "0 wrong", "automatic decisions on held-out voices, accents and wordings (synthetic test sets)")],
  num_note="Honest limits: S2D's front-desk training data is synthetic; on wordings it never heard it decides alone only ~26% of the time (the rest goes to the chain). English is being trained now.",
  mk_h="Not another audio LLM", mk_p="Speech-to-decision is suddenly a category. Everyone else is building it on top of billion-parameter audio LLMs, on GPUs or in their cloud. S2D is the micro-model, CPU-only, self-hosted corner of the market — and the only one with published French results on real calls.",
  mk_cols=["", "What it decides", "Runs on", "Model size", "French", "Calibration", "Licence"],
  mk_src="From each project's own docs or paper, November 2026. “Not published” = we found no public figure. Tell us if something is out of date.",
  niche=[("Micro, not mega", "~88M parameters vs 0.6B–32B. Fits next to your telephony on the servers you already have."),
         ("CPU, not GPU", "No accelerator to buy or rent. ~0.4 s per call on a 6-core CPU."),
         ("Your servers, not their cloud", "Audio never leaves your network — what call centres and regulated sectors need."),
         ("Fixed decisions, done well", "The trade-off: S2D answers your intents, trained for you, not any question typed at runtime.")],
  fam_h="The MTLM family", fam=[("MTLM Router", "https://mtlm-router.intrane.fr/", "Decision models for text: route, abstain, escalate."),
        ("MTLM Voice", "https://voice.intrane.fr/", "Speech-to-text → decision → spoken reply, for voice agents."),
        ("MTLM S2D", None, "Speech straight to decision. You are here.")],
  cta_h="Pilot S2D on your calls", cta_p="We train S2D on your intents and your callers' language, measure it on your recordings, and set the safety bar with you. Self-hosted from day one.", cta_b="Talk to us",
  foot="MTLM S2D · part of MTLM, by intrane.fr",
 ),
 "fr": dict(
  lang="fr", file="fr.html", other="/", other_label="English",
  title="MTLM S2D — décider depuis la voix, sans transcription",
  desc="S2D est un micro-modèle parole→décision : il oriente, transfère ou bloque un appel directement depuis l'audio, en ~0,4 s sur un CPU standard. Famille MTLM.",
  nav=[("#demo", "Démo"), ("#how", "Fonctionnement"), ("#numbers", "Chiffres"), ("#market", "Marché")], nav_cta="Piloter S2D",
  eyebrow="Famille MTLM · Parole→décision · Micro-modèle sur CPU",
  h1="Décider depuis la voix.<br>Sans transcription.",
  sub="S2D écoute l'appelant et décide quoi faire — orienter la demande, passer à un humain, bloquer un robot — sans écrire un seul mot de transcription. Un micro-modèle, ~0,4 s sur un CPU standard, sur vos serveurs.",
  cta1="L'entendre décider", cta2="Piloter S2D sur vos appels",
  proof=["Sans GPU", "Sans transcription ni appel LLM", "Français aujourd'hui, anglais en entraînement"],
  msgs=[("Rapide", "~0,4 s", "par appel sur CPU standard, contre ~11 s pour transcription + décision sur la même machine."),
        ("Précis", "84 % seul · 89 % en cascade", "sur 269 vrais appels bancaires français (MInDS-14) ; cascade = S2D d'abord, transcription seulement en cas de doute."),
        ("Prudent", "N'agit que s'il est sûr", "Sous un seuil calibré, il passe la main à la chaîne de transcription au lieu de deviner."),
        ("Micro", "~88M paramètres", "Un encodeur de parole et une mini-couche de décision. Pas un LLM audio.")],
  demo_h="L'entendre décider", demo_p="Appels d'exemple en français (voix de synthèse, audio bande téléphone). Chacun passe d'abord par S2D ; le panneau montre si S2D a décidé seul ou passé la main à la transcription, et en combien de temps.",
  demo_more="Enregistrez votre propre appel, ou testez l'anglais, sur la démo complète MTLM Voice →", wait="S2D écoute…", err="La démo est occupée, réessayez dans une minute.", lim="Limite de la démo atteinte — réessayez plus tard.",
  pick="Choisissez un appel à gauche.", a={"route": "Orienter", "handoff": "Passer à un humain", "block": "Bloquer", "clarify": "Faire répéter", "confirm": "Confirmer avec l'appelant"},
  s2d_yes="⚡ Décidé par S2D, depuis l'audio", s2d_no="S2D pas sûr → la transcription a décidé", guess="S2D supposait", bar="son seuil", no_tx="(aucune — S2D n'écrit jamais le texte)",
  heard="Transcription", m_s2d="S2D", m_total="transcription", m_conf="confiance",
  how_h="Fonctionnement", how_p="La plupart des chaînes vocales transcrivent chaque appel, puis envoient le texte à un modèle pour décider. S2D supprime l'étape du milieu pour les appels dont il est sûr.",
  steps=[("1 · Écouter", "L'audio passe dans un encodeur de parole (classe Whisper-small, CPU, fp32). Aucun texte n'est produit."),
         ("2 · Décider", "Une mini-couche de décision lit le résumé de l'encodeur et donne une décision par intention, avec une probabilité."),
         ("3 · Agir ou passer la main", "Au-dessus d'un seuil calibré, S2D agit tout de suite. En dessous, votre chaîne transcription + décision prend l'appel — rien n'est perdu.")],
  num_h="Mesuré, pas promis", num_p="Tout sur un CPU 6 cœurs. Vrais appels = MInDS-14 français (PolyAI, vrais clients bancaires), moitié rapport : 269 appels jamais vus à l'entraînement.",
  nums=[("S2D seul", "84,0 %", "de bonnes décisions, ~0,4 s par appel"), ("Cascade", "88,9 %", "de bonnes décisions · 66,5 % décidés par S2D · 2 erreurs"), ("Transcription seule", "85,9 %", "de bonnes décisions, ~11 s par appel"),
        ("Intentions d'accueil", "0 erreur", "en décision automatique sur voix, accents et formulations jamais vus (jeux de test synthétiques)")],
  num_note="Limites honnêtes : les données d'accueil de S2D sont synthétiques ; sur des formulations jamais entendues il ne décide seul que ~26 % du temps (le reste passe par la chaîne). L'anglais est en cours d'entraînement.",
  mk_h="Pas un énième LLM audio", mk_p="La parole→décision devient une catégorie. Tous les autres la construisent sur des LLM audio à milliards de paramètres, sur GPU ou dans leur cloud. S2D occupe le coin micro-modèle, CPU, auto-hébergé — et c'est le seul avec des résultats publiés en français sur de vrais appels.",
  mk_cols=["", "Ce qu'il décide", "Tourne sur", "Taille", "Français", "Calibration", "Licence"],
  mk_src="D'après la documentation ou l'article de chaque projet, novembre 2026. « Non publié » = aucun chiffre public trouvé. Signalez-nous toute info dépassée.",
  niche=[("Micro, pas méga", "~88M paramètres contre 0,6B–32B. Tient à côté de votre téléphonie, sur vos serveurs actuels."),
         ("CPU, pas GPU", "Aucun accélérateur à acheter ou louer. ~0,4 s par appel sur un CPU 6 cœurs."),
         ("Vos serveurs, pas leur cloud", "L'audio ne quitte jamais votre réseau — ce qu'exigent centres d'appels et secteurs réglementés."),
         ("Des décisions fixes, bien faites", "Le compromis : S2D répond à vos intentions, entraîné pour vous, pas à n'importe quelle question tapée à la volée.")],
  fam_h="La famille MTLM", fam=[("MTLM Router", "https://mtlm-router.intrane.fr/", "Modèles de décision pour le texte : orienter, s'abstenir, escalader."),
        ("MTLM Voice", "https://voice.intrane.fr/fr", "Transcription → décision → réponse vocale, pour agents vocaux."),
        ("MTLM S2D", None, "De la parole directement à la décision. Vous êtes ici.")],
  cta_h="Piloter S2D sur vos appels", cta_p="Nous entraînons S2D sur vos intentions et le langage de vos appelants, le mesurons sur vos enregistrements et fixons le seuil de sécurité avec vous. Auto-hébergé dès le premier jour.", cta_b="Nous contacter",
  foot="MTLM S2D · famille MTLM, par intrane.fr",
 ),
}

EXTRA_CSS = """
.tbl{overflow-x:auto;border:1px solid var(--line);border-radius:14px;background:var(--card)}
.tbl table{border-collapse:collapse;width:100%;min-width:820px;font-size:14.5px}
.tbl th,.tbl td{padding:11px 13px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
.tbl th{font-size:12.5px;text-transform:uppercase;letter-spacing:.04em;color:var(--soft)}
.tbl tr:last-child td{border-bottom:0}.tbl td:first-child{font-weight:700;white-space:nowrap}
.tbl tr.us td{background:var(--accent-soft)}.tbl tr.us td:first-child{color:var(--accent)}
.src{color:var(--soft);font-size:13.5px;margin-top:10px}
.steps{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.big{font-size:34px;font-weight:800;letter-spacing:-.02em;margin:4px 0}
.fam a.card{text-decoration:none;color:inherit}.fam .card.here{border-color:var(--accent)}
.note{color:var(--muted);font-size:15px;margin-top:16px;max-width:780px}
@media (max-width:820px){.steps{grid-template-columns:1fr}nav a.sec{display:none}}
"""


def esc(s):
    return BV.esc(s)


def page(k):
    t = T[k]
    nav = "".join(f'<a class="sec" href="{h}">{esc(l)}</a>' for h, l in t["nav"])
    msgs = "".join(f'<div class="card msg"><div class="k">{esc(a)}</div><div class="v">{esc(b)}</div><p>{esc(c)}</p></div>' for a, b, c in t["msgs"])
    steps = "".join(f'<div class="card"><h3>{esc(a)}</h3><p>{esc(b)}</p></div>' for a, b in t["steps"])
    nums = "".join(f'<div class="card"><div class="k lbl">{esc(a)}</div><div class="big">{esc(b)}</div><p>{esc(c)}</p></div>' for a, b, c in t["nums"])
    niche = "".join(f'<div class="card"><h3>{esc(a)}</h3><p>{esc(b)}</p></div>' for a, b in t["niche"])
    rows = ""
    for r in COMP[k]:
        name = esc(r[0]) if not r[1] else f'<a href="{r[1]}" rel="nofollow noopener" target="_blank">{esc(r[0])}</a>'
        rows += f'<tr class="{"us" if r[1] is None else ""}"><td>{name}</td>' + "".join(f"<td>{esc(c)}</td>" for c in r[2:]) + "</tr>"
    cols = "".join(f"<th>{esc(c)}</th>" for c in t["mk_cols"])
    fam = "".join((f'<a class="card" href="{u}"><h3>{esc(n)}</h3><p>{esc(d)}</p></a>' if u else f'<div class="card here"><h3>{esc(n)}</h3><p>{esc(d)}</p></div>') for n, u, d in t["fam"])
    proof = "".join(f"<li>{esc(p)}</li>" for p in t["proof"])
    voice = "https://voice.intrane.fr/" + ("fr" if k == "fr" else "")
    tj = json.dumps({x: t[x] for x in ("wait", "err", "lim", "pick", "a", "s2d_yes", "s2d_no", "guess", "bar", "no_tx", "heard", "m_s2d", "m_total", "m_conf")}, ensure_ascii=False)
    samples = json.dumps([{x: s[x] for x in ("id", "label", "b64")} for s in FR_SAMPLES], ensure_ascii=False)
    canon = SITE + ("/fr" if k == "fr" else "/")
    return f"""<!doctype html>
<html lang="{k}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(t['title'])}</title><meta name="description" content="{esc(t['desc'])}">
<link rel="canonical" href="{canon}"><link rel="alternate" hreflang="en" href="{SITE}/"><link rel="alternate" hreflang="fr" href="{SITE}/fr">
<meta property="og:title" content="{esc(t['title'])}"><meta property="og:description" content="{esc(t['desc'])}"><meta property="og:url" content="{canon}">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='7' fill='%233b4fd8'/><path d='M8 16h5l3-7 3 14 3-7h3' stroke='white' stroke-width='2.4' fill='none' stroke-linecap='round' stroke-linejoin='round'/></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>{BV.CSS}{EXTRA_CSS}</style>
<script defer src="https://vigie.intrane.fr/vigie.js" data-site="s2d.intrane.fr"></script>
</head><body>
<header><div class="wrap bar"><a class="brand" href="{'/fr' if k == 'fr' else '/'}"><span class="wave"><b style="height:8px"></b><b style="height:16px"></b><b style="height:20px"></b><b style="height:11px"></b></span>MTLM S2D</a>
<nav>{nav}<a href="{t['other']}">{esc(t['other_label'])}</a></nav></div></header>
<main>
<div class="wrap hero"><span class="eyebrow">{esc(t['eyebrow'])}</span><h1>{t['h1']}</h1><p class="sub">{esc(t['sub'])}</p>
<div class="ctas"><a class="btn" href="#demo">{esc(t['cta1'])}</a><a class="btn ghost" href="#pilot">{esc(t['cta2'])}</a></div>
<ul class="proof">{proof}</ul><div class="grid4">{msgs}</div></div>

<section id="demo"><div class="wrap"><h2>{esc(t['demo_h'])}</h2><p class="lead">{esc(t['demo_p'])}</p>
<div class="demo"><div><div class="chips" id="chips"></div><a href="{voice}">{esc(t['demo_more'])}</a></div>
<div class="panel" id="out"><div class="empty">{esc(t['pick'])}</div></div></div></div></section>

<section id="how"><div class="wrap"><h2>{esc(t['how_h'])}</h2><p class="lead">{esc(t['how_p'])}</p><div class="steps">{steps}</div></div></section>

<section id="numbers"><div class="wrap"><h2>{esc(t['num_h'])}</h2><p class="lead">{esc(t['num_p'])}</p><div class="grid4">{nums}</div><p class="note">{esc(t['num_note'])}</p></div></section>

<section id="market"><div class="wrap"><h2>{esc(t['mk_h'])}</h2><p class="lead">{esc(t['mk_p'])}</p>
<div class="grid4" style="margin:0 0 24px">{niche}</div>
<div class="tbl"><table><thead><tr>{cols}</tr></thead><tbody>{rows}</tbody></table></div><p class="src">{esc(t['mk_src'])}</p></div></section>

<section><div class="wrap"><h2>{esc(t['fam_h'])}</h2><div class="grid3 fam">{fam}</div></div></section>

<section id="pilot"><div class="wrap"><h2>{esc(t['cta_h'])}</h2><p class="lead">{esc(t['cta_p'])}</p><a class="btn" href="{CONTACT}" rel="noopener" target="_blank">{esc(t['cta_b'])}</a></div></section>
</main>
<footer><div class="wrap" style="padding:30px 20px;color:var(--soft);font-size:14px">{esc(t['foot'])}</div></footer>
<script>
var T={tj},S={samples},API='{API}',busy=false,out=document.getElementById('out'),chips=document.getElementById('chips');
function esc(s){{return String(s==null?'':s).replace(/[&<>"]/g,function(c){{return {{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]}})}}
function pct(x){{return x==null?'—':Math.round(x*100)+'%'}}function sec(ms){{return ms==null?'—':(ms/1000).toFixed(1)+' s'}}
chips.innerHTML=S.map(function(s){{return '<button type="button" data-id="'+s.id+'">'+esc(s.label)+'</button>'}}).join('');
chips.onclick=function(e){{var b=e.target.closest('button');if(!b||busy)return;var s=S.filter(function(x){{return x.id===b.dataset.id}})[0];go(s)}};
function go(s){{busy=true;out.innerHTML='<div class="empty">'+esc(T.wait)+'</div>';var t0=Date.now();
 fetch(API,{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify({{audio_b64:s.b64,lang:'fr',model:'small-fr-q5_1'}})}})
 .then(function(r){{if(r.status===429)throw 'lim';return r.json()}}).then(function(d){{if(!d||!d.action)throw 'err';show(d,Date.now()-t0);
  if(d.reply_audio_b64){{try{{new Audio('data:'+(d.reply_audio_type||'audio/ogg')+';base64,'+d.reply_audio_b64).play().catch(function(){{}})}}catch(e){{}}}}
  if(window.vigie)vigie('s2d_decide',{{path:d.path,action:d.action}})}})
 .catch(function(e){{out.innerHTML='<div class="empty" style="color:var(--warn)">'+esc(e==='lim'?T.lim:T.err)+'</div>'}}).then(function(){{busy=false}})}}
function show(d){{var a=d.action||'clarify',s2=d.path==='s2d';
 var h='<span class="act '+a+'">'+esc(T.a[a]||a)+(d.intent&&(a==='route'||a==='confirm')?' → '+esc(d.intent):'')+'</span>';
 h+=s2?'<div class="why s2dw"><b>'+esc(T.s2d_yes)+'</b></div>':'<div class="why s2dw">'+esc(T.s2d_no)+(d.s2d_intent?' · '+esc(T.guess)+' <b>'+esc(d.s2d_intent)+'</b> ('+pct(d.s2d_confidence)+' &lt; '+esc(T.bar)+' '+pct(d.s2d_threshold)+')':'')+'</div>';
 if(d.reply_text)h+='<div class="reply">« '+esc(d.reply_text)+' »</div>';
 h+='<span class="lbl">'+esc(T.heard)+'</span><div class="tx">'+(s2?'<em>'+esc(T.no_tx)+'</em>':esc(d.text))+'</div>';
 h+='<div class="mets"><div class="met"><b>'+sec(d.s2d_ms)+'</b><span>'+esc(T.m_s2d)+'</span></div>'+(s2?'':'<div class="met"><b>'+sec(d.stt_ms)+'</b><span>'+esc(T.m_total)+'</span></div>')+'<div class="met"><b>'+pct(s2?d.s2d_confidence:d.intent_confidence)+'</b><span>'+esc(T.m_conf)+'</span></div></div>';
 out.innerHTML=h}}
</script></body></html>"""


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for k in ("en", "fr"):
        open(os.path.join(OUT, T[k]["file"]), "w").write(page(k))
        print("wrote s2d-site/" + T[k]["file"])
    open(os.path.join(OUT, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n")
    open(os.path.join(OUT, "sitemap.xml"), "w").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{SITE}{p}</loc></url>\n" for p in ("/", "/fr")) + "</urlset>\n")
