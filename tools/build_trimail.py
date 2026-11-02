#!/usr/bin/env python3
"""Generate the Tri Mail solution pages (site/inbox-fr.html, site/inbox.html).

Tri Mail is the done-for-you inbox-sorting offer for non-technical SME owners. It is
deliberately NOT built on layout.html: no developer nav, no jargon, its own light theme.
mtlm only appears as "propulsé par" in the footer. Edit the copy here, then run:
    python3 tools/build_trimail.py
"""
import json, os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site")

CHIPS = {
    "fr": {
        "transport": ["Bonjour, pouvez-vous me faire un devis pour 12 palettes Lyon-Chambéry jeudi ?",
                      "Où en est la livraison CMR 44821 ? Elle devait arriver hier.",
                      "La marchandise est arrivée abîmée, 3 cartons écrasés.",
                      "Relance : règlement de la facture de septembre"],
        "syndic": ["Fuite d'eau au plafond de ma salle de bain, que dois-je faire ?",
                   "L'ascenseur est encore en panne depuis lundi.",
                   "Je ne comprends pas mon relevé de charges du 3e trimestre.",
                   "Quand aura lieu la prochaine AG ?"],
        "compta": ["Vous trouverez ci-joint les factures d'achat d'octobre.",
                   "Embauche d'un salarié au 1er décembre, que vous faut-il ?",
                   "Rappel : échéance de TVA du 19 novembre.",
                   "Découvrez notre nouveau logiciel de caisse !"],
    }
}
CHIPS["en"] = CHIPS["fr"]  # the engine is tuned on French mail; the EN page demos the same French examples

