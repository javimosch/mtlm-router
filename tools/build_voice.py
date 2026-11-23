#!/usr/bin/env python3
"""Generate the MTLM Voice site (voice.intrane.fr): EN index.html + FR fr.html, robots, sitemap.

  python3 tools/build_voice.py      -> writes voice-site/

Audience: teams building voice agents / call automation. The page demos the decision step that
sits after speech-to-text: robocall gate + caller intent (incl. "wants a human"). The live demo calls
the meter (api.mtlm-router.intrane.fr/demo/voice), which forwards to the voice server on rbm21.
Samples (synthetic Piper voices, 8 kHz phone band, opus) are embedded from tools/voice_samples.json.
Keep claims measured: untuned engine ~1-2 s per decision on a quiet 6-core CPU; tuned per-client
decision models ~15-20 ms. Never name a partner company here without their OK.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "voice-site")
SITE = "https://voice.intrane.fr"
API = "https://api.mtlm-router.intrane.fr/demo/voice"
SAMPLES = json.load(open(os.path.join(HERE, "voice_samples.json")))

EXAMPLE_REQ = '{"lang": "en", "text": "Can I just talk to a real person please?"}'
EXAMPLE_RES = '''{
  "action": "handoff",
  "intent": "human",
  "intent_confidence": 1.0,
  "intent_probabilities": {"booking": 0.0, "change": 0.0, "billing": 0.0,
                           "complaint": 0.0, "info": 0.0, "human": 1.0},
  "p_robocall": 0.37
}'''

T = {
 "en": dict(
  lang="en", file="index.html", path="/", other="/fr", other_label="Français",
  title="MTLM Voice — the decision layer for voice agents",
  desc="After speech-to-text, MTLM decides what to do with the call: route the intent, hand off to a human, or block a robocall. Small models on a plain CPU, on your own servers.",
  nav_demo="Demo", nav_how="How it plugs in", nav_price="Pricing", nav_cta="Become a design partner",
  eyebrow="The decision layer for voice agents · Bring your own STT",
  h1="Your agent hears the caller.<br>MTLM decides what to do.",
  sub="After speech-to-text, every turn needs a decision: what does the caller want, should a human take over, is this a robocall? MTLM answers with small models on a plain CPU — no LLM call per turn, no GPU, on your own servers.",
  cta1="Try it with a call", cta2="Become a design partner",
  proof=["Not a speech model: it works after yours", "French and English", "No GPU"],
  msgs=[("Cheaper", "No LLM call on routine turns", "Routing, handoff and robocall decisions come from small models, not a large model per turn."),
        ("Faster", "~15–20 ms", "per decision once tuned to your intents, on a plain CPU."),
        ("Yours", "Your servers", "Runs in your cloud or on-prem. Transcripts never leave your network."),
        ("Safe", "0 wrong auto-routes", "on 269 real French bank calls (MInDS-14), at strict confidence: below it, it asks the caller to confirm instead of guessing.")],
  pain_h="Every turn of a call costs you a decision",
  pain=[("An LLM call per turn", "Sending each transcript to a large model to pick the next step adds cost on every turn, on every call."),
        ("Latency the caller hears", "Hundreds of milliseconds to seconds per turn, on top of speech-to-text and speech synthesis. Callers notice the silence."),
        ("Handoff at the wrong moment", "Angry callers stuck in a loop, or routine calls sent to an operator. Both cost you: churn on one side, staff time on the other.")],
  demo_h="Try it with a call",
  demo_p="Play a sample call, record your own (max 30 s), or paste a transcript. Calls go to S2D first, which decides from the audio alone when it is sure; otherwise the audio is transcribed by a small Whisper model (a French-tuned Whisper small for French calls) and MTLM makes the decision and plays a pre-recorded reply (French voice: Brindille, a 94K-parameter TTS). Everything runs on one shared 6-core CPU, no GPU.",
  l_lang="Call language", l_model="Speech-to-text", l_samples="Sample calls", rec="Record a call", stop="Stop",
  or_paste="Or paste a transcript", ph="e.g. Hi, I'd like to move my appointment to next week", go="Decide",
  wait="Transcribing and deciding…", wait_txt="Deciding…",
  a_route="Route", a_handoff="Hand off to a human", a_block="Block — robocall / telemarketing", a_clarify="Ask the caller again", a_confirm="Ask the caller to confirm", why_confirm="likely intent, below the strict threshold", reply_l="Spoken reply",
  why_route="confident about the intent", why_handoff="the caller wants a person, or is upset", why_block="not a real customer request", why_clarify="not sure enough to act alone",
  m_audio="audio", m_stt="speech-to-text", m_dec="decision", m_conf="confidence", m_robo="robocall score", p_s2d="S2D · decided from the audio", p_s2d_why="no transcript needed: S2D was sure enough on its own", m_s2d="S2D", no_tx="(none — S2D never writes the text)", s2d_guess="S2D guess, below its threshold — full chain used:", s2d_fb="S2D unsure → speech-to-text", s2d_fbw="S2D listened first and guessed", s2d_fbw2="not sure enough to act alone, so the speech-to-text chain decided", s2d_en="S2D was not available for this call — the speech-to-text chain decided",
  heard="Transcript", json_l="Raw JSON response",
  lim="Demo limit reached — try again in an hour.", err="The demo is busy or unreachable — try again in a moment.",
  mic_no="Microphone not available — use a sample call or paste a transcript.", too_long="Recording stopped at 30 seconds.",
  demo_note="Demo calls are processed then deleted: nothing is stored. Sample voices are synthetic. Live timings vary: the demo box is a shared CPU running other jobs.",
  s2d_tag="Live in the demo · French & English", s2d_h="S2D: speech straight to decision",
  s2d_p="Today the call goes through speech-to-text, then MTLM decides. S2D decides from the audio itself — it now runs first on French and English calls in the demo above: no transcript to generate, so the slowest step of the chain disappears.",
  s2d_pts=[("No transcription step", "Writing out the transcript is what makes speech-to-text slow on a CPU. S2D listens and decides, it never writes the text."),
           ("Already tested on real calls", "Early prototype on 269 real French bank calls (MInDS-14): 84% right from the audio alone, in about 0.4 s per call, against about 11 s for transcription plus decision on the same 6-core CPU. English: 93% right on 904 real bank calls, and 0 wrong among the 31% it decides alone."),
           ("Safer together", "When S2D is not sure, the call falls back to the full speech-to-text chain shown above. On the same calls, S2D first + fallback got 89% right, with two thirds of calls decided without asking the caller again.")],
  s2d_cta="Pilot S2D on your calls", s2d_more="See S2D →", s2d_site="https://s2d.intrane.fr/",
  how_h="Where it plugs in",
  how_p="MTLM sits between your speech-to-text and the rest of your agent. Keep your STT, keep your LLM for the turns that really need one.",
  flow=[("Caller", "phone, app, web"), ("Your speech-to-text", "any model or API"), ("MTLM decision", "route · handoff · block"), ("Your agent", "LLM only when needed")],
  req_l="Request", res_l="Response",
  dec_h="What it decides",
  dec=[("Caller intent", "Booking, change or cancellation, billing, complaint, information — or your own list of intents."),
       ("Human handoff", "The caller asks for a person, or is angry or in distress: route to an operator before it escalates."),
       ("Robocalls and telemarketing", "Sales pitches and prize robocalls are blocked before your agent spends a turn on them."),
       ("Unsure? It says so", "Every answer comes with a confidence. Below your threshold, the agent asks again or a human takes over — no confident guess."),
       ("Your own questions", "Yes/no questions, a choice between options, or a 1–4 score: urgency, satisfaction, end of call, anything your flow needs."),
       ("Your servers", "Runs on a plain CPU, in your cloud account or on-prem. Transcripts never leave your network.")],
  speed_h="Speed, measured",
  speed=[("Tuned to your intents", "~15–20 ms", "a small decision model trained on your intents and call logs"),
         ("Untuned engine (this demo)", "~1–2 s", "per decision on a quiet 6-core CPU; slower when the box is busy"),
         ("Speech-to-text (this demo)", "~1–4 s", "Whisper base for a 10-second call, same CPU — your STT replaces it")],
  price_h="Pricing",
  price=[("Design partner pilot", "Free", "For the first 3 teams: we tune MTLM on your intents and anonymized transcripts, and measure it against your current setup. In exchange: feedback and a short case study."),
         ("Custom decision model", "€149", "One-off. Trained on your intents, delivered as a small file that runs on your own CPU servers."),
         ("On-prem licence", "On request", "Volume, several languages or call flows, support and updates.")],
  form_h="Become a design partner",
  f_email="you@company.com", f_company="Company", f_use="What does your voice agent do?", f_vol="Calls per month (approx.)", f_stack="Current STT and LLM (optional)",
  f_btn="Apply as a design partner", f_note="Used only to reply to you. No newsletter.",
  f_sending="Sending…", f_ok="Thanks — I will get back to you within 48 h.", f_ko="Could not send — please try again shortly.",
  faq_h="Frequently asked questions",
  faq=[("Which speech-to-text does it work with?", "Any. MTLM takes text, so it works after Whisper, your own model or any STT API. The demo uses Whisper tiny/base on CPU only to show the full chain."),
       ("Which languages?", "French and English are tested in this demo. Other languages are possible; we test them on your calls before promising anything."),
       ("How accurate is it?", "On our test calls, every automatic decision was correct; unclear calls went to “ask again” or to a human instead. Your calls will differ — that is what the pilot measures, on your own transcripts."),
       ("Does it need a GPU?", "No. Everything runs on a plain CPU. A tuned decision model answers in ~15–20 ms."),
       ("Where does my data go?", "Nowhere: in production MTLM runs on your servers. In this demo, audio and transcripts are processed then deleted."),
       ("How long to tune it?", "A first tuned model takes days, not weeks: your intent list plus a few hundred anonymized transcripts is enough to start.")],
  who="MTLM is built by Javier Leandro Arancibia, based in Savoie, France.", tech="Engine and docs:",
 ),
 "fr": dict(
  lang="fr", file="fr.html", path="/fr", other="/", other_label="English",
  title="MTLM Voice — la couche de décision des agents vocaux",
  desc="Après la transcription, MTLM décide quoi faire de l'appel : orienter la demande, passer la main à un humain ou bloquer un robot. De petits modèles sur un simple CPU, sur vos serveurs.",
  nav_demo="Démo", nav_how="Intégration", nav_price="Tarifs", nav_cta="Devenir partenaire pilote",
  eyebrow="La couche de décision des agents vocaux · Gardez votre STT",
  h1="Votre agent entend l'appelant.<br>MTLM décide quoi faire.",
  sub="Après la transcription, chaque tour de parole demande une décision : que veut l'appelant, faut-il passer la main à un humain, est-ce un robot ? MTLM répond avec de petits modèles sur un simple CPU — sans appel à un LLM à chaque tour, sans GPU, sur vos serveurs.",
  cta1="Essayer avec un appel", cta2="Devenir partenaire pilote",
  proof=["Pas un modèle de transcription : il se place après le vôtre", "Français et anglais", "Sans GPU"],
  msgs=[("Moins cher", "Pas d'appel LLM sur les tours simples", "Orientation, transfert et détection de robots viennent de petits modèles, pas d'un gros modèle à chaque tour."),
        ("Plus rapide", "~15–20 ms", "par décision une fois adapté à vos intentions, sur un simple CPU."),
        ("Chez vous", "Vos serveurs", "Dans votre cloud ou sur site. Les transcriptions ne quittent pas votre réseau."),
        ("Sûr", "0 orientation automatique fausse", "sur 269 vrais appels bancaires en français (MInDS-14), en confiance stricte : en dessous, il fait confirmer l'appelant au lieu de deviner.")],
  pain_h="Chaque tour de parole vous coûte une décision",
  pain=[("Un appel LLM par tour", "Envoyer chaque transcription à un gros modèle pour choisir l'étape suivante ajoute un coût à chaque tour, sur chaque appel."),
        ("Une latence que l'appelant entend", "Des centaines de millisecondes à plusieurs secondes par tour, en plus de la transcription et de la synthèse vocale. Les appelants entendent le silence."),
        ("Le transfert au mauvais moment", "Des clients en colère coincés dans une boucle, ou des appels simples envoyés à un conseiller. Les deux coûtent cher.")],
  demo_h="Essayer avec un appel",
  demo_p="Écoutez un appel d'exemple, enregistrez le vôtre (30 s max) ou collez une transcription. Les appels passent d'abord par S2D, qui décide à partir de l'audio seul quand il est sûr ; sinon l'audio est transcrit par un petit modèle Whisper (un Whisper small affiné en français) et MTLM prend la décision et joue une réponse préenregistrée (voix : Brindille, une synthèse vocale de 94 000 paramètres). Tout tourne sur un seul CPU 6 cœurs partagé, sans GPU.",
  l_lang="Langue de l'appel", l_model="Transcription", l_samples="Appels d'exemple", rec="Enregistrer un appel", stop="Arrêter",
  or_paste="Ou collez une transcription", ph="ex. Bonjour, je voudrais décaler mon rendez-vous à la semaine prochaine", go="Décider",
  wait="Transcription et décision…", wait_txt="Décision…",
  a_route="Orienter", a_handoff="Passer à un humain", a_block="Bloquer — robot / démarchage", a_clarify="Redemander à l'appelant", a_confirm="Faire confirmer l'appelant", why_confirm="intention probable, sous le seuil strict", reply_l="Réponse parlée",
  why_route="intention identifiée avec confiance", why_handoff="l'appelant veut une personne, ou est mécontent", why_block="pas une vraie demande client", why_clarify="pas assez sûr pour agir seul",
  m_audio="audio", m_stt="transcription", m_dec="décision", m_conf="confiance", m_robo="score robot", p_s2d="S2D · décidé depuis l'audio", p_s2d_why="pas besoin de transcription : S2D était assez sûr seul", m_s2d="S2D", no_tx="(aucune — S2D n'écrit jamais le texte)", s2d_guess="Supposition de S2D, sous son seuil — chaîne complète utilisée :", s2d_fb="S2D pas sûr → transcription", s2d_fbw="S2D a écouté d'abord et a supposé", s2d_fbw2="pas assez sûr pour agir seul, la chaîne transcription a donc décidé", s2d_en="S2D n'était pas disponible pour cet appel — la chaîne transcription a décidé",
  heard="Transcription", json_l="Réponse JSON brute",
  lim="Limite de la démo atteinte — réessayez dans une heure.", err="La démo est occupée ou injoignable — réessayez dans un instant.",
  mic_no="Micro indisponible — utilisez un appel d'exemple ou collez une transcription.", too_long="Enregistrement arrêté à 30 secondes.",
  demo_note="Les appels de la démo sont traités puis supprimés : rien n'est conservé. Les voix des exemples sont synthétiques. Les temps varient : la machine de démo est un CPU partagé avec d'autres tâches.",
  s2d_tag="En direct dans la démo · français et anglais", s2d_h="S2D : de la voix directement à la décision",
  s2d_p="Aujourd'hui l'appel passe par la transcription, puis MTLM décide. S2D décide à partir de l'audio lui-même — il tourne désormais en premier sur les appels français et anglais de la démo ci-dessus : plus de texte à générer, donc l'étape la plus lente de la chaîne disparaît.",
  s2d_pts=[("Plus d'étape de transcription", "C'est l'écriture du texte qui rend la transcription lente sur un CPU. S2D écoute et décide, il n'écrit jamais le texte."),
           ("Déjà testé sur de vrais appels", "Premier prototype sur 269 vrais appels bancaires en français (MInDS-14) : 84 % de bonnes décisions à partir de l'audio seul, en 0,4 s environ par appel, contre environ 11 s pour transcription + décision sur le même CPU 6 cœurs. Anglais : 93 % de bonnes décisions sur 904 vrais appels bancaires, 0 erreur parmi les 31 % décidés seuls."),
           ("Plus sûr à deux", "Quand S2D n'est pas sûr, l'appel repasse par la chaîne complète avec transcription ci-dessus. Sur les mêmes appels, S2D d'abord + repli : 89 % de bonnes décisions, et deux tiers des appels décidés sans redemander à l'appelant.")],
  s2d_cta="Tester S2D sur vos appels", s2d_more="Découvrir S2D →", s2d_site="https://s2d.intrane.fr/fr",
  how_h="Où ça se branche",
  how_p="MTLM se place entre votre transcription et le reste de votre agent. Gardez votre STT, gardez votre LLM pour les tours qui en ont vraiment besoin.",
  flow=[("Appelant", "téléphone, appli, web"), ("Votre transcription", "n'importe quel modèle ou API"), ("Décision MTLM", "orienter · transférer · bloquer"), ("Votre agent", "LLM seulement si nécessaire")],
  req_l="Requête", res_l="Réponse",
  dec_h="Ce qu'il décide",
  dec=[("L'intention de l'appelant", "Rendez-vous, modification ou annulation, facturation, réclamation, information — ou votre propre liste."),
       ("Le passage à un humain", "L'appelant demande une personne, ou est en colère ou en détresse : transfert à un conseiller avant que ça dégénère."),
       ("Robots et démarchage", "Les démarchages et les robots « vous avez gagné » sont bloqués avant que votre agent y passe un tour."),
       ("Pas sûr ? Il le dit", "Chaque réponse a une confiance. Sous votre seuil, l'agent redemande ou un humain reprend — pas de réponse au hasard."),
       ("Vos propres questions", "Questions oui/non, choix entre options, ou score de 1 à 4 : urgence, satisfaction, fin d'appel, ce dont votre parcours a besoin."),
       ("Vos serveurs", "Tourne sur un simple CPU, dans votre cloud ou chez vous. Les transcriptions ne quittent pas votre réseau.")],
  speed_h="La vitesse, mesurée",
  speed=[("Adapté à vos intentions", "~15–20 ms", "un petit modèle de décision entraîné sur vos intentions et vos appels"),
         ("Moteur générique (cette démo)", "~1–2 s", "par décision sur un CPU 6 cœurs au repos ; plus lent quand la machine est chargée"),
         ("Transcription (cette démo)", "~1–4 s", "Whisper base pour un appel de 10 secondes, même CPU — votre STT la remplace")],
  price_h="Tarifs",
  price=[("Pilote partenaire", "Gratuit", "Pour les 3 premières équipes : nous adaptons MTLM à vos intentions et à des transcriptions anonymisées, et le mesurons face à votre solution actuelle. En échange : vos retours et une courte étude de cas."),
         ("Modèle de décision sur mesure", "149 €", "Paiement unique. Entraîné sur vos intentions, livré sous forme d'un petit fichier qui tourne sur vos serveurs CPU."),
         ("Licence sur site", "Sur devis", "Volume, plusieurs langues ou parcours d'appel, support et mises à jour.")],
  form_h="Devenir partenaire pilote",
  f_email="vous@entreprise.fr", f_company="Entreprise", f_use="Que fait votre agent vocal ?", f_vol="Appels par mois (environ)", f_stack="STT et LLM actuels (facultatif)",
  f_btn="Candidater comme partenaire pilote", f_note="Utilisé uniquement pour vous répondre. Pas de newsletter.",
  f_sending="Envoi…", f_ok="Merci — je reviens vers vous sous 48 h.", f_ko="Envoi impossible — réessayez dans un instant.",
  faq_h="Questions fréquentes",
  faq=[("Avec quelle transcription ça marche ?", "N'importe laquelle. MTLM prend du texte : il fonctionne après Whisper, votre propre modèle ou n'importe quelle API de transcription. La démo utilise Whisper tiny/base sur CPU uniquement pour montrer la chaîne complète."),
       ("Quelles langues ?", "Le français et l'anglais sont testés dans cette démo. D'autres langues sont possibles ; nous les testons sur vos appels avant de promettre quoi que ce soit."),
       ("Quelle précision ?", "Sur nos appels de test, chaque décision automatique était juste ; les appels flous sont partis en « redemander » ou vers un humain. Vos appels seront différents — c'est ce que mesure le pilote, sur vos propres transcriptions."),
       ("Faut-il un GPU ?", "Non. Tout tourne sur un simple CPU. Un modèle de décision adapté répond en ~15–20 ms."),
       ("Où vont mes données ?", "Nulle part : en production, MTLM tourne sur vos serveurs. Dans cette démo, l'audio et les transcriptions sont traités puis supprimés."),
       ("Combien de temps pour l'adapter ?", "Un premier modèle adapté prend des jours, pas des semaines : votre liste d'intentions et quelques centaines de transcriptions anonymisées suffisent pour démarrer.")],
  who="MTLM est développé par Javier Leandro Arancibia, en Savoie.", tech="Moteur et documentation :",
 ),
}

CSS = """
:root{--paper:#f7f8fa;--card:#ffffff;--ink:#14171c;--muted:#4f5663;--soft:#8b93a1;--line:#e2e5ea;--accent:#3b4fd8;--accent-ink:#ffffff;--accent-soft:#e8ebfd;--ok:#1d7a4e;--ok-soft:#e1f3ea;--warn:#a85b00;--warn-soft:#fbefdd;--bad:#b3261e;--bad-soft:#fbe4e2;--code:#0f1420;--code-ink:#d6dcf5}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--paper:#0f1216;--card:#171b21;--ink:#eef1f6;--muted:#b3bac6;--soft:#7d8696;--line:#2a3039;--accent:#8a99ff;--accent-ink:#0d1030;--accent-soft:#1f2550;--ok:#5fd19a;--ok-soft:#163327;--warn:#f2ad5b;--warn-soft:#3a2a12;--bad:#ff8a80;--bad-soft:#3d1a18;--code:#0a0d12;--code-ink:#c9d1f0}}
:root[data-theme="dark"]{--paper:#0f1216;--card:#171b21;--ink:#eef1f6;--muted:#b3bac6;--soft:#7d8696;--line:#2a3039;--accent:#8a99ff;--accent-ink:#0d1030;--accent-soft:#1f2550;--ok:#5fd19a;--ok-soft:#163327;--warn:#f2ad5b;--warn-soft:#3a2a12;--bad:#ff8a80;--bad-soft:#3d1a18;--code:#0a0d12;--code-ink:#c9d1f0}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--paper);color:var(--ink);font-family:'Inter',system-ui,sans-serif;line-height:1.55;font-size:17px}
a{color:var(--accent)}code,pre,.mono{font-family:'JetBrains Mono',ui-monospace,monospace}
.wrap{max-width:1060px;margin:0 auto;padding:0 20px}
header{border-bottom:1px solid var(--line);background:var(--paper);position:sticky;top:0;z-index:5}
.bar{display:flex;align-items:center;justify-content:space-between;height:62px;gap:12px}
.brand{font-weight:800;font-size:19px;letter-spacing:-.02em;color:var(--ink);text-decoration:none;display:flex;align-items:center;gap:9px}
.wave{display:inline-flex;gap:3px;align-items:center;height:20px}.wave b{display:block;width:3px;border-radius:2px;background:var(--accent)}
nav a{color:var(--muted);text-decoration:none;font-size:15px;margin-left:18px}nav a:hover{color:var(--ink)}
.btn{display:inline-block;background:var(--accent);color:var(--accent-ink);padding:12px 20px;border-radius:10px;font-weight:600;text-decoration:none;border:0;font-size:16px;cursor:pointer;font-family:inherit}
.btn:hover{filter:brightness(1.08)}.btn:disabled{opacity:.5;cursor:wait}
.btn.ghost{background:transparent;color:var(--ink);border:1.5px solid var(--line)}
.btn.sm{padding:8px 14px;font-size:14px}
.hero{padding-top:70px;padding-bottom:54px}
h1{font-size:clamp(34px,5.2vw,56px);line-height:1.08;letter-spacing:-.03em;margin:0 0 20px;font-weight:800;max-width:820px}
.sub{font-size:19px;color:var(--muted);max-width:690px;margin:0 0 28px}
.ctas{display:flex;gap:12px;flex-wrap:wrap}
.eyebrow{display:inline-block;font-size:14px;font-weight:600;color:var(--accent);background:var(--accent-soft);padding:6px 12px;border-radius:999px;margin-bottom:18px}
.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:34px}
.msg .k{font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--accent)}.msg .v{font-size:19px;font-weight:800;margin:6px 0 6px;letter-spacing:-.01em;line-height:1.25}.msg p{font-size:15px}
.proof{display:flex;gap:10px 22px;flex-wrap:wrap;margin-top:30px;color:var(--muted);font-size:15px;padding:0;list-style:none}
.proof li:before{content:"✓";color:var(--accent);font-weight:700;margin-right:8px}
section{padding:56px 0;border-top:1px solid var(--line)}
h2{font-size:clamp(26px,3.4vw,34px);letter-spacing:-.02em;margin:0 0 12px;line-height:1.15}
.lead{color:var(--muted);max-width:680px;margin:0 0 26px}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:22px}
.card h3{margin:0 0 8px;font-size:18px}.card p{margin:0;color:var(--muted);font-size:16px}
.demo{display:grid;grid-template-columns:1fr 1fr;gap:20px;align-items:start}
.ctl{display:flex;flex-wrap:wrap;gap:14px 20px;margin-bottom:16px}
.lbl{display:block;font-size:13px;color:var(--soft);margin-bottom:6px;font-weight:600;text-transform:uppercase;letter-spacing:.04em}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:10px;overflow:hidden}
.seg button{font-family:inherit;cursor:pointer;border:0;background:var(--card);color:var(--muted);padding:7px 13px;font-size:14px}
.seg button.on{background:var(--accent);color:var(--accent-ink)}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px}
.chips button{font-family:inherit;cursor:pointer;border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:10px;padding:8px 12px;font-size:14px;text-align:left}
.chips button:before{content:"▶";color:var(--accent);font-size:11px;margin-right:7px}
.chips button:hover{border-color:var(--accent)}
#rec{display:inline-flex;align-items:center;gap:9px}#rec .dot{width:10px;height:10px;border-radius:50%;background:currentColor}
#rec.on{background:var(--bad);color:#fff}
.row{display:flex;gap:8px;margin-top:8px}
input,textarea{font-family:inherit;font-size:16px;width:100%;min-width:0;padding:12px 14px;border-radius:10px;border:1.5px solid var(--line);background:var(--card);color:var(--ink)}
input:focus{outline:none;border-color:var(--accent)}
.panel{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px;min-height:260px}
.empty{color:var(--soft);display:flex;align-items:center;justify-content:center;min-height:220px;text-align:center}
.act{display:inline-block;font-weight:700;font-size:20px;padding:7px 14px;border-radius:9px}
.act.route{background:var(--ok-soft);color:var(--ok)}.act.handoff{background:var(--warn-soft);color:var(--warn)}.act.block{background:var(--bad-soft);color:var(--bad)}.act.clarify,.act.confirm{background:var(--accent-soft);color:var(--accent)}.reply{margin:10px 0 4px;font-style:italic}.act.s2dfb{background:var(--line,#8882);color:inherit;opacity:.85}.s2dw{border-left:3px solid var(--accent);padding-left:8px}
.why{color:var(--muted);font-size:15px;margin:8px 0 14px}
.tx{background:var(--paper);border-radius:9px;padding:11px 13px;font-size:15px;margin:6px 0 14px}
.mets{display:grid;grid-template-columns:repeat(auto-fit,minmax(96px,1fr));gap:8px}
.met{border:1px solid var(--line);border-radius:9px;padding:7px 9px}.met b{display:block;font-size:17px;font-variant-numeric:tabular-nums}.met span{font-size:12px;color:var(--soft)}
details.raw{margin-top:14px}details.raw summary{cursor:pointer;font-size:14px;color:var(--muted)}
pre{background:var(--code);color:var(--code-ink);border-radius:10px;padding:14px;font-size:13px;overflow-x:auto;margin:8px 0 0;line-height:1.5}
.note{color:var(--soft);font-size:14px;margin-top:12px}
audio{width:100%;margin-top:10px;height:36px}
.flow{display:flex;gap:10px;align-items:stretch;flex-wrap:wrap;margin:24px 0}
.flow .card{flex:1;min-width:150px;padding:16px}.flow .card.me{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
.flow .arr{align-self:center;color:var(--soft);font-size:20px}
.flow h3{font-size:16px;margin:0 0 4px}.flow p{font-size:14px}
.code2{display:grid;grid-template-columns:1fr 1fr;gap:16px}.code2>div,.demo>div{min-width:0}
.speed{width:100%;border-collapse:collapse;margin-top:8px}.speed td{padding:14px 10px;border-bottom:1px solid var(--line);vertical-align:top}
.speed td:nth-child(2){font-weight:800;font-size:20px;white-space:nowrap;font-variant-numeric:tabular-nums}.speed td:nth-child(3){color:var(--muted);font-size:15px}
.price{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.price .amt{font-size:28px;font-weight:800;margin:4px 0 10px;letter-spacing:-.02em}
.price .card.hi{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
.formwrap{max-width:560px}form.lead{display:grid;gap:10px}
details.faq{border-bottom:1px solid var(--line);padding:16px 0}details.faq summary{cursor:pointer;font-weight:600;font-size:17px}details.faq p{color:var(--muted);margin:10px 0 0}
footer{border-top:1px solid var(--line);padding:32px 0 48px;color:var(--soft);font-size:14px}footer p{margin:4px 0}
@media (max-width:980px){.grid4{grid-template-columns:repeat(2,1fr)}}
@media (max-width:820px){.grid3,.demo,.code2,.price{grid-template-columns:1fr}nav a.hide{display:none}.hero{padding-top:44px;padding-bottom:38px}.flow{flex-direction:column}.flow .arr{transform:rotate(90deg)}}
"""

PAGE = r"""<!DOCTYPE html>
<html lang="%%lang%%"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>%%title%%</title>
<meta name="description" content="%%desc%%">
<link rel="canonical" href="%%canon%%">
<link rel="alternate" hreflang="%%olang%%" href="%%ocanon%%">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='7' fill='%233b4fd8'/><g fill='white'><rect x='7' y='13' width='3' height='6' rx='1.5'/><rect x='12' y='9' width='3' height='14' rx='1.5'/><rect x='17' y='6' width='3' height='20' rx='1.5'/><rect x='22' y='11' width='3' height='10' rx='1.5'/></g></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>%%css%%</style>
<script defer src="https://vigie.intrane.fr/vigie.js" data-site="voice.intrane.fr"></script>
</head><body>
<header><div class="wrap bar">
  <a class="brand" href="%%path%%"><span class="wave"><b style="height:8px"></b><b style="height:16px"></b><b style="height:20px"></b><b style="height:12px"></b></span>MTLM Voice</a>
  <nav><a class="hide" href="#demo">%%nav_demo%%</a><a class="hide" href="#how">%%nav_how%%</a><a class="hide" href="#pricing">%%nav_price%%</a><a href="%%other%%">%%other_label%%</a><a class="btn sm" style="margin-left:18px;color:var(--accent-ink)" href="#partner" data-track="mv_nav_partner">%%nav_cta%%</a></nav>
</div></header>
<main>
<div class="wrap hero">
  <span class="eyebrow">%%eyebrow%%</span>
  <h1>%%h1%%</h1>
  <p class="sub">%%sub%%</p>
  <div class="ctas"><a class="btn" href="#demo" data-track="mv_hero_demo">%%cta1%%</a><a class="btn ghost" href="#partner" data-track="mv_hero_partner">%%cta2%%</a></div>
  <ul class="proof">%%proof%%</ul>
  <div class="grid4">%%msgs%%</div>
</div>
<section><div class="wrap"><h2>%%pain_h%%</h2><div class="grid3" style="margin-top:24px">%%pain%%</div></div></section>
<section id="demo"><div class="wrap">
  <h2>%%demo_h%%</h2><p class="lead">%%demo_p%%</p>
  <div class="demo">
    <div>
      <div class="ctl">
        <div><span class="lbl">%%l_lang%%</span><div class="seg" id="seg-lang"><button type="button" data-v="en">English</button><button type="button" data-v="fr">Français</button></div></div>
        <div><span class="lbl">%%l_model%%</span><div class="seg" id="seg-model"><button type="button" data-v="tiny-q5_1">Whisper tiny · 39M</button><button type="button" data-v="base-q5_1">Whisper base · 74M</button><button type="button" data-v="small-fr-q5_1" id="m-frs">Whisper small FR · 244M</button></div></div>
      </div>
      <span class="lbl">%%l_samples%%</span>
      <div class="chips" id="chips"></div>
      <button class="btn" id="rec" type="button"><span class="dot"></span><span id="rec-l">%%rec%%</span></button>
      <span class="lbl" style="margin-top:20px">%%or_paste%%</span>
      <form id="txt-form" class="row"><input id="txt" maxlength="600" placeholder="%%ph%%"><button class="btn" type="submit">%%go%%</button></form>
      <audio id="player" controls hidden></audio>
      <p class="note">%%demo_note%%</p>
    </div>
    <div class="panel" id="out"><div class="empty">—</div></div>
  </div>
</div></section>
<section id="how"><div class="wrap">
  <h2>%%how_h%%</h2><p class="lead">%%how_p%%</p>
  <div class="flow">%%flow%%</div>
  <div class="code2"><div><span class="lbl">%%req_l%%</span><pre>%%req%%</pre></div><div><span class="lbl">%%res_l%%</span><pre>%%res%%</pre></div></div>
</div></section>
<section><div class="wrap"><h2>%%dec_h%%</h2><div class="grid3" style="margin-top:24px">%%dec%%</div></div></section>
<section><div class="wrap" style="max-width:860px"><h2>%%speed_h%%</h2><table class="speed">%%speed%%</table></div></section>
<section id="s2d"><div class="wrap"><span class="eyebrow">%%s2d_tag%%</span><h2>%%s2d_h%%</h2><p class="lead">%%s2d_p%%</p><div class="grid3" style="margin-top:24px">%%s2d_pts%%</div><div class="ctas" style="margin-top:24px"><a class="btn" href="%%s2d_site%%" data-track="mv_s2d_site">%%s2d_more%%</a> <a class="btn ghost" href="#partner" data-track="mv_s2d_partner">%%s2d_cta%%</a></div></div></section>
<section id="pricing"><div class="wrap"><h2>%%price_h%%</h2><div class="price" style="margin-top:24px">%%price%%</div></div></section>
<section id="partner"><div class="wrap formwrap">
  <h2>%%form_h%%</h2>
  <form id="lead-form" class="lead">
    <input name="email" type="email" required placeholder="%%f_email%%">
    <input name="company" type="text" required placeholder="%%f_company%%">
    <input name="use_case" type="text" placeholder="%%f_use%%">
    <input name="volume" type="text" placeholder="%%f_vol%%">
    <input name="stack" type="text" placeholder="%%f_stack%%">
    <input name="website" type="text" tabindex="-1" autocomplete="off" style="display:none" aria-hidden="true">
    <input type="hidden" name="lang" value="%%lang%%"><input type="hidden" name="niche" value="voice">
    <button type="submit" class="btn">%%f_btn%%</button>
    <p id="lead-msg" class="note" style="text-align:center;margin:0"></p>
    <p class="note" style="text-align:center;margin:0">%%f_note%%</p>
  </form>
</div></section>
<section><div class="wrap" style="max-width:780px"><h2>%%faq_h%%</h2>%%faq%%</div></section>
</main>
<footer><div class="wrap">
  <p>%%who%% <a href="https://www.linkedin.com/in/arancibiajav/" rel="noopener" target="_blank">LinkedIn</a></p>
  <p>%%tech%% <a href="https://mtlm-router.intrane.fr/" data-track="mv_footer_tech">mtlm-router →</a></p>
</div></footer>
<script>
(function(){
var T=%%tj%%,S=%%samples%%,API='%%api%%',LANG='%%lang%%'==='fr'?'fr':'en',MODEL='base-q5_1',busy=false;
var out=document.getElementById('out'),chips=document.getElementById('chips'),player=document.getElementById('player'),recB=document.getElementById('rec'),recL=document.getElementById('rec-l'),txt=document.getElementById('txt');
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function seg(id,v){Array.prototype.forEach.call(document.querySelectorAll('#'+id+' button'),function(b){b.className=b.dataset.v===v?'on':''})}
function setModel(m){MODEL=m;seg('seg-model',m)}
function setLang(l){LANG=l;seg('seg-lang',l);var fs=document.getElementById('m-frs');fs.hidden=l!=='fr';setModel(l==='fr'?'small-fr-q5_1':'base-q5_1');chips.innerHTML=S.filter(function(s){return s.lang===l}).map(function(s){return '<button type="button" data-id="'+s.id+'">'+esc(s.label)+'</button>'}).join('');
 Array.prototype.forEach.call(chips.querySelectorAll('button'),function(b){b.addEventListener('click',function(){var s=S.filter(function(x){return x.id===b.dataset.id})[0];player.hidden=false;player.src='data:audio/webm;base64,'+s.b64;player.play().catch(function(){});send({audio_b64:s.b64},'sample:'+s.id)})})}
function lock(on){busy=on;Array.prototype.forEach.call(document.querySelectorAll('#demo button'),function(b){if(b!==recB||!rec)b.disabled=on})}
function pct(x){return x==null?'—':Math.round(x*100)+'%'}
function sec(ms){return ms==null?'—':(ms/1000).toFixed(1)+' s'}
function show(d){var a=d.action||'clarify',lab={route:T.a_route,handoff:T.a_handoff,block:T.a_block,clarify:T.a_clarify,confirm:T.a_confirm}[a],why={route:T.why_route,handoff:T.why_handoff,block:T.why_block,clarify:T.why_clarify,confirm:T.why_confirm}[a];
 var s2=d.path==='s2d';
 var head='<span class="act '+a+'">'+esc(lab)+(d.intent&&(a==='route'||a==='confirm')?' → '+esc(d.intent):'')+'</span>'+(s2?' <span class="act route">⚡ '+esc(T.p_s2d)+'</span>':(d.s2d_intent?' <span class="act s2dfb">⚡ '+esc(T.s2d_fb)+'</span>':''));
 var rp=d.reply_text?'<span class="lbl">'+T.reply_l+'</span><div class="reply">« '+esc(d.reply_text)+' »</div>':'';
 var m='';if(d.audio_s!=null)m+='<div class="met"><b>'+d.audio_s+' s</b><span>'+T.m_audio+'</span></div><div class="met"><b>'+sec(d.stt_ms)+'</b><span>'+T.m_stt+'</span></div>';
 if(d.s2d_ms!=null)m+='<div class="met"><b>'+sec(d.s2d_ms)+'</b><span>'+T.m_s2d+'</span></div>';
 m+='<div class="met"><b>'+sec(d.decide_ms)+'</b><span>'+T.m_dec+'</span></div><div class="met"><b>'+pct(d.intent_confidence)+'</b><span>'+T.m_conf+'</span></div><div class="met"><b>'+pct(d.p_robocall)+'</b><span>'+T.m_robo+'</span></div>';
 if(window.innerWidth<820)out.scrollIntoView({behavior:'smooth',block:'start'});var gs=(!s2&&d.s2d_intent)?'<div class="why s2dw">⚡ '+esc(T.s2d_fbw)+' <b>'+esc(d.s2d_intent)+'</b> ('+pct(d.s2d_confidence)+', '+(T.m_conf)+' &lt; '+pct(d.s2d_threshold)+') — '+esc(T.s2d_fbw2)+'.</div>':((!s2&&LANG==='en')?'<div class="why s2dw">⚡ '+esc(T.s2d_en)+'.</div>':'');
 out.innerHTML=head+'<div class="why">'+esc(s2?T.p_s2d_why:why)+'</div>'+gs+'<div class="why">'+(a==='clarify'&&d.intent?' · '+esc(d.intent)+'?':'')+'</div>'+rp+'<span class="lbl">'+T.heard+'</span><div class="tx">'+(s2?'<em>'+esc(T.no_tx)+'</em>':esc(d.text))+'</div><div class="mets">'+m+'</div><details class="raw"><summary>'+T.json_l+'</summary><pre>'+esc(JSON.stringify(d,null,2))+'</pre></details>';}
function send(body,src){if(busy)return;lock(true);out.innerHTML='<div class="empty">'+(body.text?T.wait_txt:T.wait)+'</div>';body.lang=LANG;body.model=MODEL;
 fetch(API,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)}).then(function(r){if(r.status===429)throw 'lim';return r.json()})
 .then(function(d){if(!d||!d.action)throw 'err';show(d);if(d.reply_audio_b64){try{new Audio('data:'+(d.reply_audio_type||'audio/ogg')+';base64,'+d.reply_audio_b64).play().catch(function(){})}catch(e){}}if(window.vigie)vigie('voice_decide',{action:d.action,lang:LANG,src:src,model:MODEL})})
 .catch(function(e){out.innerHTML='<div class="empty" style="color:var(--warn)">'+(e==='lim'?T.lim:T.err)+'</div>'}).then(function(){lock(false)})}
var rec=null,chunks=[],timer=null;
function b64(blob,cb){var r=new FileReader();r.onload=function(){cb(String(r.result).split(',')[1])};r.readAsDataURL(blob)}
function stopRec(){if(rec&&rec.state!=='inactive')rec.stop();clearTimeout(timer)}
recB.addEventListener('click',function(){if(rec){stopRec();return}if(busy)return;
 if(!navigator.mediaDevices||!window.MediaRecorder){out.innerHTML='<div class="empty">'+T.mic_no+'</div>';return}
 navigator.mediaDevices.getUserMedia({audio:true}).then(function(st){chunks=[];var opt=MediaRecorder.isTypeSupported&&MediaRecorder.isTypeSupported('audio/webm;codecs=opus')?{mimeType:'audio/webm;codecs=opus',audioBitsPerSecond:24000}:{};
  rec=new MediaRecorder(st,opt);rec.ondataavailable=function(e){chunks.push(e.data)};
  rec.onstop=function(){st.getTracks().forEach(function(t){t.stop()});var bl=new Blob(chunks,{type:rec.mimeType||'audio/webm'});rec=null;recB.classList.remove('on');recL.textContent=T.rec;player.hidden=false;player.src=URL.createObjectURL(bl);b64(bl,function(x){send({audio_b64:x},'mic')})};
  rec.start();recB.classList.add('on');recL.textContent=T.stop;timer=setTimeout(function(){stopRec()},30000)})
 .catch(function(){out.innerHTML='<div class="empty">'+T.mic_no+'</div>'})});
document.getElementById('txt-form').addEventListener('submit',function(e){e.preventDefault();var t=txt.value.trim();if(t.length>=3)send({text:t},'text')});
Array.prototype.forEach.call(document.querySelectorAll('#seg-lang button'),function(b){b.addEventListener('click',function(){setLang(b.dataset.v)})});
Array.prototype.forEach.call(document.querySelectorAll('#seg-model button'),function(b){b.addEventListener('click',function(){MODEL=b.dataset.v;seg('seg-model',MODEL)})});
setLang(LANG);seg('seg-model',MODEL);
var lf=document.getElementById('lead-form');lf.addEventListener('submit',function(ev){ev.preventDefault();
 var msg=document.getElementById('lead-msg'),fd=new FormData(lf),f={};fd.forEach(function(v,k){f[k]=v});if(f.website)return;delete f.website;
 var lb=lf.querySelector('button');if(lb.disabled)return;lb.disabled=true;msg.textContent=T.f_sending;
 fetch('https://bkn.intrane.fr/v1/hooks/forms',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({form:'mtlm-leads',fields:f})})
 .then(function(r){return r.json()}).then(function(x){if(x&&x.ok){msg.textContent=T.f_ok;lf.reset();if(window.vigie)vigie('lead',{form:'mtlm-leads',niche:'voice'})}else{msg.textContent=(x&&x.error)||T.f_ko}})
 .catch(function(){msg.textContent=T.f_ko}).then(function(){lb.disabled=false})});
document.addEventListener('click',function(e){var t=e.target.closest('[data-track]');if(t&&window.vigie)vigie(t.getAttribute('data-track'),{page:location.pathname})});
})();
</script>
</body></html>
"""


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def page(k):
    d = T[k]
    flow = '<div class="arr">→</div>'.join(
        f'<div class="card{" me" if i == 2 else ""}"><h3>{esc(h)}</h3><p>{esc(p)}</p></div>' for i, (h, p) in enumerate(d["flow"]))
    rep = {
        "lang": d["lang"], "olang": "fr" if k == "en" else "en", "path": d["path"], "other": d["other"], "other_label": d["other_label"],
        "canon": SITE + d["path"], "ocanon": SITE + T["fr" if k == "en" else "en"]["path"],
        "title": esc(d["title"]), "desc": esc(d["desc"]), "css": CSS, "api": API, "h1": d["h1"],
        "msgs": "".join(f'<div class="card msg"><div class="k">{esc(k)}</div><div class="v">{esc(v)}</div><p>{esc(t)}</p></div>' for k, v, t in d["msgs"]),
        "proof": "".join(f"<li>{esc(t)}</li>" for t in d["proof"]),
        "pain": "".join(f'<div class="card"><h3>{esc(h)}</h3><p>{esc(p)}</p></div>' for h, p in d["pain"]),
        "dec": "".join(f'<div class="card"><h3>{esc(h)}</h3><p>{esc(p)}</p></div>' for h, p in d["dec"]),
        "speed": "".join(f"<tr><td>{esc(a)}</td><td>{esc(b)}</td><td>{esc(c)}</td></tr>" for a, b, c in d["speed"]),
        "price": "".join(f'<div class="card{" hi" if i == 0 else ""}"><h3>{esc(h)}</h3><div class="amt">{esc(a)}</div><p>{esc(p)}</p></div>'
                         for i, (h, a, p) in enumerate(d["price"])),
        "s2d_pts": "".join(f'<div class="card"><h3>{esc(h)}</h3><p>{esc(t)}</p></div>' for h, t in d["s2d_pts"]),
        "faq": "".join(f'<details class="faq"><summary>{esc(q)}</summary><p>{esc(a)}</p></details>' for q, a in d["faq"]),
        "flow": flow, "req": esc(EXAMPLE_REQ), "res": esc(EXAMPLE_RES),
        "tj": json.dumps({x: d[x] for x in ("rec", "stop", "wait", "wait_txt", "a_route", "a_handoff", "a_block", "a_clarify", "a_confirm", "why_confirm", "reply_l", "why_route",
                                             "why_handoff", "why_block", "why_clarify", "m_audio", "m_stt", "m_dec", "m_conf", "m_robo", "p_s2d", "p_s2d_why", "m_s2d", "no_tx", "s2d_guess", "s2d_fb", "s2d_fbw", "s2d_fbw2", "s2d_en",
                                             "heard", "json_l", "lim", "err", "mic_no", "too_long", "f_sending", "f_ok", "f_ko")}, ensure_ascii=False),
        "samples": json.dumps([{x: s[x] for x in ("id", "lang", "label", "b64")} for s in SAMPLES], ensure_ascii=False),
    }
    for key in ("s2d_tag", "s2d_h", "s2d_p", "s2d_cta", "s2d_more", "s2d_site", "eyebrow", "nav_demo", "nav_how", "nav_price", "nav_cta", "sub", "cta1", "cta2", "pain_h", "demo_h", "demo_p", "l_lang", "l_model",
                "l_samples", "rec", "or_paste", "ph", "go", "demo_note", "how_h", "how_p", "req_l", "res_l", "dec_h", "speed_h", "price_h",
                "form_h", "f_email", "f_company", "f_use", "f_vol", "f_stack", "f_btn", "f_note", "faq_h", "who", "tech"):
        rep[key] = esc(d[key])
    h = PAGE
    for key, v in rep.items():
        h = h.replace("%%" + key + "%%", v)
    assert "%%" not in h.replace("%%", "", 0) or "%%" not in h, [x for x in h.split("%%")[1::2]][:5]
    return h


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for k in ("en", "fr"):
        open(os.path.join(OUT, T[k]["file"]), "w").write(page(k))
        print("wrote voice-site/" + T[k]["file"])
    open(os.path.join(OUT, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n")
    open(os.path.join(OUT, "sitemap.xml"), "w").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{SITE}{p}</loc></url>\n" for p in ("/", "/fr")) + "</urlset>\n")
    print("wrote voice-site/robots.txt, sitemap.xml")
