# eq — GoEmotions tone lane (2026-10-10)

Source: google-research GoEmotions (Reddit comments, 28 emotions, Apache-2.0).
Raw files: train.tsv / dev.tsv / test.tsv (label ids index emotions.txt,
Reddit comment ids in col 3). eq_*.jsonl = 28 labels merged into 5 tone
superclasses (own mapping): positive / neutral / frustrated / confused /
distressed. 39,720 train / 4,965 dev / 4,995 test.

Training: tools/emit_eq.py (runs on rbm21, torch 2.14 CPU, hf/router3s384
export). Balanced 2500/class train subsample; taps/l2 swept on dev; test is a
pure holdout. Best: mean@-2,-3,-4, l2=1e-2 → 51.4% test (majority 30.6%).
Second run with a tone-matched system prompt: 49.7% dev — no effect; the trunk
genuinely encodes generic tone weakly.

Artifact: eq_tone_mt.head (17KB, temp 1.126). Published as free DEMO lane in
javimosch/mtlm-heads — deliberately weak-but-honest entry demonstrating why
conformal abstention and domain-fitted heads matter. Not certified.
