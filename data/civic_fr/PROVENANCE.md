# civic_fr lane corpus — provenance

Taxonomy: real DansMaRue (Mairie de Paris) type/soustype labels via
opendata.paris.fr API (ODbL), grouped into 11 canonical FR routes.

Utterances: SYNTHETIC — tools/build_civic_fr.py fills French citizen-report
templates with real soustype phrases and location slots (20 templates ×
phrases × 20 locations, seed 23, deduped). DansMaRue publishes no free text
(Pittsburgh 311 and DansMaRue are both structured-only — recorded dead end).

Status: honest DEMO lane. Numbers on the synthetic holdout do not certify
production behavior — for that it needs real signalement text (client export).
train.jsonl 1320 rows / holdout.jsonl 330 rows, 80/20 per-route, 11 routes.
