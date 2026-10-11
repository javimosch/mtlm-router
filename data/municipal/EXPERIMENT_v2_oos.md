# mairie v2/v3/v4 — adding an `oos` class: experiment log

## Goal

Shipped `mairie_mt3.head` (16 sanitation routes, no `oos` class) leaks ~43% of
municipal-adjacent out-of-scope requests into confident routes (measured by
`tools/oos_eval_mairie.py` and replicated here on a 30-row held-out set).
Fix attempted: retrain with an explicit `oos` class fed by hard negatives.

## Data

- `data/mairie_oos_train.jsonl` — 215 handwritten French municipal-adjacent
  negatives (état civil, urbanisme, bruit, stationnement, voirie, social,
  scolaire…) — the exact space the old head leaked into.
- `data/mairie_oos_eval.jsonl` — 30 held-out negatives, same style.
- Train corpora tried: `municipal12_train` (5.8k), `municipal12_train_aug`
  (13.4k synthetic-augmented), `municipal_train` (5.8k original, granular
  labels merged via MERGE map in emit_mairie_v4.py).

## Results (holdout = municipal12_holdout.jsonl, 633 rows)

| head | taps | corpus | in_scope full | in_scope clean (95) | oos recall | leak |
|---|---|---|---|---|---|---|
| mairie_mt3 (shipped) | 3×max {2,4,3} | ? | .946 | .968 | — | .43 |
| v2 mean | 3×mean | base | .780 | — | 1.00 | .00 |
| v2 max | 3×max {2,4,3} | base | .801 | — | 1.00 | .00 |
| v3 sklearn | 3×max | aug | .809/.814 | .789 | .967 | .00 |
| v4 sklearn C=.01 | 3×max | orig merged | .894 | .789 | 1.00 | .00 |

## Holdout contamination finding

`municipal12_holdout.jsonl` is NOT clean: 536/633 rows appear verbatim in
`municipal_train.jsonl`, 104 in `municipal_holdout.jsonl`. Only **95 rows are
uncontaminated** for a head trained on the original corpus (13 for the 12-*
corpora). Any historical mairie holdout number must be read through this.
Clean-subset indices: `/tmp/clean_idx.json` on rbm21.

## What the gap is NOT

Ruled out: tap choice, pooling kind, corpus size/augmentation, optimizer
convergence (sklearn converged train 94% still 81% holdout), label
granularity, exact-match holdout leakage (clean subset shows same gap).

Remaining hypothesis: the shipped head's recipe had a detail we could not
reconstruct (extraction-time preprocessing or a different training row mix);
its W remains compatible with current features (94.6% under head_io-evaluated
DECIDE_SYS extraction).

## Decision

**Do not replace.** v4 buys zero OOS leak at a real ~18pt clean-holdout
in-scope cost (95 rows — noisy but consistent across all retrained variants).
Shipped head stays live; `mairie_v4_mt.head` kept on rbm21
(`/root/mtlm/models/`) as the OOS-correct fallback if the operator prefers the
abstention-first posture. Revisit if the original emit recipe is recovered.
