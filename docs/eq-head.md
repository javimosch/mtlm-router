# EQ head — emotional-state classification over the frozen trunk

Status: experiment (GoEmotions, 5-bucket coarse taxonomy).

## Why

An emotion head is a second typed signal next to intent routing: a cheap LLM
can't reliably read tone, and doing it by generation is slow, inconsistent, and
can't abstain. A `.head` over the frozen trunk gives `{emotion, confidence}` in
milliseconds — the same "doesn't guess" property as the router.

The pitch: **the model that reads the room before your chatbot answers.** EQ is
a live trend (e.g. Instinct); our differentiator is typed sidecar signals
(intent, emotion, confidence) that run self-hosted on CPU, not a hosted EQ API.

## Label space (v1)

GoEmotions' 27 emotions + neutral are finer than a support/care product needs.
Mapped to 5 buckets:

| bucket | GoEmotions labels |
|---|---|
| `frustrated` | anger, annoyance, disapproval, disgust |
| `distressed` | disappointment, embarrassment, fear, grief, nervousness, remorse, sadness |
| `confused` | confusion, curiosity, realization, surprise |
| `positive` | admiration, amusement, approval, caring, desire, excitement, gratitude, joy, love, optimism, pride, relief |
| `neutral` | neutral |

Multi-label rows are kept only when all labels map to the same bucket
(rater agreement). Corpus: 39,720 train / 4,965 dev / 4,995 test.

## Product surface

`POST /v1/assess` (or the generic head endpoint) returns the bucket +
calibrated confidence. Downstream contract:

```
user msg ─┬─► gate head   → which expert/lane
          ├─► eq head     → {emotion, confidence}
          └─► route head  → intent
                 │
        context = {route, emotion, confidence}
                 ▼
          cheap LLM / tool / human
```

- `frustrated`/`distressed` @ high conf → de-escalation context or human lane
- `confused` → clarify-first prompting
- low confidence → do not inject emotional context (abstain)
- two heads, one frozen trunk — stock MoE pattern

## Results (v1, mean@-4, router3 trunk)

5-way holdout: **55.6%** (majority baseline ~37%), temp 0.95, 11 conf-wrong.

| bucket | holdout acc | n |
|---|---|---|
| positive | 74.0% | 1863 |
| neutral | 64.4% | 1606 |
| confused | 30.1% | 488 |
| distressed | 24.6% | 366 |
| frustrated | 19.2% | 672 |

Negative emotions collapse mostly into `neutral`/`positive` — the head misses
upset users, the worst failure mode for the product pitch.

Negativity flag (binary refits on the same features):

| positive set | thr | prec | rec |
|---|---|---|---|
| frustrated | 0.5 | 0.61 | 0.06 |
| frustrated+distressed | 0.5 | 0.62 | 0.18 |
| frustrated+distressed | 0.7 | 0.85 | 0.05 |
| +confused | 0.5 | 0.64 | 0.35 |

Reading: detectable but weak at layer -4 mean pooling — high-precision at low
recall (when it does fire at 0.7+, it's usually right).

## Full sweep (verdict)

All 12 (layer, pooling) combos were extracted and refit:

| combo | 5-way | neg_prec | neg_rec |
|---|---|---|---|
| (-4, mean) | 0.556 | 0.62 | 0.18 |
| (-3, mean) | 0.553 | 0.63 | 0.16 |
| (-2, mean) | 0.551 | 0.65 | 0.16 |
| (-1, last) | 0.507 | 0.70 | 0.12 |
| others | 0.48–0.51 | 0.50–0.70 | 0.03–0.13 |

**Verdict: parked.** No layer/pooling unlocks emotion on this trunk — the
frozen 7M encodes "what action" (it was trained on routing/instruction data),
not "how the user feels". An EQ head would need trunk fine-tuning on emotional
text, or a different backbone. The sidecar-signals architecture (intent +
confidence + emotion injected as context) remains a good product shape; EQ is
the part that doesn't clear the bar today.

## Known limits

- GoEmotions is Reddit English; French and domain-specific tone will shift.
- Emotion labels are annotator-subjective; ~60-70% is a realistic ceiling for
  coarse buckets (BERT gets avg F1 .46 on the full 27-way taxonomy).
- Head trained on router3 features is trunk-bound; re-emit against router9 for
  production use.
