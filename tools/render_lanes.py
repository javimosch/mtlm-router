"""render_lanes.py — generate site/lanes/<family>.html per lane from the catalog.

Programmatic per-lane pages: each lane family gets a standalone page with its
honest metrics, taxonomy chips, a pinned live playground (POST /demo/route with
expert=<lane>), install one-liner, and funnel CTAs. Vigie + data-track wired
like pricing.html/catalog.html.

Usage: python3 tools/render_lanes.py [--index URL|path] [--outdir site/lanes]
"""
import argparse, json, html, urllib.request, os, sys

INDEX = "https://raw.githubusercontent.com/javimosch/mtlm-heads/master/index.json"

# family -> deployed expert name on api.mtlm-router.intrane.fr + page copy.
# expert=None means the lane is not on the hosted demo (page renders without playground).
LANES_META = {
    "banking77": {
        "expert": "bank77",
        "title": "Banking support intent routing",
        "desc": "Routes banking customer-service messages into 50 typed intents (card issues, transfers, top-ups, FX) plus a calibrated out-of-scope refusal. Trained on the public banking77 corpus — the free proof lane for the format.",
        "examples": ["i was charged twice for the same thing", "how long until my new card arrives", "can i use apple pay with this account", "i lost my card, please block it"],
        "honest": "English benchmark phrasing, ~73% holdout. This is triage/routing with abstention, not autonomous resolution — a real deployment wants a private lane on your ticket taxonomy.",
    },
    "civic": {
        "expert": "civic",
        "title": "Civic issue reporting (English)",
        "desc": "Routes citizen reports — potholes, graffiti, missed bins, street lighting — into a municipal action taxonomy with abstention on out-of-scope requests.",
        "examples": ["there is a huge pothole on main street", "graffiti on the library wall", "my recycling bin was not collected"],
        "honest": "Synthetic corpus; live-verified. English counterpart of civic_fr.",
    },
    "civic_fr": {
        "expert": "civic_fr",
        "title": "Signalement municipal (français)",
        "desc": "Trie les signalements citoyens en français — lampadaire en panne, nid de poule, dépôt sauvage, encombrants — vers une taxonomie d'actions municipales, avec refus calibré hors-scope.",
        "examples": ["le lampadaire de ma rue est en panne", "il y a un nid de poule devant chez moi", "quelqu'un a deposé un canapé sur le trottoir", "la poubelle jaune n'a pas été ramassée"],
        "honest": "Natural-phrasing augmented v3w head (110 handwritten rows): 22/22 on natural probes, calibrated qhat 0.746. French only.",
    },
    "clinc150": {
        "expert": "clinc",
        "title": "Generic intent routing — 150 classes",
        "desc": "Broad-domain intent classification from the public clinc150 corpus — 150 routes plus out-of-scope detection. The widest free lane; shows clarification candidates when the top routes are close.",
        "examples": ["what's my account balance", "transfer 50 euros to marie", "book a table for two tonight"],
        "honest": "74% holdout on 151 routes — wide taxonomy means clarification-first behavior on real traffic (delegates with ranked candidates rather than guessing).",
    },
    "eq_tone": {
        "expert": "eq",
        "title": "Email tone triage (demo)",
        "desc": "Classifies the tone of short workplace messages — angry, neutral, pleased, urgent, informative. Honest demo lane: kept to show what a partial lane looks like.",
        "examples": ["this is the third time i'm reporting this issue", "thanks so much for the quick fix", "please review when you have a moment"],
        "honest": "~50% accuracy — the trunk ceiling for 6-way tone at 7M params. Triage-only at conf≥0.9 (~5% automation). A v3 retrain was evaluated and rejected. Not for production.",
    },
    "helpdesk": {
        "expert": "helpdesk2",
        "title": "IT helpdesk routing",
        "desc": "Routes IT support requests — account unlock, password reset, hardware, VPN, provisioning — into a small internal-ops taxonomy.",
        "examples": ["unlock carol's account, she can't log in", "my vpn keeps dropping every hour", "provision a laptop for the new intern"],
        "honest": "Small synthetic taxonomy, live-verified. Good narrow-lane demo: high automation when the domain matches.",
    },
    "pii": {
        "expert": "pii",
        "title": "PII & contact-detail detection",
        "desc": "Flags personal data in user content — emails, phone numbers (incl. 'at dot com' and spelled digits), IBANs, card numbers, French SSN — plus off-platform handoff attempts (Telegram/WhatsApp/Insta handles). GDPR-flavored lane for forums, comments and marketplace uploads.",
        "examples": ["call me on 06 12 34 56 78 please", "my email is jane dot doe at gmail dot com", "add me on telegram @nightowl99", "order 458721 shipped yesterday"],
        "honest": "Synthetic-injection corpus (PII patterns in real comment text) + hand-written eval incl. obfuscation. 85.8% in-scope / 95.7% OOS on holdout, 90% on natural phrasings. Surface-pattern lane — semantic harm categories (hate, harassment) were evaluated and deliberately NOT shipped: the trunk ceiling is ~60% there.",
    },
    "pii_rules": {
        "expert": "piirules",
        "title": "PII detection — deterministic rules",
        "desc": "Model-free PII lane: IBAN mod-97, Luhn-validated card numbers, 9+-digit phone runs, email regex, domain blocklists. Deterministic verdicts at ~zero inference cost — no forward pass at all. On prod it's wired as a hybrid: rules fire first, the `pii` head handles the fuzzy phrasings.",
        "examples": ["call me on 06 12 34 56 78 please", "virement FR14 2004 1010 0505 0001 3M02 606", "card 4111 1111 1111 1111 declined", "order 458721 shipped yesterday"],
        "honest": "Rules pack, not a learned head — exact patterns are provable, but fuzzy/obfuscated phrasing ('jane dot doe at gmail dot com') falls through to the fallback head or to none. Ship both `pii` (head) + `pii_rules` (rules) together: rules catch the exact shapes, the head catches the fuzz.",
    },
    "link_safety": {
        "expert": "link_safety",
        "title": "Unsafe-link detection",
        "desc": "Flags risky links in user content: phishing phrasing, adult/gambling patterns, and a domain blocklist. Zero model cost — a pure rules lane that scales to million-row blocklists via hash-set lookup. GDPR-friendly: everything stays on your box.",
        "examples": ["click http://phishing.test to verify your account", "visit casino-online.example for free spins", "my site is example.com", "order shipped via colissimo.fr"],
        "honest": "Demo blocklist ships ~7 domains — production deployments fetch HaGeZi feeds at install time (GPL, never shipped in a pack). Covers the link surface, not semantic toxicity.",
    },
    "mod_policy": {
        "expert": "mod_policy",
        "title": "Moderation policy layer (score-consumer)",
        "desc": "The decision layer over YOUR scorer: post category scores {nudity, violence, drugs, self_harm, scam} from any upstream model — SightEngine, SigLIP, openmod, your own ONNX — and get a calibrated publish/review/remove/unchecked verdict. Threshold policy is a rules file you own; absent inputs escalate instead of silently passing.",
        "examples": ["scores: nudity 0.82 -> remove", "scores: nudity 0.4, violence 0.1 -> review", "scores: violence 0.05, nudity 0.02 -> publish"],
        "honest": "Demo thresholds are hand-authored — production deployments tune the rule file to their own scorer's score distribution (that's the €149 custom-lane job). This is the honest image-moderation path: your scorer does pixels, mtlm owns the typed verdict.",
    },
    "profanity": {
        "expert": "profanity",
        "title": "Profanity / obscene-term detection",
        "desc": "Wordlist lane over 403 terms (LDNOOBW public list): 'clean' vs 'profane' in ~0ms with zero model cost. The deobfuscation layer catches obfuscation for free — 'f u c k', 'sh1t', 'FvCk', 'a$$hole' all resolve to the listed term before matching.",
        "examples": ["this is a clean comment", "you absolute asshole", "what the f u c k", "have a nice day"],
        "honest": "Single-token wordlist matching — obfuscation-normalized, but morphological variants that aren't in the list ('fucking', 'phuck') can miss. Multiword list entries can't fire yet. Wordlist = transparent coverage: you can see and extend every term it checks.",
    },
    "scam_detect": {
        "expert": "scam_detect",
        "title": "Scam & fraud phrasing detection",
        "desc": "Classifies messages as 'clean', 'suspicious' or 'scam' over classic fraud shapes: lottery/prize, crypto-doubling, gift-card demands, IRS/impersonation, advance-fee openers. 'suspicious' is the honest middle tier — soft signals like urgency language escalate rather than convict.",
        "examples": ["CONGRATULATIONS you have WON the lottery prize", "send 0.5 BTC to double your bitcoin", "pay the irs warrant fee in gift cards", "your package arrived, track it here"],
        "honest": "Pattern detection, not semantic fraud analysis — formulaic scams catch at 0.9+, novel phrasing can miss (that's what 'suspicious' + the abstention path are for). Complements, doesn't replace, real anti-fraud tooling.",
    },
    "disposable_email": {
        "expert": "disposable_email",
        "title": "Disposable-email detection",
        "desc": "Flags throwaway/temp-mail addresses — the signup-fraud lane. 9,925-domain public blocklist; the email's domain is extracted from the text and matched (with parent-suffix walk), so 'bob@mailinator.com' flags while real providers pass.",
        "examples": ["signup bob@mailinator.com now", "register alice@gmail.com", "contact me at x@10minutemail.com"],
        "honest": "Coverage = the public blocklist's coverage — new disposable providers appear weekly and the list lags. Refresh it like any feed; a miss here is a list gap, not a model error.",
    },
    "mod_text": {
        "expert": "mod_text",
        "title": "All-in-one text moderation",
        "desc": "One request → the full text-moderation verdict across 17 classes: self-harm, extremism, scam, harassment, PII (email/phone/IBAN/card/crypto), unsafe links, spam, profanity — severity-ordered so the worst violation wins. 'matched_rule' names the firing check.",
        "examples": ["i want to die", "white power slogans", "send 0.5 BTC to double your bitcoin", "call me 0612345678", "a perfectly normal comment"],
        "honest": "Pattern coverage, not semantic moderation — it catches what its rules describe (deterministic, auditable, extendable) and doesn't pretend to understand context the way a big guard model does. That's the honest contract.",
    },
    "extremism": {
        "expert": "extremism",
        "title": "Extremist content & calls to violence",
        "desc": "Flags explicit extremist shapes — calls to violence, glorification, coded term lists — as 'extremist' vs 'clean' at ~0ms. Regex for kill/bomb/praise shapes, a curated term list for org names, and the 'phrases' kind catches multiword terms like 'white power'.",
        "examples": ["kill the infidels", "praise isis forever", "white power slogans", "i love my community"],
        "honest": "No canonical public extremism wordlist exists — this pack is hand-authored call-to-violence patterns plus a curated term list. It catches explicit phrasing; coded/dogwhistle language is a model problem, not a rules one. Multiword terms now catch via the 'phrases' kind.",
    },
    "self_harm": {
        "expert": "self_harm",
        "title": "Self-harm & distress signals",
        "desc": "Flags explicit self-harm / suicidal-ideation phrasing as 'self_harm' vs 'clean' at ~0ms. Context-anchored patterns — 'suicide squad' and colloquial use stay clean while 'i want to die' and 'thinking about suicide methods' flag.",
        "examples": ["i want to die", "thinking about suicide methods", "im going to end it all tonight", "i want to watch suicide squad"],
        "honest": "A triage signal, never an autonomous verdict on someone's welfare — every hit should escalate for human review. Coverage is explicit anchored phrasing; implicit or veiled distress is a different problem. Carefully tuned against colloquial false positives.",
    },
    "spam": {
        "expert": "spam",
        "title": "Spam / promo-blast detection",
        "desc": "Flags pharma/casino/SEO/promo spam shapes at ~0ms — regexes for pharma/casino/SEO formulas plus a classic spam-phrase list; the leet fold catches 'v1agra'-style evasion.",
        "examples": ["buy cheap v1agra online no prescription", "free money work from home now", "claim your casino bonus free spins", "nice article, very helpful"],
        "honest": "Classic keyword/phrase coverage — catches formulaic spam; sophisticated spam is a model problem. Phrase tier at 0.75 flags softer promo-speak.",
    },
    "harassment": {
        "expert": "harassment",
        "title": "Harassment & directed abuse",
        "desc": "Flags directed abuse — you-anchored insults ('you are stupid'), threats ('i will kill you'), dismissal ('shut up') — distinct from profanity's vocabulary focus: harassment is target-directed. ~0ms.",
        "examples": ["you are stupid and pathetic", "i will kill you", "shut up loser", "have a great day"],
        "honest": "Covers direct second-person abuse formulas — the most common harassment shape in comment spam. Sarcasm, context-dependent abuse, and third-person targeting are model problems; this is the deterministic first pass.",
    },
    "drugs": {
        "expert": "drugs",
        "title": "Drug-deal / slang detection",
        "desc": "Flags acquisition and sale-context drug phrasing — 'buy weed', 'need a plug', 'score some molly' — while medical use ('prescribed', 'medication') stays clean. ~0ms.",
        "examples": ["buy weed online cheap", "need a plug for the weekend", "my doctor prescribed xanax", "pickup some molly for the party"],
        "honest": "Catches deal/sale phrasing, not pharmacology discussion — 'my doctor prescribed xanax' is clean by design. The hard part is distinguishing context; that's why it's anchored to transaction verbs, not drug names alone.",
    },
    "nsfw": {
        "expert": "nsfw",
        "title": "Explicit / adult-content detection",
        "desc": "Flags explicit-content references — adult sites, escort services, 'send nudes' solicitation — as 'nsfw' vs 'clean' at ~0ms. Separate from link_safety's adult-domain check: this catches the phrasing even without a URL.",
        "examples": ["check out this porn site", "free onlyfans content", "send nudes pls", "watch the movie tonight"],
        "honest": "Direct-reference detection — catches explicit phrasing; euphemism, context, and implication are model problems. link_safety covers the *link* side of adult content; this covers the text itself.",
    },
    "hate": {
        "expert": "hate",
        "title": "Hate speech & dehumanization",
        "desc": "Flags hate-speech shapes — ethnic-cleansing calls, dehumanizing terms ('subhuman', 'vermin'), glorification markers ('heil hitler', 'race war') — while political disagreement stays clean. ~0ms.",
        "examples": ["kill all the immigrants", "heil hitler", "i disagree with their policies", "those filthy subhuman parasites"],
        "honest": "Targets hate SPEECH, not opinions — 'i disagree with their policies' is clean by design. Anchored to dehumanization and violence shapes, not ideology terms alone.",
    },
    "violence": {
        "expert": "violence",
        "title": "Threats & graphic violence",
        "desc": "Flags explicit threat and violence phrasing — 'im going to kill you', 'i want to stab someone' — while contextual mentions ('action movie violence') stay clean. Anchored to threat verbs, not the word 'violence'.",
        "examples": ["im going to kill you tonight", "i want to stab someone", "the action movie had violence", "i will stab anyone who tries"],
        "honest": "Covers direct threat formulas and graphic-violence references — the last mod_policy 'unchecked' category with a text lane. Distinct from extremism (ideological) and harassment (abuse): this is raw physical-harm signal.",
    },
}

