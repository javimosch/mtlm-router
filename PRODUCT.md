# mtlm-router — a self-hosted typed decision layer

**One sentence:** a 7M-parameter model, trained end-to-end in pure machin/MFL,
that turns natural-language requests into typed, calibrated routing decisions —
in ~30ms, on CPU, on-prem — and knows when to say "not my job".

## What it does

Every request gets a structured decision, not a guess:

```
POST /v1/assess {"state": "remind me to call the dentist tomorrow"}

→ {"decision": {"choice": "set_reminder", "confidence": 0.9999},
   "noul":     {"answer": "no",  "probability": 2e-13},   # escalate?
   "score":    {"grade": "3",    "confidence": 0.9999}}   # complexity 1-4
```

**One forward pass answers all three questions.** No tokens generated — the
heads read the model's hidden state directly. Malformed output is
unrepresentable: `choice` is always one of the trained routes.

| endpoint | question answered |
|---|---|
| `POST /v1/route {state \| messages, options?, execute?, min_conf?}` | **the product call** — assess → gate → dispatch; returns `{action: tool_call\|generate\|delegate, route, confidence, p_yes, tier, reason, call?}` |
| `POST /v1/decide {state, options?}` | which of N routes? (+ `options` restricts the set server-side) |
| `POST /v1/noul {state}` | should this escalate? (p_yes) |
| `POST /v1/score {state}` | how complex is it? (grade 1–4) |
| `POST /v1/assess {state}` | all of the above, one pass |
| `POST /v1/chat/completions` | generative path — fills tool args, answers chat |

All typed endpoints take an optional `context` array — prior turns,
alternating user/assistant — so follow-ups like *"and in London?"* route
against the conversation, not just the last message.

## Numbers (held-out, live-verified — m7router3s384)

Leak-free protocol: heads fit on train rows only, evaluated through the
served runtime (`/v1/decide`, `/v1/route`) on the untouched holdout. Earlier
"all-rows" live figures (99.5–100%) were inflated by holdout leakage in the
emitted weights — corrected 2026-10-08.

- Route head (mhd3 `mean@-3 + max@-4`): **98.4%** live on the 800-row holdout,
  1 confident-wrong (all-rows production fit measures 99.5%, leaked)
- Noul head (mhd3 `mean@-2 + max@-3`): **99.4%** live, 0 confident-wrong
- Score head (mhd3 `mean@-2 + max@-3`): **98.8%** live, errors adjacent-tier
- Business gate (mhd3 `mean@-2 + max@-3`): **98.7%** live, 149 holdout rows
- Generative eval (800 probes): tool-name 98.75%, arg-value 95.2%
- Latency: 28–47ms p50 per decision measured live on hosted 2026-10-08
  (route 34.7, decide 28.1, expert lanes ~45, noul/score ~42), no GPU —
  batched pooled prefill + clamped prefix cache
- Model: 7.2M params, llama-arch, seq-384, 8.06MB int8 — the whole serving
  stack is MFL

## The product shape

The dispatcher pattern is abstention-first — a wrong dispatch requires the
typed head *and* the generative path to be wrong in the same direction:

1. `/v1/assess` → route + confidence + escalate? + complexity, ~30ms
2. Escalate on: low confidence | `escalate` route | noul yes | head-vs-trunk
   disagreement
3. Only agreed, confident routes execute

**Per-customer route tables are ~7KB head artifacts**, not model fine-tunes.
A customer's tool vocabulary is a config file — one command does the rest:

```
python3 tools/head_studio.py --config my_routes.json --hf /path/to/hf-bundle \
    --name myco --outdir out/
# → validates routes, synthesizes train/eval specs (leakage-filtered),
#   trains on the frozen trunk, reports acc/ECE/confusion, writes:
#   out/myco.head + out/myco.head.json (manifest)
# serve: ANVIL_HEAD=out/myco.head ./anvil-serve model.bin 8097
```

Measured on the demo 6-route IT helpdesk config (`tools/demo_helpdesk.json`)
over the router3 trunk: **100% on leakage-filtered held-out rows** — accuracy
scales with how many stems the config supplies. Same trunk, per-deployment
brains.

**Observability is built in**: `ANVIL_LOG` streams every decision as JSONL;
`tools/calibrate.py` buckets confidence vs labeled outcomes for real-traffic
calibration; `tools/refit_temp.py` refits a head's temperature on your own
labeled traffic so the confidence gate stays honest; `tools/health_check.py`
is the one-command prod smoke.

## Mixture of experts — one trunk, many brains

Heads are experts: a ~7KB `.head` file is a domain's whole routing brain on
the same frozen trunk. The MoE product is automatic expert selection — a
**gate head** whose "routes" are domain names picks the expert, then the
expert head scores the domain routes. Both read one prefill's hidden state,
so the second decision costs ~1ms, not a second forward pass.

