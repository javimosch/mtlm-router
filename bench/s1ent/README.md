# s1ent — trained entailment scoring for /v1/systemone (negative result)

Question: can a trained head on the frozen 7M trunk score `State / Question /
Option / Correct?` well enough to replace raw logprob candidate scoring?

## v1 — random negatives, 1:4 imbalance (2026-10-09)

7.5k CLINC150 rows, all tap configs → balanced acc **0.50** on every config.
Majority-class collapse; reported 81.8% acc was the class prior. Head emitted
but not shipped (`s1ent_mt3.head` on rbm21, unused).

## v2 — balanced, hard negatives (this dir)

`gen_s1hard.py` builds 2,400 balanced train rows (pos + sibling-token hard neg)
and 4,500 eval rows grouped into 900 five-way questions (gold + 4 hard negs).
`s1hard.py` fits LR on pooled taps and reports bacc + ranking top-1.

| taps | bacc | top1 | top2 |
|---|---|---|---|
| mean@-2,-3,-4 | 0.532 | 27.2% | 54.4% |
| max@-4,-2,-3 | **0.596** | **40.0%** | 66.6% |

Chance: 20% top1. Verdict: the trunk's pooled features carry *weak* entailment
signal — hard negatives unblock learning vs the imbalanced run — but 40% top1
on hard-negative 5-way is not a scorer we ship. `ANVIL_S1_HEAD` stays wired as
the hook if a future trunk/head closes the gap. Runtime default remains raw
logprob scoring.