CARD_STYLE = "bg-gray-900 border border-gray-800 rounded-xl p-6"


def esc(s): return html.escape(str(s), quote=True)


def lane_page(name, lane, meta):
    ver = esc(lane["version"]); fam = esc(name)
    acc = lane.get("holdout_acc")
    op = lane.get("operating") or {}
    tax = lane.get("taxonomy") or []
    expert = meta.get("expert")
    chips = "".join(
        f'<button type="button" class="lp-chip text-xs bg-gray-800 border border-gray-700 text-gray-300 rounded-full px-3 py-1 hover:border-cyan-700">{esc(q)}</button>'
        for q in meta["examples"])
    tax_chips = ", ".join(esc(t) for t in tax[:16]) + (" …" if len(tax) > 16 else "")
    metrics = []
    if acc is not None:
        metrics.append(f"holdout <strong>{acc*100:.1f}%</strong> (n={lane.get('n_holdout','?')})")
    if op.get("min_conf") is not None:
        metrics.append(f"floor conf≥{op['min_conf']}")
    if op.get("qhat") is not None:
        metrics.append(f"qhat {op['qhat']}")
    oo = lane.get("oos") or {}
    if isinstance(oo.get("oos_recall"), (int, float)):
        metrics.append(f"oos recall {oo['oos_recall']*100:.0f}%")
    status = lane.get("status", "demo")
    badge = ("free · certified", "text-green-300 border-green-800 bg-green-950") if status == "certified" \
        else ("free · demo", "text-amber-300 border-amber-800 bg-amber-950")
    playground = ""
    if expert:
        playground = f"""
<div class="{CARD_STYLE} mb-8" id="try">
  <h2 class="text-lg font-bold mb-1">Try it live — pinned to <span class="mono text-cyan-300">expert:"{esc(expert)}"</span></h2>
  <p class="text-gray-500 text-sm mb-4">Free demo endpoint, no signup. Same call your agent would make.</p>
  <form id="lp-form" class="flex gap-2">
    <input id="lp-in" type="text" maxlength="300" placeholder="{esc(meta['examples'][0])}" class="flex-1 bg-gray-950 border border-gray-700 rounded-lg px-4 py-3 text-gray-100 placeholder-gray-600 focus:outline-none focus:border-cyan-600" autocomplete="off">
    <button type="submit" class="bg-cyan-700 text-white px-5 py-3 rounded-lg font-medium hover:opacity-90">Decide</button>
  </form>
  <div class="flex flex-wrap gap-2 mt-3">{chips}</div>
  <div id="lp-out" class="mt-4 hidden">
    <div class="grid sm:grid-cols-4 gap-3 text-center">
      <div class="bg-gray-950 border border-gray-800 rounded-lg p-3"><div class="text-xs text-gray-500">route</div><div id="lp-route" class="mono text-cyan-300 text-lg"></div></div>
      <div class="bg-gray-950 border border-gray-800 rounded-lg p-3"><div class="text-xs text-gray-500">confidence</div><div id="lp-conf" class="mono text-lg"></div></div>
      <div class="bg-gray-950 border border-gray-800 rounded-lg p-3"><div class="text-xs text-gray-500">action</div><div id="lp-action" class="mono text-lg"></div></div>
      <div class="bg-gray-950 border border-gray-800 rounded-lg p-3"><div class="text-xs text-gray-500">set · ms</div><div id="lp-meta" class="mono text-lg"></div></div>
    </div>
    <p id="lp-note" class="text-gray-500 text-xs mt-3 text-center"></p>
  </div>
  <p id="lp-err" class="text-red-400 text-sm mt-3 hidden"></p>
</div>"""
    playground_js = ""
    if expert:
        playground_js = f"""
<script>
var LP_EXPERT={json.dumps(expert)},LP_LANE={json.dumps(name)};
function lpTrack(ev,props){{if(window.vigie){{props.lane=LP_LANE;vigie(ev,props);}}}}
document.querySelectorAll('.lp-chip').forEach(function(b){{b.addEventListener('click',function(){{document.getElementById('lp-in').value=b.textContent;lpTrack('lane_demo_chip',{{chip:b.textContent}});}});}});
document.getElementById('lp-form').addEventListener('submit',function(e){{
  e.preventDefault();
  var s=document.getElementById('lp-in').value.trim();if(!s)return;
  lpTrack('lane_demo_try',{{}});
  fetch('https://api.mtlm-router.intrane.fr/demo/route',{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify({{state:s,expert:LP_EXPERT}})}})
   .then(function(r){{return r.json().then(function(d){{return{{ok:r.ok,d:d}};}});}})
   .then(function(res){{
     var d=res.d;
     if(!res.ok||d.error){{var m=(d.error&&d.error.message)||('http '+res.status);document.getElementById('lp-err').textContent=m;document.getElementById('lp-err').classList.remove('hidden');lpTrack('lane_demo_error',{{error:m}});return;}}
     document.getElementById('lp-err').classList.add('hidden');
     document.getElementById('lp-out').classList.remove('hidden');
     document.getElementById('lp-route').textContent=d.route||'—';
     document.getElementById('lp-conf').textContent=(d.confidence!=null?d.confidence.toFixed(2):'—');
     document.getElementById('lp-action').textContent=d.action||'—';
     document.getElementById('lp-meta').textContent=(d.set_size!=null?'set '+d.set_size:'—')+' · '+(d.latency_ms!=null?d.latency_ms+'ms':'');
     var cands=(d.candidates||[]).map(function(c){{return c.route;}}).slice(0,3).join(', ');
     document.getElementById('lp-note').textContent=d.action==='delegate'&&cands?('clarify: '+cands):(d.action==='delegate'?'delegated — out of scope or low confidence':'automated — singleton set, tool-fill ready');
     lpTrack('lane_demo_result',{{action:d.action,route:d.route,set_size:d.set_size}});
   }})
   .catch(function(err){{document.getElementById('lp-err').textContent='network error — demo may be rate-limited';document.getElementById('lp-err').classList.remove('hidden');lpTrack('lane_demo_error',{{error:'network'}});}});
}});
</script>"""
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(meta['title'])} — mtlm-router lane {fam}</title>
<meta name="description" content="{esc(meta['desc'][:155])}">
<link rel="canonical" href="https://mtlm-router.intrane.fr/lanes/{fam}.html">
<script type="application/ld+json">{{
 "@context":"https://schema.org","@type":"SoftwareApplication",
 "name":"mtlm-router {fam} lane","applicationCategory":"DeveloperApplication",
 "operatingSystem":"any (CPU)","offers":{{"@type":"Offer","price":"0","priceCurrency":"EUR"}},
 "description":{json.dumps(meta['desc'][:300])},
 "url":"https://mtlm-router.intrane.fr/lanes/{fam}.html",
 "downloadUrl":{json.dumps(lane.get("url",""))},
 "softwareVersion":{json.dumps(lane["version"])},"license":"Apache-2.0",
 "author":{{"@type":"Organization","name":"intrane","url":"https://mtlm-router.intrane.fr"}}
}}</script>
<script type="application/ld+json">{{
 "@context":"https://schema.org","@type":"BreadcrumbList",
 "itemListElement":[{{"@type":"ListItem","position":1,"name":"mtlm-router","item":"https://mtlm-router.intrane.fr/"}},
 {{"@type":"ListItem","position":2,"name":"catalog","item":"https://mtlm-router.intrane.fr/catalog.html"}},
 {{"@type":"ListItem","position":3,"name":{json.dumps(name)},"item":"https://mtlm-router.intrane.fr/lanes/{fam}.html"}}]
}}</script>
<script src="https://cdn.tailwindcss.com"></script>
<script defer src="https://vigie.intrane.fr/vigie.js" data-site="mtlm-router.intrane.fr"></script>
<style>.mono{{font-family:ui-monospace,monospace}}body{{background:#030712;color:#d1d5db}}</style></head>
<body class="max-w-4xl mx-auto px-6 py-14">
<script>document.addEventListener('DOMContentLoaded',function(){{if(window.vigie)vigie('lane_page_view',{{lane:{json.dumps(name)}}});}});</script>
<p class="mono text-xs text-gray-500 mb-2"><a href="/" class="text-cyan-400 hover:underline">mtlm-router</a> / <a href="/catalog.html" class="text-cyan-400 hover:underline">catalog</a> / {fam}</p>
<p class="mono text-xs text-gray-600 mb-2">a lane is a rules.json or .head pack — <a href="https://github.com/javimosch/machin-anvil/blob/master/RULEPACK.md" class="text-cyan-500 hover:underline">write your own (RULEPACK.md)</a></p>
<div class="flex items-baseline justify-between mb-2">
  <h1 class="text-3xl font-bold">{esc(meta['title'])}</h1>
  <span class="mono text-xs px-2 py-1 rounded border {badge[1]}">{badge[0]}</span>
</div>
<p class="mono text-gray-500 text-sm mb-6">{fam}@{ver} · {lane.get('classes', len(tax))} routes</p>
<p class="text-gray-400 text-sm mb-4">{esc(meta['desc'])}</p>
<p class="text-gray-300 text-sm mb-8">{' · '.join(metrics) if metrics else ''}</p>
{playground}
<div class="{CARD_STYLE} mb-8">
  <h2 class="text-lg font-bold mb-2">Taxonomy ({len(tax)} routes)</h2>
  <p class="mono text-gray-400 text-sm">{tax_chips}</p>
</div>
<div class="{CARD_STYLE} mb-8">
  <h2 class="text-lg font-bold mb-2">Honest limits</h2>
  <p class="text-gray-400 text-sm">{esc(meta['honest'])}</p>
</div>
<div class="{CARD_STYLE} mb-8">
  <h2 class="text-lg font-bold mb-2">Install</h2>
  <pre class="mono text-xs bg-gray-950 border border-gray-800 rounded p-3 overflow-x-auto">python3 tools/lane_install.py {fam}@{ver} --apply --appliance .
{'python3 tools/lane_repro.py ' + fam + '-' + ver + '.lanepack.tar.gz --url http://localhost:8402   # re-run the published eval yourself' if lane.get('eval_sample') else ''}</pre>
  <p class="text-gray-600 text-xs mt-2 mono">sha256: {esc(lane.get('sha256',''))[:24]}… · Apache-2.0 · <a data-track="lane_pack_dl" href="{esc(lane.get('url',''))}" class="text-cyan-400 hover:underline">download lanepack</a></p>
</div>
<div class="bg-gray-900 border border-cyan-800 rounded-xl p-6">
  <div class="mono text-cyan-300 text-sm mb-1">NEED YOUR OWN ROUTES?</div>
  <p class="text-gray-400 text-sm mb-4">A private lane on your taxonomy — trained, calibrated, exclusive. €149 / domain, 3 business days.</p>
  <a data-track="cta_custom_lane" href="/custom-lane.html?lane={fam}" class="inline-block bg-cyan-700 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-cyan-600">Get a lane like this</a>
  <a data-track="cta_pricing" href="/pricing.html" class="inline-block text-cyan-400 text-sm hover:underline ml-4">pricing →</a>
</div>
<p class="text-center text-gray-600 text-xs mt-14">generated by tools/render_lanes.py · source: <a href="{INDEX}" class="text-cyan-400 hover:underline mono">index.json</a></p>
<script>document.addEventListener('click',function(e){{var t=e.target.closest('[data-track]');if(t&&window.vigie)vigie(t.getAttribute('data-track'),{{href:t.getAttribute('href')||'',page:location.pathname}});}});</script>
{playground_js}
</body></html>"""


def hub(families):
    rows = "".join(
        f'<div class="{CARD_STYLE}"><div class="flex items-baseline justify-between"><a href="/lanes/{esc(n)}.html" class="mono text-lg text-cyan-300 hover:underline">{esc(n)}</a><span class="text-gray-500 text-xs mono">{esc(LANES_META[n]["title"])}</span></div></div>'
        for n in families)
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lanes — mtlm-router</title><script src="https://cdn.tailwindcss.com"></script>
<script defer src="https://vigie.intrane.fr/vigie.js" data-site="mtlm-router.intrane.fr"></script>
<style>.mono{{font-family:ui-monospace,monospace}}body{{background:#030712;color:#d1d5db}}</style></head>
<body class="max-w-4xl mx-auto px-6 py-14">
<p class="mono text-xs text-gray-500 mb-2"><a href="/" class="text-cyan-400 hover:underline">mtlm-router</a> / lanes</p>
<h1 class="text-3xl font-bold mb-2">Lane pages</h1>
<p class="text-gray-400 text-sm mb-8">One page per lane family — live demo, honest metrics, install one-liner.</p>
<div class="space-y-4">{rows}</div>
<p class="text-center text-gray-600 text-xs mt-14">generated by tools/render_lanes.py</p>
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default=INDEX)
    ap.add_argument("--outdir", default="site/lanes")
    a = ap.parse_args()
    raw = urllib.request.urlopen(a.index).read() if a.index.startswith("http") else open(a.index, "rb").read()
    lanes = json.loads(raw)["lanes"]
    vkey = lambda l: [int(x) for x in l["version"].split(".")]
    latest = {}
    for l in lanes:
        if l.get("yanked") or l["name"] not in LANES_META:
            continue
        cur = latest.get(l["name"])
        if cur is None or (l.get("live_verified"), vkey(l)) > (cur.get("live_verified"), vkey(cur)):
            latest[l["name"]] = l
    os.makedirs(a.outdir, exist_ok=True)
    written = []
    for name in sorted(latest):
        path = os.path.join(a.outdir, name + ".html")
        open(path, "w").write(lane_page(name, latest[name], LANES_META[name]))
        written.append(path)
    open(os.path.join(a.outdir, "index.html"), "w").write(hub(sorted(latest)))
    base = "https://mtlm-router.intrane.fr"
    urls = ["/", "/fr.html", "/docs.html", "/catalog.html", "/pricing.html",
            "/vs-llm-routing.html",
            "/custom-lane.html",
            "/inbox.html", "/inbox-fr.html", "/municipal.html", "/municipal-fr.html",
            "/lanes/index.html"] + ["/lanes/%s.html" % n for n in sorted(latest)]
    sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sm += "".join("  <url><loc>%s%s</loc></url>\n" % (base, u) for u in urls)
    sm += "</urlset>\n"
    smap = os.path.join(os.path.dirname(a.outdir.rstrip("/")), "sitemap.xml")
    open(smap, "w").write(sm)
    print(json.dumps({"pages": written, "hub": a.outdir + "/index.html", "sitemap": smap}))


if __name__ == "__main__":
    main()