```
ANVIL_HEAD=models/m7router3s384.head \
ANVIL_GATE=models/moe_gate.head \
ANVIL_EXPERTS="it_helpdesk:models/helpdesk.head,fleet_gate:models/fleet_gate.head,rpg:models/rpg.head" \
./anvil-serve model.bin 8400
curl localhost:8400/v1/route -d '{"state":"status of ticket INC4821"}'
# {"action":"tool_call","route":"ticket_status","confidence":0.86,
#  "domain":"it_helpdesk","gate_confidence":0.99,"expert":"it_helpdesk",...}
```

One `/v1/route` call, one prefill, two decisions. `ANVIL_GATE_MINCONF` (or
per-request `min_gate_conf`) delegates with `low_gate_confidence` when the
gate itself is unsure; an unmapped domain falls back to `ANVIL_HEAD`. The
older key-per-head pattern (`ANVIL_TENANTS` + `tools/moe_route.py` shim)
still works for manual expert selection, but native mode is the product API.

v0.1 gate head (`out/moe_gate.head`, trained on rbm4 — `tools/build_gate_spec.py`
assembled 981 domain-labeled rows from the real corpora): **95.4% held-out
expert selection, ECE 0.035** (0.965 with harvested rows + serving-prompt
training). Live demo on rbm4 routes helpdesk/tools/chat requests correctly
in ~22ms end-to-end; wrong-gate cases degrade to `escalate` on the fallback
head — a wrong gate delegates instead of misrouting. Weak lane is `rpg`
(64 real rows) — thin domains need label volume, same rule as everywhere else.

**Per-head features** (`mhd2` flags, anvil ≥ 6089a71): each head declares
the hidden-state tap it was trained on — `last-token`, `max`, or `mean`
over the last user turn at a chosen layer — and mixed configs coexist on
one instance. The shipped mix: gate + default tools head on last-token,
`fleet_gate` on max@-3, `it_helpdesk`/`rpg` on mean@-3/@-4. Sweep verdicts:
**mean pooling wins short synthetic rows, max wins long prose, last-token
holds on canonical short commands** — pooling is a per-head choice, never
a server flag.

**The label flywheel runs daily** (`mtlm-gate-flywheel.timer` on rbm21):
`ANVIL_LOG` records every decision on rbm4; `tools/harvest_gate.py`
auto-labels rows where gate and expert agreed at ≥0.90 conf into
`gate_harvest.jsonl` (train-only — auto-labels never touch holdout) and
files uncertain/delegated rows to `gate_review.jsonl` for judging;
`tools/shadow_feed.py` streams real GitHub issues into the router as
shadow traffic. Re-run `build_gate_spec.py` + `train_head.py` to fold
harvested rows into the next `moe_gate.head`.

## Honest limits

- 7M params: argument values from the generative path can be sloppy — validate
  platform-side before executing.
- `noul`/`score` answer *fixed* trained questions, not arbitrary criteria text
  (dynamic criteria is the roadmap item).
- **Calibration needs your traffic.** A head's stored temperature is fit on
  synthetic holdout; on real traffic softmax confidences saturate ~1.0 even
  when wrong (measured on a production shadow deployment: 65/72 decisions at
  conf ≥0.99 with 61.5% accuracy). Run `tools/refit_temp.py --labels
  your_traffic.jsonl --mode marginal` once you have ~50+ labeled rows — it
  rewrites T so mean confidence tracks empirical accuracy, and an untrusted
  head degrades to honest abstention instead of confident guessing.
