#!/usr/bin/env python3
"""Generate the MTLM S2D site (s2d.intrane.fr): EN index.html + FR fr.html, robots, sitemap.

  python3 tools/build_s2d.py      -> writes s2d-site/

S2D = speech-to-decision: a micro model that decides what to do with a call straight from the audio,
no transcript, on a plain CPU. Part of the MTLM family (Router, Voice).

Two audiences, two looks (same facts):
  FR (fr.html)    — French SMBs (cabinet médical, syndic, comptable, mairie). Plain language, warm paper
                    look (Tri Mail family: Figtree), trade selector, free audit, tech details lower down.
  EN (index.html) — developers building voice agents. crmd family look (Instrument Serif + Geist),
                    terminal block, "drop-in before your STT", landscape table.
Both: live demo near the top, intrane.fr-style ownership band, no pricing (not decided yet).

Every number must match a measurement (memgraph project mtlm: s2d-v1-encoder, s2d-cascade,
s2d-front-gate, s2d-competitors). Competitor facts: only what their own pages/papers say; "not
published" when unknown; no disparaging wording. Trade samples (tools/s2d_samples_trades.json) are
synthetic Piper voices; some are deliberately ones S2D is NOT sure about, to show the hand-over.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "s2d-site")
SITE = "https://s2d.intrane.fr"
API = "https://api.mtlm-router.intrane.fr/demo/voice"
CONTACT = "https://www.linkedin.com/in/arancibiajav/"
SAMPLES = json.load(open(os.path.join(HERE, "s2d_samples_trades.json")))
TRADES = ["medical", "syndic", "comptable", "mairie"]
TRADE_L = {"fr": {"medical": "Cabinet médical", "syndic": "Syndic", "comptable": "Cabinet comptable", "mairie": "Mairie"},
           "en": {"medical": "Medical practice", "syndic": "Property manager", "comptable": "Accounting firm", "mairie": "Town hall"}}

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

# Shared demo strings
DEMO = {
 "fr": dict(wait="S2D écoute l'appel…", err="La démo est occupée, réessayez dans une minute.", lim="Limite de la démo atteinte — réessayez plus tard.",
            pick="Choisissez un appel.", a={"route": "Orienté", "handoff": "Passé à un humain", "block": "Bloqué", "clarify": "Faire répéter", "confirm": "À confirmer avec l'appelant"},
            yes="⚡ Décidé par S2D, depuis la voix", no="S2D n'était pas sûr → il a passé la main à la transcription",
            guess="S2D pensait", bar="son seuil", no_tx="(aucune — S2D n'écrit jamais le texte)", heard="Ce que l'appelant a dit", said="Phrase de l'appel",
            m_s2d="S2D", m_stt="transcription", m_conf="confiance", reply="Réponse jouée à l'appelant"),
 "en": dict(wait="S2D is listening…", err="The demo is busy, try again in a minute.", lim="Demo limit reached for now — try again later.",
            pick="Pick a call.", a={"route": "route", "handoff": "handoff", "block": "block", "clarify": "clarify", "confirm": "confirm"},
            yes="⚡ path: s2d — decided from the audio", no="path: chain — S2D below its bar, speech-to-text decided",
            guess="S2D guess", bar="bar", no_tx="(none — S2D never writes the text)", heard="transcript", said="what the caller says",
            m_s2d="s2d", m_stt="stt", m_conf="confidence", reply="spoken reply"),
}

FR = dict(
 title="S2D — votre standard comprend l'appel, sans transcrire",
 desc="S2D écoute l'appel et l'oriente : rendez-vous, facturation, réclamation, humain, démarchage. Un micro-modèle installé chez vous, sans cloud ni GPU. Quand il hésite, il passe la main.",
 h1="Votre standard comprend l'appel.<br><em>Sans transcrire. Sans cloud.</em>",
 sub="Toute la journée, quelqu'un décroche pour savoir si l'appel concerne un rendez-vous, une facture, une réclamation — ou un démarcheur. S2D écoute l'appelant et l'oriente au bon endroit, en moins d'une seconde, sur votre propre machine. Quand il hésite, il passe la main plutôt que de se tromper.",
 cta1="Écouter un appel", cta2="Audit gratuit",
 proof=["La voix ne sort jamais de chez vous", "Pas de GPU, pas de ChatGPT", "Les cas douteux restent pour un humain"],
 demo_h="Essayez avec un vrai appel", demo_p="Choisissez votre métier, puis un appel. C'est le vrai moteur, en direct. Les voix sont des voix de synthèse ; certains appels sont volontairement de ceux où S2D hésite, pour que vous voyiez ce qui se passe alors.",
 demo_more="Pas votre métier ? S2D apprend vos propres motifs d'appel pendant l'installation.",
 pain_h="Pourquoi vos appels méritent mieux",
 pain=[("Des heures perdues à décrocher", "Prendre l'appel, demander le motif, transférer : c'est le travail de quelqu'un, toute la journée, avant même de répondre vraiment."),
       ("Un appel mal orienté coûte cher", "Une réclamation envoyée au mauvais service, c'est un client qui rappelle, plus énervé. S2D préfère passer la main que deviner."),
       ("Vos appels restent chez vous", "Pas d'enregistrement envoyé à un service américain : S2D tourne sur votre machine. La voix de vos clients ne sort jamais.")],
 safe_h="Quand il hésite, il passe la main à un humain",
 safe_p="S2D ne décide seul que lorsqu'il est sûr — au-dessus d'un seuil réglé sur de vrais résultats. Sinon, l'appel passe à la transcription ou à une personne. Sur nos tests d'accueil (voix, accents et formulations jamais entendus), il n'a fait aucune erreur en décidant seul.",
 safe=[("Sûr", "Il oriente tout de suite", "rendez-vous, facturation, réclamation, démarchage bloqué."), ("Pas sûr", "Il passe la main", "à la transcription, qui décide plus lentement mais sans deviner."), ("« Je veux parler à quelqu'un »", "Il transfère", "à un humain, sans discuter.")],
 steps_h="Comment ça se passe",
 steps=[("1 · Audit gratuit", "Vous nous envoyez quelques appels enregistrés (ou nous en enregistrons ensemble). Nous mesurons ce que S2D en ferait, appel par appel."),
        ("2 · Installation chez vous", "S2D apprend vos motifs d'appel et s'installe sur votre machine ou votre serveur. Aucun abonnement cloud."),
        ("3 · Vous gardez la main", "Vous voyez chaque décision et réglez le seuil avec nous : plus prudent, plus d'appels passent à un humain.")],
 tech_h="Pour les techniciens", tech_p="Un encodeur de parole (~88M paramètres, classe Whisper-small) et une mini-couche de décision, sur un CPU 6 cœurs. Mesuré sur MInDS-14 français (PolyAI, vrais clients bancaires) : 269 appels jamais vus à l'entraînement.",
 nums=[("S2D seul", "84,0 %", "de bonnes décisions, ~0,4 s par appel"), ("Cascade", "88,9 %", "66,5 % décidés par S2D · 2 erreurs"), ("Transcription seule", "85,9 %", "~11 s par appel"), ("Tests d'accueil", "0 erreur", "en décision automatique (jeux synthétiques)")],
 num_note="Limites honnêtes : les données d'accueil sont synthétiques ; sur des formulations jamais entendues, S2D ne décide seul qu'environ 26 % du temps, le reste passe par la transcription. Les questions d'information pure (horaires, documents) sont son point faible actuel.",
 mk_h="Le seul à tourner sur un CPU, chez vous", mk_p="D'autres font de la « parole→décision », mais sur des LLM audio à milliards de paramètres, sur GPU ou dans leur cloud. S2D est le micro-modèle qui tient sur votre machine.",
 mk_cols=["", "Ce qu'il décide", "Tourne sur", "Taille", "Français", "Calibration", "Licence"],
 mk_src="D'après la documentation ou l'article de chaque projet, novembre 2026. « Non publié » = aucun chiffre public trouvé.",
 man_k="Pourquoi chez vous", man="Si vous ne possédez pas l'outil, c'est l'outil qui vous possède.",
 man_p="S2D fait partie d'intrane : des outils qu'on installe chez soi, qu'on peut lire et garder en marche. La voix de vos clients n'a pas à passer par le GPU de quelqu'un d'autre.",
 fam_h="La famille MTLM", fam=[("MTLM Router", "https://mtlm-router.intrane.fr/fr", "Décider sur du texte : orienter, s'abstenir, escalader."), ("MTLM Voice", "https://voice.intrane.fr/fr", "Transcription → décision → réponse vocale."), ("Tri Mail", "https://trimail.intrane.fr/", "Le même principe pour vos mails.")],
 cta_h="Audit gratuit sur vos appels", cta_p="Quelques appels enregistrés suffisent pour voir ce que S2D en ferait chez vous. On en parle 15 minutes ?", cta_b="Demander l'audit gratuit",
 nav=[("#demo", "Essayer"), ("#comment", "Comment ça se passe"), ("#tech", "Technique")], nav_cta="Audit gratuit", other="/", other_l="English",
 foot="S2D · famille MTLM, par intrane.fr",
)

EN = dict(
 title="S2D — speech-to-decision on a CPU",
 desc="S2D turns a caller's audio straight into a decision — route, handoff, block — in ~0.4 s on a plain CPU, no transcript, no GPU. A micro model you self-host. Part of MTLM.",
 kicker="MTLM · speech-to-decision · CPU-only · self-host",
 h1="Decide from the voice.<br><em>No transcript.</em>",
 sub="S2D is a micro model that listens to the caller and returns a decision — route the intent, hand off to a human, block a robocall — in ~0.4 s on a plain CPU. When it isn't sure, it says so, and your speech-to-text chain takes over.",
 cta1="Hear it decide", cta2="Pilot S2D",
 proof=["~88M params, not an audio LLM", "No GPU", "Your servers"],
 term_c="# French call, phone-band audio → decision (live endpoint, real response)",
 demo_h="Hear it <em>decide</em>.", demo_p="Real engine, live. French calls (synthetic voices, phone band) from four kinds of front desk. Some are deliberately ones S2D isn't sure about — watch it hand over instead of guessing.",
 slot_h="Drop-in <em>before</em> your STT.", slot_p="S2D is an HTTP JSON call: audio in, decision out. It is designed to sit in front of the speech-to-text step of a voice stack — Pipecat, LiveKit Agents, an Asterisk dialplan — and short-circuit the turns it is sure about.",
 slot=[("1", "Audio in", "The caller's first turn, 16 kHz mono. No text is produced."), ("2", "Decide", "Encoder + tiny head → one probability per intent, ~0.3–0.5 s on CPU."), ("3", "Act or fall through", "Above a calibrated bar: act. Below: call your STT + LLM as today. Nothing is lost.")],
 nums_h="Measured, <em>not promised</em>.", nums_p="One 6-core CPU. Real calls = MInDS-14 French (PolyAI, real bank customers), report half: 269 calls never used for training.",
 nums=[("s2d alone", "84.0%", "right · ~0.4 s/call"), ("cascade", "88.9%", "right · 66.5% decided by S2D · 2 wrong"), ("stt chain alone", "85.9%", "right · ~11 s/call"), ("front-desk gate", "0 wrong", "auto-decisions on held-out voices, accents, wordings (synthetic)")],
 num_note="Limits: front-desk training data is synthetic; on unseen wordings S2D decides alone ~26% of the time. Plain information questions are its current weak spot. English is in training.",
 mk_h="Everyone else went <em>big</em>.", mk_p="Speech-to-decision is suddenly a category — built on billion-parameter audio LLMs, on GPUs or in someone's cloud. S2D is the other corner: micro model, CPU-only, self-hosted, with published French numbers on real calls.",
 niche=[("Micro, not mega", "~88M parameters vs 0.6B–32B. Fits next to your telephony."), ("CPU, not GPU", "No accelerator to buy or rent."), ("Your servers", "Audio never leaves your network."), ("The trade-off", "Fixed intents trained for you — not any question typed at runtime.")],
 mk_cols=["", "Decides", "Runs on", "Size", "French", "Calibration", "Licence"],
 mk_src="From each project's own docs or paper, November 2026. “Not published” = no public figure found.",
 man_k="why self-host", man="If you don't own the stack, you are part of someone else's system.",
 man_p="S2D is part of intrane: infrastructure you run yourself, read the source of, and keep running. Your callers' voices shouldn't have to go through someone else's GPU.",
 fam_h="The MTLM family", fam=[("MTLM Router", "https://mtlm-router.intrane.fr/", "Decisions on text: route, abstain, escalate."), ("MTLM Voice", "https://voice.intrane.fr/", "STT → decision → spoken reply for voice agents."), ("Tri Mail", "https://trimail.intrane.fr/", "The same idea for a shared inbox (French).")],
 cta_h="Pilot S2D on <em>your</em> calls.", cta_p="We train S2D on your intents, measure it on your recordings, and set the safety bar with you. Self-hosted from day one.", cta_b="Talk to us",
 nav=[("#demo", "Demo"), ("#slot", "How it slots in"), ("#numbers", "Numbers"), ("#landscape", "Landscape")], other="/fr", other_l="Français",
 foot="S2D · part of MTLM, by intrane.fr",
)

TERM_OUT = """{
  "path": "s2d",
  "action": "route",
  "intent": "facturation",
  "s2d_confidence": 0.9915,
  "s2d_threshold": 0.9603,
  "s2d_ms": 311,
  "text": ""
}"""


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


ICON = "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='7' fill='%233b4fd8'/><path d='M8 16h5l3-7 3 14 3-7h3' stroke='white' stroke-width='2.4' fill='none' stroke-linecap='round' stroke-linejoin='round'/></svg>"


def head(k, t, fonts, css):
    canon = SITE + ("/fr" if k == "fr" else "/")
    return f"""<!doctype html>
