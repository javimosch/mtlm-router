# MASSIVE fr-FR head — generality test (2026-10-05)

Source: SetFit/amazon_massive_intent_fr-FR (HF, parquet mirror of Amazon MASSIVE;
the AmazonScience/massive repo is loader-script-only, refused by datasets 5.x).
11,514 train / 2,974 test, 60 intents, French.

Sweep (12 combos, single LR fit each, l2=1e-3, router3 trunk):
  (-4,mean) 65.03% cw11  <- best, emitted
  (-3,mean) 64.66%  (-4,max) 61.57%  (-1,mean) 61.0%  ... last-pooling 46-52%
Majority baseline 5.9%.

Verdict: works but mediocre vs fine-tuned multilingual encoders (~85-91%
published). The trunk encodes ITS training distribution; heads excel on
client-distribution exports (municipal export 79%) not arbitrary intent vocab.
Product framing: 'a head per client trained on their export' — never
'generic intent classifier'.

Artifact: massive_fr_m4m.head (70KB, mean@-4, temp 0.762) on rbm21
../mtl-data/municipal/. Not shipped in any appliance — benchmark probe only.

Perf note: head_probe.py's full sweep (5-fold CV x 7 clf params x 12 combos)
took >4h CPU at 60 classes and was killed; emit_massive.py (single fit per
combo) did the same job in ~1h including feature extraction.