T = {
 "fr": dict(
  lang="fr", other="inbox", other_label="EN", title="Tri Mail — vos mails triés automatiquement, installé chez vous",
  desc="Tri Mail range automatiquement les mails de votre boîte partagée (devis, suivis, litiges, factures…). Installé chez vous, sans abonnement, les cas douteux restent pour un humain.",
  nav_try="Essayer", nav_offer="Tarif", nav_cta="Audit gratuit",
  h1="Vos mails triés automatiquement.<br>Installé chez vous.",
  sub="Chaque matin, quelqu'un ouvre la boîte contact@ et range les devis, les suivis, les réclamations et les factures. Tri Mail le fait à sa place, sur votre propre machine. Quand il hésite, il laisse le mail à un humain plutôt que de se tromper.",
  cta1="Essayer maintenant", cta2="Audit gratuit sur vos mails",
  proof=["Aucune donnée ne sort de chez vous", "Pas d'abonnement obligatoire", "Les cas douteux restent pour un humain"],
  pain_h="Pourquoi vos mails méritent mieux qu'un tri à la main",
  pain=[("Du temps perdu tous les jours", "Trier une boîte partagée prend facilement 30 minutes à une heure par jour, avant même de traiter le premier mail."),
        ("Un mail mal rangé coûte cher", "Une réclamation classée en facture, c'est un client qui attend. Tri Mail préfère vous laisser un mail que le ranger au mauvais endroit."),
        ("Vos mails restent chez vous", "Pas de ChatGPT, pas de serveur américain : Tri Mail tourne sur votre machine. Vos mails et ceux de vos clients ne sortent jamais.")],
  demo_h="Essayez sur vos propres mails",
  demo_p="Choisissez votre métier, collez l'objet ou la première phrase d'un mail, et regardez où Tri Mail le rangerait. C'est le vrai moteur, en direct.",
  sec=[("transport", "Transport"), ("syndic", "Syndic / gestion"), ("compta", "Cabinet comptable")],
  ph="Collez l'objet ou le début d'un mail…", btn="Trier", wait="Analyse…",
  auto="Rangé automatiquement", review="Laissé à un humain", autre="Publicité / hors sujet", conf="confiance",
  lim="Limite de démo atteinte, réessayez dans une heure.", err="Le moteur ne répond pas, réessayez.",
  demo_note="Votre métier n'est pas dans la liste ? Tri Mail apprend vos propres catégories pendant l'installation.",
  how_h="Comment ça se passe",
  how=[("1", "Audit gratuit", "Vous m'envoyez les objets de 25 mails récents (un copier-coller suffit) et vos catégories de tri. Sous 48 h, vous recevez le tri et le taux de réussite."),
       ("2", "Installation", "J'installe Tri Mail sur votre machine et je l'entraîne sur vos mails. Vos mails arrivent rangés dans des dossiers ; les cas douteux vont dans « À vérifier »."),
       ("3", "30 jours d'accompagnement", "Un rapport chaque semaine : combien de mails rangés, combien laissés à un humain. Ensuite, Tri Mail vous appartient et continue de tourner.")],
  offer_h="Installé chez vous — 490 € HT, une seule fois",
  offer_badge="Tarif de lancement réservé aux 3 premiers clients",
  offer=["Installation et entraînement sur vos mails", "30 jours d'accompagnement, rapport hebdomadaire", "Aucun abonnement, aucun coût par mail", "Maintenance en option dès 150 € HT/mois, sans engagement — sans elle, rien ne s'arrête"],
  offer_hw="Pas de serveur ? Je fournis un mini-PC prêt à brancher, au prix coûtant.",
  form_h="Commencez par l'audit gratuit",
  f_email="vous@entreprise.fr", f_company="Entreprise", f_use="Quels mails ? ex. devis / suivi / litige / facture",
  f_btn="Demander l'audit gratuit", f_note="Utilisé uniquement pour vous répondre. Pas de newsletter.",
  f_sending="Envoi…", f_ok="Merci — je reviens vers vous sous 48 h avec la marche à suivre.", f_ko="Échec de l’envoi — réessayez dans un instant.",
  faq_h="Questions fréquentes",
  faq=[("Mes mails sortent-ils de l'entreprise ?", "Non. Tri Mail tourne sur votre machine et lit votre boîte comme le ferait un logiciel de messagerie. Aucun mail n'est envoyé à un service extérieur."),
       ("Ça marche avec ma messagerie ?", "Tri Mail fonctionne avec toute boîte accessible en IMAP, ce qui couvre la plupart des hébergeurs. Pour Microsoft 365 et Gmail, nous vérifions ensemble la connexion pendant l'audit."),
       ("Et s'il se trompe ?", "Quand Tri Mail n'est pas sûr, il range le mail dans « À vérifier » au lieu de deviner. Il ne supprime jamais rien, et pendant les premiers jours il peut tourner en mode observation, sans rien déplacer."),
       ("Comment se passe l'installation ?", "En Savoie et Haute-Savoie, je viens l'installer sur place (frais de déplacement en sus, selon la distance). Ailleurs en France ou à l'étranger, l'installation se fait à distance pendant un appel vidéo : sur votre serveur s'il y en a un, sinon je vous envoie un mini-PC déjà configuré, que vous n'avez qu'à brancher."),
       ("Quel matériel faut-il ?", "Un ordinateur ou un petit serveur sous Linux, même modeste — pas de carte graphique. Si vous n'en avez pas, je fournis un mini-PC au prix coûtant."),
       ("Et après les 30 jours ?", "Tri Mail est à vous et continue de fonctionner. La maintenance (mises à jour, ajustements de catégories, support) est optionnelle, à partir de 150 € HT par mois, sans engagement.")],
  who="Tri Mail est un service de Javier Leandro Arancibia, en Savoie.", tech="Propulsé par mtlm, un moteur de décision conçu pour tourner sur processeur, sans GPU.",
 ),
 "en": dict(
  lang="en", other="inbox-fr", other_label="FR", title="Tri Mail — your emails sorted automatically, installed on your premises",
  desc="Tri Mail automatically sorts your shared mailbox (quotes, tracking, complaints, invoices…). Installed on your premises, no subscription, doubtful cases stay with a human.",
  nav_try="Try it", nav_offer="Price", nav_cta="Free audit",
  h1="Your emails, sorted automatically.<br>Installed on your premises.",
  sub="Every morning someone opens the shared contact@ mailbox and files quotes, tracking requests, complaints and invoices. Tri Mail does it for them, on your own machine. When it is unsure, it leaves the email to a human instead of guessing.",
  cta1="Try it now", cta2="Free audit on your emails",
  proof=["No data leaves your premises", "No mandatory subscription", "Doubtful cases stay with a human"],
  pain_h="Why your inbox deserves better than sorting by hand",
  pain=[("Time lost every day", "Sorting a shared mailbox easily takes 30 minutes to an hour a day, before the first email is even handled."),
        ("A misfiled email is expensive", "A complaint filed as an invoice is a customer left waiting. Tri Mail would rather leave you an email than file it in the wrong place."),
        ("Your emails stay with you", "No ChatGPT, no US servers: Tri Mail runs on your machine. Your emails and your customers' never leave.")],
  demo_h="Try it on your own emails",
  demo_p="Pick your trade, paste the subject or first line of an email (in French), and see where Tri Mail would file it. This is the real engine, live.",
  sec=[("transport", "Transport"), ("syndic", "Property management"), ("compta", "Accounting firm")],
  ph="Paste a subject or the start of an email…", btn="Sort", wait="Analysing…",
  auto="Filed automatically", review="Left to a human", autre="Advertising / off-topic", conf="confidence",
  lim="Demo limit reached, try again in an hour.", err="The engine is not responding, try again.",
  demo_note="Your trade is not listed? Tri Mail learns your own categories during installation.",
  how_h="How it works",
  how=[("1", "Free audit", "Send me the subject lines of 25 recent emails (copy-paste is enough) and your sorting categories. Within 48 h you get the sort and the success rate."),
       ("2", "Installation", "I install Tri Mail on your machine and train it on your emails. Your emails arrive filed in folders; doubtful ones go to “To check”."),
       ("3", "30 days of support", "A weekly report: how many emails filed, how many left to a human. After that Tri Mail is yours and keeps running.")],
  offer_h="Installed on your premises — €490, one-off",
  offer_badge="Launch price, reserved for the first 3 customers",
  offer=["Installation and training on your emails", "30 days of support, weekly report", "No subscription, no per-email cost", "Optional maintenance from €150/month, no commitment — without it, nothing stops"],
  offer_hw="No server? I supply a ready-to-plug mini-PC at cost.",
  form_h="Start with the free audit",
  f_email="you@company.com", f_company="Company", f_use="Which emails? e.g. quotes / tracking / complaints / invoices",
  f_btn="Request the free audit", f_note="Used only to reply to you. No newsletter.",
  f_sending="Sending…", f_ok="Thanks — I will get back to you within 48 h with next steps.", f_ko="Could not send — please try again shortly.",
  faq_h="Frequently asked questions",
  faq=[("Do my emails leave the company?", "No. Tri Mail runs on your machine and reads your mailbox the way an email client would. No email is sent to any outside service."),
       ("Does it work with my email provider?", "Tri Mail works with any mailbox reachable over IMAP, which covers most providers. For Microsoft 365 and Gmail we check the connection together during the audit."),
       ("What if it gets it wrong?", "When Tri Mail is unsure it files the email in “To check” instead of guessing. It never deletes anything, and for the first days it can run in observe-only mode without moving anything."),
       ("How does installation work?", "In Savoie and Haute-Savoie (France), I install it on site (travel costs extra, depending on distance). Elsewhere in France or abroad, installation is done remotely over a video call: on your server if you have one, otherwise I ship you a pre-configured mini-PC that you just plug in."),
       ("What hardware do I need?", "A computer or small server running Linux, even a modest one — no graphics card. If you don't have one, I supply a mini-PC at cost."),
       ("And after the 30 days?", "Tri Mail is yours and keeps working. Maintenance (updates, category adjustments, support) is optional, from €150/month, no commitment.")],
  who="Tri Mail is a service by Javier Leandro Arancibia, based in Savoie, France.", tech="Powered by mtlm, a decision engine built to run on a plain CPU, no GPU.",
 ),
}