<html lang="{k}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(t['title'])}</title><meta name="description" content="{esc(t['desc'])}">
<link rel="canonical" href="{canon}"><link rel="alternate" hreflang="en" href="{SITE}/"><link rel="alternate" hreflang="fr" href="{SITE}/fr">
<meta property="og:title" content="{esc(t['title'])}"><meta property="og:description" content="{esc(t['desc'])}"><meta property="og:url" content="{canon}">
<link rel="icon" href="{ICON}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?{fonts}&display=swap" rel="stylesheet">
<style>{css}</style>
<script defer src="https://vigie.intrane.fr/vigie.js" data-site="s2d.intrane.fr"></script>
</head>"""


def comp_table(k, cols):
    rows = ""
    for r in COMP[k]:
        name = esc(r[0]) if not r[1] else f'<a href="{r[1]}" rel="nofollow noopener" target="_blank">{esc(r[0])}</a>'
        rows += f'<tr class="{"us" if r[1] is None else ""}"><td>{name}</td>' + "".join(f"<td>{esc(c)}</td>" for c in r[2:]) + "</tr>"
    return '<div class="tbl"><table><thead><tr>' + "".join(f"<th>{esc(c)}</th>" for c in cols) + f"</tr></thead><tbody>{rows}</tbody></table></div>"


def demo_block(k):
    tabs = "".join(f'<button type="button" data-t="{tr}"{" class=on" if i == 0 else ""}>{esc(TRADE_L[k][tr])}</button>' for i, tr in enumerate(TRADES))
    return f'<div class="demo"><div><div class="tabs" id="tabs" role="tablist">{tabs}</div><div class="chips" id="chips"></div></div><div class="panel" id="out"><div class="empty">{esc(DEMO[k]["pick"])}</div></div></div>'


def demo_js(k):
    lab = "label_fr" if k == "fr" else "label_en"
    S = [{"id": s["id"], "t": s["trade"], "l": s[lab], "x": s["text"], "b64": s["b64"]} for s in SAMPLES]
    return f"""<script>
