# civic_fr v3 experiment — natural-phrasing augmentation (negative result)

Hypothesis (pass 27 finding): `civic_fr@0.1.1` is template-bound — corpus-like
phrasing routes correctly, natural French ("nid de poule", "lampadaire en
panne") lands `oos`. Paraphrase augmentation should fix coverage.

## What was tried

`civic_fr_natural_train.jsonl`: 71 hand-written natural-FR rows (~6/route,
colloquial phrasing, no template). `civic_fr_natural_eval.jsonl`: 22 held-out
natural probes, 2/route. Two fits via `emit_civic_fr_v3.py`:

| | v2 baseline (0.1.1) | v3 (+natural ×1) | v3w (+natural ×4) |
|---|---|---|---|
| in-scope acc (template holdout) | ~1.0 | 0.994 | 0.991 |
| OOS recall | **0.909** | 0.727 | 0.636 |
| id-OOS recall | 0.83 | 0.50 | **0.33** |
| far-OOS recall | 1.0 | 1.0 | 1.0 |
| natural-phrasing acc | — | 0.36 | 0.45 |
| natural → false-oos | — | 0.14 | 0.05 |

## Result

Not shipped. Natural rows buy ~+9–20% natural coverage but cost −20 to −50
points of id-OOS recall — the hard negatives (French mairie-adjacent OOS) sit
exactly where natural paraphrases live in the frozen feature space. A linear
head over pooled trunk features cannot separate "natural phrasing of a known
route" from "a different municipal topic we've never seen" — they are
literally the same neighborhood.

## What this means

- 0.1.1 remains the honest shipped head: it fails by *abstaining* on
  out-of-corpus phrasing (the designed failure mode), not by misrouting.
- Fixing natural coverage needs either (a) a much larger natural corpus
  (hundreds/route, real citizen mail), (b) a deeper head than linear, or
  (c) a trunk trained on more diverse French — none achievable by
  re-weighting 71 rows.
- Reproduce: `data/civic_fr_natural_*.jsonl` + `tools/emit_civic_fr_v3.py`
  (runs on rbm21, emits `civic_fr_v3_mt.head`, never packaged).