- **Ambiguous human-judgment tasks need label volume, not a bigger model.**
  On a fuzzy 3-way boundary ("is this issue a good fit for a drive-by
  comment") a 0.6B web-pretrained backbone scored *worse* than this 7M trunk
  (37% vs 48% on a 27-row holdout). The ceiling is label clarity and count;
  heads shine on well-defined structured decisions.
- Chat quality is TinyStories-grade — this is a dispatcher, not a chatbot.

## Field results on real corpora (2026-10)

- **Municipal requests (geored12, real production export, 6,402 rows, 15
  routes): 81.5% live / 82.5% offline, leak-free** (mhd3 multi-tap head:
  concat of max-pooled taps at layers -4/-2/-3, one forward pass;
  single-tap equivalent 78.5% live). Merging the ambiguous
  collecte_om/collecte_selective pair — >50% of residual error — gives a
  14-route head at **90.7% live** (85% automated at 98.1% at conf≥0.8):
  a taxonomy finding, not a model-capacity win. The strongest evidence
  that a per-client head works when the data matches the trunk's
  distribution. Under a **conformal abstention gate** (`tools/conformal_eval.py`,
  split-half calibration on live probability vectors): at error budget
  α=0.02 the gate auto-answers **97.8% of requests at 0.97% error** —
  ~13 points more automation than the τ=0.8 confidence floor at a
  comparable error rate, because a singleton prediction set is a smarter
  criterion than max-prob≥τ. Pick the error budget, get the guaranteed
  operating point — no hand-tuned floors. **Shipped in the runtime:**
  `ANVIL_EXPERT_QHAT="mairie_c:0.648"` enables the gate per lane —
  singleton prediction sets answer, anything else delegates with
  `reason:"conformal_abstain"` and the response exposes `set_size`/`qhat`.
  Live on the hosted API; empirical figure, formal coverage assumes
  calibration/production exchangeability — recalibrate per client.
  **Drift handling shipped:** `GET|POST /_qhat` updates any lane's
  threshold live, and `tools/aci_qhat.py` closes the loop — labeled
  outcomes (feedback verdicts) → ACI step `qhat −= γ·(err_rate−α)` →
  pushed via `/_qhat`, wired into the daily flywheel. The error budget
  survives distribution shift without a restart. Two operating modes:
  the coverage-max point above (empirical), or a **certified point** —
  `conformal_eval.py` also computes a Clopper-Pearson 95% upper bound on
  error *among automated answers* per threshold; at α=0.02 the certified
  operating point is 82.2% automated with the bound at 1.11% error —
  "no more than 2% of auto-answered requests are wrong, 95% confidence"
  is a sentence you can put in a contract. A `--mondrian` mode also
  reports class-conditional calibration — per-route qhat so a rare
  request type gets its own error budget instead of hiding inside the
  marginal average (on the merged lane: 96.5% auto @ 2.3% err with
  worst-class automation 66.7% exposed — the fairness check you'd want
  before trusting a municipal deployment).
- **French intent benchmark (MASSIVE fr-FR, 60 intents): 65%.** Real but
  not production-grade — used as the second domain in the MoE demo.
- **Generic English email (Enron kitchen-l, 8–20 folder-routes): 38–48%.**
  Subject-only vs body: same. TF-IDF concat: no rescue. Conclusion: head
  quality is data-dependent and must be *measured* on the client's export —
  the pilot (export → holdout number) is the product.
- **Generative routing (fine-tuned trunk, Jev path): not yet.** A 150-step
  fine-tune learned the tool_call format but collapsed to one class at 7M
  scale on an imbalanced 15-way task. Heads remain the product; a balanced
  retry is staged (`ft_retry.sh` on rbm21).

## Appliance

```
tar xzf mtlm-router-v0.2.0-linux-amd64.tar.gz   # v0.2.0 release
cd mtlm-router-v0.2.0-linux-amd64 && ./start.sh  # serves :8097
```

7.5MB total: static MFL binary + int8 model + decide/noul/score mhd3 heads +
business gate + it_helpdesk/mairie/mairie_c expert lanes + systemd unit +
start.sh + `mtlm-router` CLI. No Python, no GPU, no cloud key. `tools/package_appliance.sh`
rebuilds the tarball from any trunk+heads set.

## Agent-first surface (cli-specs, verified)

The appliance ships a `mtlm-router` CLI wrapper and a self-describing server,
aligned with https://cli-specs.intrane.fr/ — **28/28 on cli-spec-conformance**
(black-box checks of output, guide and daemon specs).

- `./mtlm-router guide` — embedded operator manual (JSON); `help-json`,
  `version`, `install`/`uninstall`
- `./mtlm-router serve|daemon start|stop|status` — loopback default, health-
  polled `/_health`, stop via `POST /_shutdown` (token-gated off loopback)
- `./mtlm-router feedback "msg"` — dual-write to the appliance's
  `POST /v1/feedback` (open, idempotent, rate-limited) and the central relay;
  `GET /v1/feedback` is admin-gated
- `./mtlm-router update [--check|--force]` — sha256[:12] content-hash verify,
  smoke-test, atomic swap with `.bak` rollback; hourly passive nudge on stderr
- Server endpoints beyond /v1: `GET /guide`, `GET /llms.txt`, `GET /_health`,
  `GET /v1/whoami` (masked-key tenant identity), `POST /_shutdown`
- Env knobs: `ANVIL_BIND` (wrapper forces loopback; `start.sh` serves 0.0.0.0),
  `ANVIL_EXPERT_MINCONF` (per-lane abstention floors), `ANVIL_FEEDBACK_LOG`

## Stack

- model + heads: [javimosch/mtlm-7m-router3s384](https://huggingface.co/javimosch/mtlm-7m-router3s384)
  (previous: [mtlm-7m-router2s384](https://huggingface.co/javimosch/mtlm-7m-router2s384))
- runtime: [machin-anvil](https://github.com/javimosch/machin-anvil) (pure MFL,
  OpenAI-compatible + decision endpoints)
- training + evals + reference dispatcher: this repo (`tools/`)