var D={json.dumps(DEMO[k], ensure_ascii=False)},S={json.dumps(S, ensure_ascii=False)},API='{API}',busy=false,cur='medical',
out=document.getElementById('out'),chips=document.getElementById('chips'),tabs=document.getElementById('tabs');
function esc(s){{return String(s==null?'':s).replace(/[&<>"]/g,function(c){{return {{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]}})}}
function pct(x){{return x==null?'—':Math.round(x*100)+'%'}}function sec(ms){{return ms==null?'—':(ms/1000).toFixed(1)+' s'}}
function draw(){{chips.innerHTML=S.filter(function(s){{return s.t===cur}}).map(function(s){{return '<button type="button" data-id="'+s.id+'"><span>'+esc(s.l)+'</span><small>« '+esc(s.x)+' »</small></button>'}}).join('')}}
tabs.onclick=function(e){{var b=e.target.closest('button');if(!b)return;cur=b.dataset.t;[].forEach.call(tabs.children,function(c){{c.className=c===b?'on':''}});draw()}};
chips.onclick=function(e){{var b=e.target.closest('button');if(!b||busy)return;go(S.filter(function(x){{return x.id===b.dataset.id}})[0])}};
function go(s){{busy=true;chips.classList.add('busy');out.innerHTML='<div class="empty pulse">'+esc(D.wait)+'</div>';
 fetch(API,{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify({{audio_b64:s.b64,lang:'fr',model:'small-fr-q5_1'}})}})
 .then(function(r){{if(r.status===429)throw 'lim';return r.json()}}).then(function(d){{if(!d||!d.action)throw 'err';show(d,s);
  if(d.reply_audio_b64){{try{{new Audio('data:'+(d.reply_audio_type||'audio/ogg')+';base64,'+d.reply_audio_b64).play().catch(function(){{}})}}catch(e){{}}}}
  if(window.vigie)vigie('s2d_decide',{{path:d.path,action:d.action,trade:s.t}})}})
 .catch(function(e){{out.innerHTML='<div class="empty warn">'+esc(e==='lim'?D.lim:D.err)+'</div>'}}).then(function(){{busy=false;chips.classList.remove('busy')}})}}
function show(d,s){{var a=d.action||'clarify',s2=d.path==='s2d';
 var h='<div class="res"><span class="act '+a+'">'+esc(D.a[a]||a)+(d.intent&&(a==='route'||a==='confirm')?' → '+esc(d.intent):'')+'</span></div>';
 h+=s2?'<div class="path yes">'+esc(D.yes)+'</div>':'<div class="path no">'+esc(D.no)+(d.s2d_intent?' · '+esc(D.guess)+' <b>'+esc(d.s2d_intent)+'</b> '+pct(d.s2d_confidence)+' &lt; '+esc(D.bar)+' '+pct(d.s2d_threshold):'')+'</div>';
 if(d.reply_text)h+='<span class="lbl">'+esc(D.reply)+'</span><div class="reply">« '+esc(d.reply_text)+' »</div>';
 h+='<span class="lbl">'+esc(D.heard)+'</span><div class="tx">'+(s2?'<em>'+esc(D.no_tx)+'</em>':esc(d.text))+'</div>';
 h+='<div class="mets"><div class="met"><b>'+sec(d.s2d_ms)+'</b><span>'+esc(D.m_s2d)+'</span></div>'+(s2?'':'<div class="met"><b>'+sec(d.stt_ms)+'</b><span>'+esc(D.m_stt)+'</span></div>')+'<div class="met"><b>'+pct(s2?d.s2d_confidence:d.intent_confidence)+'</b><span>'+esc(D.m_conf)+'</span></div></div>';
 out.innerHTML=h}}
draw();
</script>"""


DEMO_CSS = """
.demo{display:grid;grid-template-columns:1.05fr 1fr;gap:22px;align-items:start}
.tabs{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px}
.tabs button{font:inherit;font-size:14.5px;cursor:pointer;border:1px solid var(--line);background:transparent;color:var(--muted);padding:8px 14px;border-radius:999px}
.tabs button.on{background:var(--accent);border-color:var(--accent);color:var(--accent-ink)}
.chips{display:grid;gap:10px}.chips.busy{opacity:.55;pointer-events:none}
.chips button{font:inherit;text-align:left;cursor:pointer;border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:12px;padding:12px 14px;display:block;width:100%}
.chips button:hover{border-color:var(--accent)}
.chips button span{display:block;font-weight:600}.chips button span:before{content:"▶";color:var(--accent);font-size:11px;margin-right:8px}
.chips button small{display:block;color:var(--muted);font-size:13.5px;margin-top:3px;line-height:1.4}
.panel{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px;min-height:280px}
.empty{color:var(--soft);display:flex;align-items:center;justify-content:center;min-height:240px;text-align:center}.empty.warn{color:var(--warn)}
.pulse{animation:p 1.2s ease-in-out infinite}@keyframes p{50%{opacity:.45}}
.act{display:inline-block;font-weight:700;font-size:20px;padding:7px 14px;border-radius:9px;background:var(--accent-soft);color:var(--accent)}
.act.handoff{background:var(--warn-soft);color:var(--warn)}.act.block{background:var(--bad-soft);color:var(--bad)}
.path{margin:12px 0 14px;padding:9px 12px;border-radius:9px;font-size:14.5px;border-left:3px solid var(--accent);background:var(--accent-soft)}
.path.no{border-left-color:var(--soft);background:transparent;color:var(--muted)}
.lbl{display:block;font-size:12.5px;color:var(--soft);font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin-top:10px}
.reply{font-style:italic;margin:4px 0 6px}
.tx{background:var(--paper);border-radius:9px;padding:10px 12px;font-size:15px;margin:6px 0 12px}
.mets{display:flex;gap:10px;flex-wrap:wrap}.met{border:1px solid var(--line);border-radius:10px;padding:8px 12px;min-width:90px}
.met b{display:block;font-size:17px}.met span{font-size:12.5px;color:var(--soft)}
.tbl{overflow-x:auto;border:1px solid var(--line);border-radius:14px;background:var(--card)}
.tbl table{border-collapse:collapse;width:100%;min-width:820px;font-size:14px}
.tbl th,.tbl td{padding:11px 13px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
.tbl th{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--soft);font-weight:600}
.tbl tr:last-child td{border-bottom:0}.tbl td:first-child{font-weight:600;white-space:nowrap}
.tbl tr.us td{background:var(--accent-soft)}.tbl tr.us td:first-child{color:var(--accent)}
.src{color:var(--soft);font-size:13px;margin-top:10px}
@media (max-width:820px){.demo{grid-template-columns:1fr}nav a.sec{display:none}}
"""

# ---------------- FR: Tri Mail family (warm paper, Figtree) ----------------
FR_CSS = """
:root{--paper:#faf7f2;--card:#ffffff;--ink:#1c1917;--muted:#57534e;--soft:#8f877e;--line:#e7e2d9;--accent:#3b4fd8;--accent-ink:#ffffff;--accent-soft:#e9ebfb;--warn:#b45309;--warn-soft:#fdf0dc;--bad:#b3261e;--bad-soft:#fbe4e1;--band:#1c1917;--band-ink:#f5f2ed}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--paper:#171513;--card:#211e1b;--ink:#f5f2ed;--muted:#c4bdb3;--soft:#8a837a;--line:#36312c;--accent:#8e9cff;--accent-ink:#11142e;--accent-soft:#232848;--warn:#f0a952;--warn-soft:#3a2a14;--bad:#f2867c;--bad-soft:#3d1b18;--band:#0e0d0c;--band-ink:#f5f2ed}}
:root[data-theme="dark"]{--paper:#171513;--card:#211e1b;--ink:#f5f2ed;--muted:#c4bdb3;--soft:#8a837a;--line:#36312c;--accent:#8e9cff;--accent-ink:#11142e;--accent-soft:#232848;--warn:#f0a952;--warn-soft:#3a2a14;--bad:#f2867c;--bad-soft:#3d1b18;--band:#0e0d0c;--band-ink:#f5f2ed}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--paper);color:var(--ink);font-family:'Figtree',system-ui,sans-serif;line-height:1.55;font-size:17px}
a{color:var(--accent)}
.wrap{max-width:1040px;margin:0 auto;padding:0 20px}
header{border-bottom:1px solid var(--line)}
.bar{display:flex;align-items:center;justify-content:space-between;height:64px;gap:12px}
.brand{font-weight:800;font-size:20px;letter-spacing:-.02em;color:var(--ink);text-decoration:none;display:flex;align-items:center;gap:9px}
.wave{display:inline-flex;gap:3px;align-items:center;height:20px}.wave b{display:block;width:3px;border-radius:2px;background:var(--accent)}
nav{display:flex;align-items:center}nav a{color:var(--muted);text-decoration:none;font-size:15px;margin-left:18px}nav a:hover{color:var(--ink)}
.btn{display:inline-block;background:var(--accent);color:var(--accent-ink);padding:13px 22px;border-radius:10px;font-weight:600;text-decoration:none;font-size:16px}
.btn.ghost{background:transparent;color:var(--ink);border:1.5px solid var(--line)}.btn.sm{padding:8px 14px;font-size:14.5px}
.hero{padding:64px 0 50px}
h1{font-size:clamp(34px,5.4vw,56px);line-height:1.08;letter-spacing:-.03em;margin:0 0 20px;font-weight:800;max-width:820px}
h1 em{font-style:normal;color:var(--accent)}
.sub{font-size:19px;color:var(--muted);max-width:700px;margin:0 0 28px}
.ctas{display:flex;gap:12px;flex-wrap:wrap}
.proof{display:flex;gap:10px 22px;flex-wrap:wrap;margin:28px 0 0;color:var(--muted);font-size:15px;padding:0;list-style:none}
.proof li:before{content:"✓";color:var(--accent);font-weight:700;margin-right:8px}
section{padding:58px 0;border-top:1px solid var(--line)}
h2{font-size:clamp(26px,3.4vw,34px);letter-spacing:-.02em;margin:0 0 12px;line-height:1.15}
.lead{color:var(--muted);max-width:700px;margin:0 0 26px}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:22px}
.card h3{margin:0 0 8px;font-size:18px}.card p{margin:0;color:var(--muted);font-size:16px}
.card .k{font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--accent)}
.big{font-size:32px;font-weight:800;letter-spacing:-.02em;margin:4px 0}
.note{color:var(--muted);font-size:15px;margin-top:16px;max-width:780px}
.more{color:var(--muted);font-size:15px;margin-top:14px}
.band{background:var(--band);color:var(--band-ink);border-top:0}
.band .k{font-size:13px;text-transform:uppercase;letter-spacing:.08em;opacity:.6}
.band blockquote{margin:10px 0 14px;font-size:clamp(24px,3.4vw,34px);font-weight:800;letter-spacing:-.02em;line-height:1.2;max-width:820px}
.band p{opacity:.8;max-width:700px;margin:0}
.fam a.card{text-decoration:none;color:inherit}.fam a.card:hover{border-color:var(--accent)}
footer{border-top:1px solid var(--line);padding:30px 0;color:var(--soft);font-size:14px}
@media (max-width:820px){.grid3,.grid4{grid-template-columns:1fr}.hero{padding-top:40px}}
"""


def page_fr():
    t, k = FR, "fr"
    nav = "".join(f'<a class="sec" href="{h}">{esc(l)}</a>' for h, l in t["nav"])
    card3 = lambda xs: "".join(f'<div class="card"><h3>{esc(a)}</h3><p>{esc(b)}</p></div>' for a, b in xs)
    safe = "".join(f'<div class="card"><div class="k">{esc(a)}</div><h3 style="margin-top:6px">{esc(b)}</h3><p>{esc(c)}</p></div>' for a, b, c in t["safe"])
    nums = "".join(f'<div class="card"><div class="k">{esc(a)}</div><div class="big">{esc(b)}</div><p>{esc(c)}</p></div>' for a, b, c in t["nums"])
    fam = "".join(f'<a class="card" href="{u}"><h3>{esc(n)}</h3><p>{esc(d)}</p></a>' for n, u, d in t["fam"])
    proof = "".join(f"<li>{esc(p)}</li>" for p in t["proof"])
    return head(k, t, "family=Figtree:wght@400;600;700;800", FR_CSS + DEMO_CSS) + f"""<body>
<header><div class="wrap bar"><a class="brand" href="/fr"><span class="wave"><b style="height:8px"></b><b style="height:16px"></b><b style="height:20px"></b><b style="height:11px"></b></span>S2D</a>
<nav>{nav}<a href="{t['other']}">{esc(t['other_l'])}</a><a class="btn sm" style="margin-left:18px;color:var(--accent-ink)" href="#audit">{esc(t['nav_cta'])}</a></nav></div></header>
<main>
<div class="wrap hero"><h1>{t['h1']}</h1><p class="sub">{esc(t['sub'])}</p>
<div class="ctas"><a class="btn" href="#demo">{esc(t['cta1'])}</a><a class="btn ghost" href="#audit">{esc(t['cta2'])}</a></div><ul class="proof">{proof}</ul></div>
<section id="demo"><div class="wrap"><h2>{esc(t['demo_h'])}</h2><p class="lead">{esc(t['demo_p'])}</p>{demo_block(k)}<p class="more">{esc(t['demo_more'])}</p></div></section>
<section><div class="wrap"><h2>{esc(t['pain_h'])}</h2><div class="grid3">{card3(t['pain'])}</div></div></section>
<section><div class="wrap"><h2>{esc(t['safe_h'])}</h2><p class="lead">{esc(t['safe_p'])}</p><div class="grid3">{safe}</div></div></section>
<section id="comment"><div class="wrap"><h2>{esc(t['steps_h'])}</h2><div class="grid3">{card3(t['steps'])}</div></div></section>
<section class="band"><div class="wrap"><div class="k">{esc(t['man_k'])}</div><blockquote>{esc(t['man'])}</blockquote><p>{esc(t['man_p'])}</p></div></section>
<section id="tech"><div class="wrap"><h2>{esc(t['tech_h'])}</h2><p class="lead">{esc(t['tech_p'])}</p><div class="grid4">{nums}</div><p class="note">{esc(t['num_note'])}</p>
<h3 style="margin:40px 0 8px;font-size:22px">{esc(t['mk_h'])}</h3><p class="lead">{esc(t['mk_p'])}</p>{comp_table(k, t['mk_cols'])}<p class="src">{esc(t['mk_src'])}</p></div></section>
<section><div class="wrap"><h2>{esc(t['fam_h'])}</h2><div class="grid3 fam">{fam}</div></div></section>
<section id="audit"><div class="wrap"><h2>{esc(t['cta_h'])}</h2><p class="lead">{esc(t['cta_p'])}</p><a class="btn" href="{CONTACT}" rel="noopener" target="_blank" data-track="s2d_audit">{esc(t['cta_b'])}</a></div></section>
</main><footer><div class="wrap">{esc(t['foot'])}</div></footer>
{demo_js(k)}</body></html>"""


# ---------------- EN: crmd family (ink, Instrument Serif + Geist) ----------------
EN_CSS = """
:root{--paper:#f4efe6;--card:#fffdf8;--ink:#14120f;--muted:#5b554c;--soft:#8c857a;--line:#e2dacb;--accent:#b7791f;--accent-ink:#14120f;--accent-soft:#f6e7c9;--warn:#a85b00;--warn-soft:#fbefdd;--bad:#b3261e;--bad-soft:#fbe4e1;--term:#14120f;--term-ink:#ede6d9;--ok:#2f7d32;--band:#14120f;--band-ink:#ede6d9}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--paper:#0d0c0a;--card:#14120f;--ink:#ede6d9;--muted:rgba(237,230,217,.68);--soft:rgba(237,230,217,.45);--line:rgba(237,230,217,.12);--accent:#f2b33d;--accent-ink:#0d0c0a;--accent-soft:rgba(242,179,61,.12);--warn:#f2b33d;--warn-soft:rgba(242,179,61,.12);--bad:#e98a7a;--bad-soft:rgba(233,138,122,.13);--term:#1b1814;--term-ink:#ede6d9;--ok:#8fd18a;--band:#1b1814;--band-ink:#ede6d9}}
:root[data-theme="dark"]{--paper:#0d0c0a;--card:#14120f;--ink:#ede6d9;--muted:rgba(237,230,217,.68);--soft:rgba(237,230,217,.45);--line:rgba(237,230,217,.12);--accent:#f2b33d;--accent-ink:#0d0c0a;--accent-soft:rgba(242,179,61,.12);--warn:#f2b33d;--warn-soft:rgba(242,179,61,.12);--bad:#e98a7a;--bad-soft:rgba(233,138,122,.13);--term:#1b1814;--term-ink:#ede6d9;--ok:#8fd18a;--band:#1b1814;--band-ink:#ede6d9}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--paper);color:var(--ink);font-family:'Geist',system-ui,sans-serif;font-size:16.5px;line-height:1.6;-webkit-font-smoothing:antialiased}
a{color:var(--accent)}code,pre,.mono{font-family:'Geist Mono',ui-monospace,Menlo,monospace}
.wrap{max-width:1120px;margin:0 auto;padding:0 24px}
header{border-bottom:1px solid var(--line)}
.bar{display:flex;align-items:center;justify-content:space-between;height:64px;gap:12px}
.brand{font-family:'Instrument Serif',Georgia,serif;font-size:27px;color:var(--ink);text-decoration:none;display:flex;align-items:center;gap:9px}
.wave{display:inline-flex;gap:3px;align-items:center;height:20px}.wave b{display:block;width:3px;border-radius:2px;background:var(--accent)}
nav{display:flex;align-items:center}nav a{color:var(--muted);text-decoration:none;font-size:14.5px;margin-left:20px}nav a:hover{color:var(--ink)}
.btn{display:inline-block;background:var(--accent);color:var(--accent-ink);padding:12px 20px;border-radius:999px;font-weight:600;text-decoration:none;font-size:15px}
.btn.ghost{background:transparent;color:var(--ink);border:1px solid var(--line)}
h1,h2,.serif{font-family:'Instrument Serif',Georgia,serif;font-weight:400;letter-spacing:-.01em}
h1{font-size:clamp(46px,7.4vw,88px);line-height:.98;margin:14px 0 22px}
h1 em,h2 em{color:var(--accent)}
h2{font-size:clamp(34px,4.6vw,52px);line-height:1.04;margin:0 0 14px}
.kick{font-family:'Geist Mono',monospace;font-size:12.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--soft)}
.hero{display:grid;grid-template-columns:1.05fr 1fr;gap:40px;align-items:center;padding:70px 0 56px}
.sub{font-size:18px;color:var(--muted);margin:0 0 26px;max-width:560px}
.ctas{display:flex;gap:12px;flex-wrap:wrap}
.proof{display:flex;gap:8px 20px;flex-wrap:wrap;margin:24px 0 0;padding:0;list-style:none;font-family:'Geist Mono',monospace;font-size:13px;color:var(--muted)}
.proof li:before{content:"→ ";color:var(--accent)}
.term{background:var(--term);color:var(--term-ink);border-radius:14px;border:1px solid var(--line);overflow:hidden;min-width:0}
.term .tb{display:flex;gap:6px;padding:11px 14px;border-bottom:1px solid rgba(237,230,217,.1)}.term .tb i{width:10px;height:10px;border-radius:50%;background:rgba(237,230,217,.2)}
.term pre{margin:0;padding:16px 18px;font-size:13px;line-height:1.6;overflow-x:auto;white-space:pre}
.term .c{color:rgba(237,230,217,.45)}.term .p{color:#f2b33d}.term .o{color:#8fd18a}
section{padding:72px 0;border-top:1px solid var(--line)}
.lead{color:var(--muted);max-width:680px;margin:0 0 30px;font-size:17px}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:22px}
.card h3{margin:0 0 6px;font-size:17px;font-weight:600}.card p{margin:0;color:var(--muted);font-size:15px}
.card .n{font-family:'Geist Mono',monospace;color:var(--accent);font-size:13px}
.card .k{font-family:'Geist Mono',monospace;font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--soft)}
.big{font-family:'Instrument Serif',Georgia,serif;font-size:46px;line-height:1;margin:8px 0 6px;color:var(--ink)}
.note{color:var(--muted);font-size:14.5px;margin-top:16px;max-width:780px}
.band{background:var(--band);color:var(--band-ink);border-top:0}
.band .kick{color:rgba(237,230,217,.5)}
.band blockquote{font-family:'Instrument Serif',Georgia,serif;font-size:clamp(32px,4.4vw,50px);line-height:1.08;margin:12px 0 16px;max-width:900px}
.band p{color:rgba(237,230,217,.72);max-width:680px;margin:0}
.fam a.card{text-decoration:none;color:inherit}.fam a.card:hover{border-color:var(--accent)}
footer{border-top:1px solid var(--line);padding:30px 0;color:var(--soft);font-size:14px}
@media (max-width:860px){.hero{grid-template-columns:1fr;padding-top:40px}.grid3,.grid4{grid-template-columns:1fr}}
"""


def page_en():
    t, k = EN, "en"
    nav = "".join(f'<a class="sec" href="{h}">{esc(l)}</a>' for h, l in t["nav"])
    slot = "".join(f'<div class="card"><div class="n">{esc(n)} /</div><h3>{esc(a)}</h3><p>{esc(b)}</p></div>' for n, a, b in t["slot"])
    nums = "".join(f'<div class="card"><div class="k">{esc(a)}</div><div class="big">{esc(b)}</div><p>{esc(c)}</p></div>' for a, b, c in t["nums"])
    niche = "".join(f'<div class="card"><h3>{esc(a)}</h3><p>{esc(b)}</p></div>' for a, b in t["niche"])
    fam = "".join(f'<a class="card" href="{u}"><h3>{esc(n)}</h3><p>{esc(d)}</p></a>' for n, u, d in t["fam"])
    proof = "".join(f"<li>{esc(p)}</li>" for p in t["proof"])
    term = (f'<span class="c">{esc(t["term_c"])}</span>\n<span class="p">$</span> curl -s {API} \\\n'
            "    -H 'content-type: application/json' \\\n"
            "    -d '{\"lang\":\"fr\",\"model\":\"small-fr-q5_1\",\"audio_b64\":\"…\"}'\n"
            f'<span class="o">{esc(TERM_OUT)}</span>\n<span class="c"># 0.3 s on CPU · no transcript written</span>')
    return head(k, t, "family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&family=Instrument+Serif:ital@0;1", EN_CSS + DEMO_CSS) + f"""<body>
<header><div class="wrap bar"><a class="brand" href="/"><span class="wave"><b style="height:8px"></b><b style="height:16px"></b><b style="height:20px"></b><b style="height:11px"></b></span>S2D</a>
<nav>{nav}<a href="{t['other']}">{esc(t['other_l'])}</a></nav></div></header>
<main>
<div class="wrap hero"><div><div class="kick">{esc(t['kicker'])}</div><h1>{t['h1']}</h1><p class="sub">{esc(t['sub'])}</p>
<div class="ctas"><a class="btn" href="#demo">{esc(t['cta1'])}</a><a class="btn ghost" href="#pilot">{esc(t['cta2'])}</a></div><ul class="proof">{proof}</ul></div>
<div class="term"><div class="tb"><i></i><i></i><i></i></div><pre>{term}</pre></div></div>
<section id="demo"><div class="wrap"><h2>{t['demo_h']}</h2><p class="lead">{esc(t['demo_p'])}</p>{demo_block(k)}</div></section>
<section id="slot"><div class="wrap"><h2>{t['slot_h']}</h2><p class="lead">{esc(t['slot_p'])}</p><div class="grid3">{slot}</div></div></section>
<section id="numbers"><div class="wrap"><h2>{t['nums_h']}</h2><p class="lead">{esc(t['nums_p'])}</p><div class="grid4">{nums}</div><p class="note">{esc(t['num_note'])}</p></div></section>
<section id="landscape"><div class="wrap"><h2>{t['mk_h']}</h2><p class="lead">{esc(t['mk_p'])}</p><div class="grid4" style="margin-bottom:22px">{niche}</div>{comp_table(k, t['mk_cols'])}<p style="color:var(--soft);font-size:13px;margin-top:10px">{esc(t['mk_src'])}</p></div></section>
<section class="band"><div class="wrap"><div class="kick">{esc(t['man_k'])}</div><blockquote>{esc(t['man'])}</blockquote><p>{esc(t['man_p'])}</p></div></section>
<section><div class="wrap"><h2>{esc(t['fam_h'])}</h2><div class="grid3 fam">{fam}</div></div></section>
<section id="pilot"><div class="wrap"><h2>{t['cta_h']}</h2><p class="lead">{esc(t['cta_p'])}</p><a class="btn" href="{CONTACT}" rel="noopener" target="_blank" data-track="s2d_pilot">{esc(t['cta_b'])}</a></div></section>
</main><footer><div class="wrap">{esc(t['foot'])}</div></footer>
{demo_js(k)}</body></html>"""


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "index.html"), "w").write(page_en())
    open(os.path.join(OUT, "fr.html"), "w").write(page_fr())
    open(os.path.join(OUT, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n")
    open(os.path.join(OUT, "sitemap.xml"), "w").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{SITE}{p}</loc></url>\n" for p in ("/", "/fr")) + "</urlset>\n")
    print("wrote s2d-site/index.html, fr.html, robots.txt, sitemap.xml")