CSS = """
:root{--paper:#faf7f2;--card:#ffffff;--ink:#1c1917;--muted:#57534e;--soft:#a8a29e;--line:#e7e2d9;--accent:#1f6f4a;--accent-ink:#ffffff;--accent-soft:#e3f1e8;--warn:#b45309;--warn-soft:#fdf0dc}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--paper:#171513;--card:#211e1b;--ink:#f5f2ed;--muted:#c4bdb3;--soft:#8a837a;--line:#36312c;--accent:#4fb582;--accent-ink:#0f1a14;--accent-soft:#1d3327;--warn:#f0a952;--warn-soft:#3a2a14}}
:root[data-theme="dark"]{--paper:#171513;--card:#211e1b;--ink:#f5f2ed;--muted:#c4bdb3;--soft:#8a837a;--line:#36312c;--accent:#4fb582;--accent-ink:#0f1a14;--accent-soft:#1d3327;--warn:#f0a952;--warn-soft:#3a2a14}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--paper);color:var(--ink);font-family:'Figtree',system-ui,sans-serif;line-height:1.55;font-size:17px}
a{color:var(--accent)}
.wrap{max-width:1040px;margin:0 auto;padding:0 20px}
header{border-bottom:1px solid var(--line)}
.bar{display:flex;align-items:center;justify-content:space-between;height:64px;gap:12px}
.brand{font-weight:800;font-size:20px;letter-spacing:-.02em;color:var(--ink);text-decoration:none;display:flex;align-items:center;gap:8px}
.brand i{display:inline-block;width:22px;height:16px;border:2.5px solid var(--accent);border-radius:3px;position:relative}
.brand i:after{content:"";position:absolute;left:3px;right:3px;top:3px;height:5px;border-bottom:2.5px solid var(--accent);border-left:2.5px solid var(--accent);border-right:2.5px solid var(--accent);border-radius:0 0 3px 3px}
nav a{color:var(--muted);text-decoration:none;font-size:15px;margin-left:18px}nav a:hover{color:var(--ink)}
.btn{display:inline-block;background:var(--accent);color:var(--accent-ink);padding:13px 22px;border-radius:10px;font-weight:600;text-decoration:none;border:0;font-size:16px;cursor:pointer;font-family:inherit}
.btn:hover{filter:brightness(1.07)}
.btn.ghost{background:transparent;color:var(--ink);border:1.5px solid var(--line)}
.btn.sm{padding:8px 14px;font-size:14px}
.hero{padding-top:72px;padding-bottom:56px}
h1{font-size:clamp(34px,5.4vw,56px);line-height:1.08;letter-spacing:-.03em;margin:0 0 20px;font-weight:800;max-width:780px}
.sub{font-size:19px;color:var(--muted);max-width:660px;margin:0 0 28px}
.ctas{display:flex;gap:12px;flex-wrap:wrap}
.proof{display:flex;gap:10px 22px;flex-wrap:wrap;margin-top:30px;color:var(--muted);font-size:15px;padding:0;list-style:none}
.proof li:before{content:"✓";color:var(--accent);font-weight:700;margin-right:8px}
section{padding:56px 0;border-top:1px solid var(--line)}
h2{font-size:clamp(26px,3.4vw,34px);letter-spacing:-.02em;margin:0 0 12px;line-height:1.15}
.lead{color:var(--muted);max-width:640px;margin:0 0 28px}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:22px}
.card h3{margin:0 0 8px;font-size:18px}.card p{margin:0;color:var(--muted);font-size:16px}
.step{font-weight:800;color:var(--accent);font-size:15px;margin-bottom:6px}
.demo{max-width:680px}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}
.seg{display:flex;flex-wrap:wrap;gap:8px}
.seg button,.chips button{font-family:inherit;cursor:pointer;border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:999px;padding:7px 14px;font-size:14px}
.seg button.on{background:var(--accent);border-color:var(--accent);color:var(--accent-ink)}
.chips button{border-radius:10px;text-align:left;color:var(--muted);font-size:13px}
.row{display:flex;gap:8px}
input,textarea{font-family:inherit;font-size:16px;width:100%;min-width:0;padding:13px 14px;border-radius:10px;border:1.5px solid var(--line);background:var(--card);color:var(--ink)}
input:focus{outline:none;border-color:var(--accent)}
.out{min-height:84px;margin-top:14px;display:flex;align-items:center;justify-content:center;text-align:center;border-radius:12px;background:var(--card);border:1px dashed var(--line);padding:14px}
.cat{font-size:22px;font-weight:700}.verdict{font-weight:600;margin-top:4px}
.ok{color:var(--accent)}.warn{color:var(--warn)}.muted{color:var(--soft)}
.note{color:var(--soft);font-size:14px;margin-top:12px}
.offer{display:grid;grid-template-columns:1.1fr .9fr;gap:24px;align-items:start}
.badge{display:inline-block;background:var(--warn-soft);color:var(--warn);font-weight:600;font-size:14px;padding:5px 12px;border-radius:999px;margin-bottom:14px}
.ticks{list-style:none;padding:0;margin:0 0 16px}.ticks li{padding:8px 0;border-bottom:1px solid var(--line)}.ticks li:before{content:"✓";color:var(--accent);font-weight:700;margin-right:10px}
form.lead{display:grid;gap:10px}
details{border-bottom:1px solid var(--line);padding:16px 0}summary{cursor:pointer;font-weight:600;font-size:17px}details p{color:var(--muted);margin:10px 0 0}
footer{border-top:1px solid var(--line);padding:32px 0 48px;color:var(--soft);font-size:14px}
footer p{margin:4px 0}
@media (max-width:780px){.grid3,.offer{grid-template-columns:1fr}nav a.hide{display:none}.hero{padding-top:48px;padding-bottom:40px}.row{flex-direction:column}}
"""


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def page(k):
    d = T[k]
    secs = "".join(f'<button type="button" data-s="{s}">{esc(n)}</button>' for s, n in d["sec"])
    pains = "".join(f'<div class="card"><h3>{esc(h)}</h3><p>{esc(p)}</p></div>' for h, p in d["pain"])
    steps = "".join(f'<div class="card"><div class="step">{n}</div><h3>{esc(h)}</h3><p>{esc(p)}</p></div>' for n, h, p in d["how"])
    ticks = "".join(f"<li>{esc(t)}</li>" for t in d["offer"])
    proof = "".join(f"<li>{esc(t)}</li>" for t in d["proof"])
    faq = "".join(f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in d["faq"])
    tj = json.dumps({x: d[x] for x in ("wait", "auto", "review", "autre", "conf", "lim", "err", "f_sending", "f_ok", "f_ko")}, ensure_ascii=False)
    chips = json.dumps(CHIPS[k], ensure_ascii=False)
    tech_href = "/mtlm-router/fr" if k == "fr" else "/mtlm-router"
    return f"""<!DOCTYPE html>
<html lang="{d['lang']}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(d['title'])}</title>
<meta name="description" content="{esc(d['desc'])}">
<link rel="alternate" hreflang="{'en' if k == 'fr' else 'fr'}" href="https://mtlm-router.intrane.fr/mtlm-router/{d['other']}">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='7' fill='%231f6f4a'/><rect x='7' y='9' width='18' height='14' rx='2' fill='none' stroke='white' stroke-width='2.5'/><path d='M10 15h12' stroke='white' stroke-width='2.5'/></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>{CSS}</style>
<script defer src="https://vigie.intrane.fr/vigie.js" data-site="mtlm-router.intrane.fr"></script>
</head><body>
<header><div class="wrap bar">
  <a class="brand" href="#"><i></i>Tri Mail</a>
  <nav><a class="hide" href="#essai">{d['nav_try']}</a><a class="hide" href="#tarif">{d['nav_offer']}</a><a href="/mtlm-router/{d['other']}">{d['other_label']}</a><a class="btn sm" style="margin-left:18px;color:var(--accent-ink)" href="#audit" data-track="tm_nav_audit">{d['nav_cta']}</a></nav>
</div></header>
<main>
<div class="wrap hero">
  <h1>{d['h1']}</h1>
  <p class="sub">{esc(d['sub'])}</p>
  <div class="ctas"><a class="btn" href="#essai" data-track="tm_hero_try">{d['cta1']}</a><a class="btn ghost" href="#audit" data-track="tm_hero_audit">{d['cta2']}</a></div>
  <ul class="proof">{proof}</ul>
</div>
<section><div class="wrap"><h2>{esc(d['pain_h'])}</h2><div class="grid3" style="margin-top:24px">{pains}</div></div></section>
<section id="essai"><div class="wrap demo">
  <h2>{esc(d['demo_h'])}</h2><p class="lead">{esc(d['demo_p'])}</p>
  <div class="seg" id="tri-seg">{secs}</div>
  <div class="chips" id="tri-chips"></div>
  <form id="tri-form" class="row"><input id="tri-text" maxlength="300" required placeholder="{esc(d['ph'])}"><button class="btn">{d['btn']}</button></form>
  <div class="out" id="tri-out"><span class="muted">—</span></div>
  <p class="note">{esc(d['demo_note'])}</p>
</div></section>
<section><div class="wrap"><h2>{esc(d['how_h'])}</h2><div class="grid3" style="margin-top:24px">{steps}</div></div></section>
<section id="tarif"><div class="wrap offer">
  <div><span class="badge">{esc(d['offer_badge'])}</span><h2>{esc(d['offer_h'])}</h2><ul class="ticks">{ticks}</ul><p class="note">{esc(d['offer_hw'])}</p></div>
  <div class="card" id="audit"><h3 style="margin-bottom:14px">{esc(d['form_h'])}</h3>
    <form id="lead-form" class="lead">
      <input name="email" type="email" required placeholder="{d['f_email']}">
      <input name="company" type="text" placeholder="{esc(d['f_company'])}">
      <input name="use_case" type="text" placeholder="{esc(d['f_use'])}">
      <input name="website" type="text" tabindex="-1" autocomplete="off" style="display:none" aria-hidden="true">
      <input type="hidden" name="lang" value="{d['lang']}"><input type="hidden" name="niche" value="tri-mail">
      <button type="submit" class="btn">{esc(d['f_btn'])}</button>
      <p id="lead-msg" class="note" style="text-align:center;margin:0"></p>
      <p class="note" style="text-align:center;margin:0">{esc(d['f_note'])}</p>
    </form></div>
</div></section>
<section><div class="wrap" style="max-width:760px"><h2>{esc(d['faq_h'])}</h2>{faq}</div></section>
</main>
<footer><div class="wrap">
  <p>{esc(d['who'])} <a href="https://www.linkedin.com/in/arancibiajav/" rel="noopener" target="_blank">LinkedIn</a></p>
  <p>{esc(d['tech'])} <a href="{tech_href}" data-track="tm_footer_tech">mtlm →</a></p>
</div></footer>
<script>
(function(){{var CH={chips},T={tj},S='transport';
var out=document.getElementById('tri-out'),inp=document.getElementById('tri-text'),chips=document.getElementById('tri-chips');
function esc(s){{return String(s).replace(/[&<>"]/g,function(c){{return{{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]}})}}
function setS(s){{S=s;Array.prototype.forEach.call(document.querySelectorAll('#tri-seg button'),function(b){{b.className=b.dataset.s===s?'on':'';}});
 chips.innerHTML=CH[s].map(function(c){{return '<button type="button">'+esc(c)+'</button>'}}).join('');
 Array.prototype.forEach.call(chips.querySelectorAll('button'),function(b){{b.addEventListener('click',function(){{inp.value=b.textContent;run();}});}});
 out.innerHTML='<span class="muted">—</span>';}}
var busy=false,sb=document.querySelector('#tri-form button');
function lock(on){{busy=on;sb.disabled=on;inp.disabled=on;sb.style.opacity=on?'.55':'';sb.style.cursor=on?'wait':'';Array.prototype.forEach.call(chips.querySelectorAll('button'),function(b){{b.disabled=on;}});}}
function run(){{var t=inp.value.trim();if(busy||t.length<3)return;lock(true);out.innerHTML='<span class="muted">'+T.wait+'</span>';
 fetch('https://api.mtlm-router.intrane.fr/demo/triage',{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify({{sector:S,text:t}})}})
 .then(function(r){{if(r.status===429)throw 'lim';return r.json()}}).then(function(d){{if(!d||!d.decision)throw 'err';
  var lab=d.decision==='auto'?T.auto:(d.decision==='autre'?T.autre:T.review),cl=d.decision==='auto'?'ok':'warn';
  var cat=d.decision==='autre'?'':'<div class="cat">'+esc(d.category)+'</div>';
  out.innerHTML='<div>'+cat+'<div class="verdict '+cl+'">'+lab+' <span class="muted" style="font-weight:400">· '+T.conf+' '+Math.round(d.confidence*100)+'%</span></div></div>';
  if(window.vigie)vigie('triage',{{sector:S,decision:d.decision,page:'tri-mail'}});
 }}).catch(function(e){{out.innerHTML='<span class="warn">'+(e==='lim'?T.lim:T.err)+'</span>';}}).then(function(){{lock(false);}});}}
Array.prototype.forEach.call(document.querySelectorAll('#tri-seg button'),function(b){{b.addEventListener('click',function(){{setS(b.dataset.s)}})}});
document.getElementById('tri-form').addEventListener('submit',function(e){{e.preventDefault();run();}});setS('transport');
var lf=document.getElementById('lead-form');lf.addEventListener('submit',function(ev){{ev.preventDefault();
 var msg=document.getElementById('lead-msg'),fd=new FormData(lf),f={{}};fd.forEach(function(v,k){{f[k]=v;}});if(f.website)return;delete f.website;
 var lb=lf.querySelector('button');if(lb.disabled)return;lb.disabled=true;lb.style.opacity='.55';msg.textContent=T.f_sending;
 fetch('https://bkn.intrane.fr/v1/hooks/forms',{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify({{form:'mtlm-leads',fields:f}})}})
 .then(function(r){{return r.json()}}).then(function(x){{if(x&&x.ok){{msg.textContent=T.f_ok;lf.reset();if(window.vigie)vigie('lead',{{form:'mtlm-leads',niche:'tri-mail'}});}}else{{msg.textContent=(x&&x.error)||T.f_ko;}}}})
 .catch(function(){{msg.textContent=T.f_ko;}}).then(function(){{lb.disabled=false;lb.style.opacity='';}});}});
document.addEventListener('click',function(e){{var t=e.target.closest('[data-track]');if(t&&window.vigie)vigie(t.getAttribute('data-track'),{{page:location.pathname}});}});
}})();
</script>
</body></html>
"""


if __name__ == "__main__":
    for k, f in (("fr", "inbox-fr.html"), ("en", "inbox.html")):
        open(os.path.join(ROOT, f), "w").write(page(k))
        print("wrote", f)
