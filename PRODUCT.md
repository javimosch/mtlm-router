# mtlm-router — a self-hosted typed decision layer

**One sentence:** a 7M-parameter model, trained end-to-end in pure machin/MFL,
that turns natural-language requests into typed, calibrated routing decisions —
in ~15ms, on CPU, on-prem — and knows when to say "not my job".

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

## Numbers (held-out, live-verified — m7router3s384, prod since 2026-09-22)

- Route head: **97.6%** on the stem-diverse holdout, ECE 0.012
- Head/generative agreement: **100%** (the dispatcher's consistency metric;
  was 0.9275 on router2 — the corpus fix closed the gap)
- Noul head: **98.9%** holdout
- Score head: **97.9%** holdout, errors only ever adjacent-tier
- Generative eval (800 probes): tool-name 98.75%, arg-value 95.2%
- Latency: ~15ms per decision on a shared 6-core LXC, no GPU
- Model: 7.2M params, llama-arch, seq-384, 8.06MB int8 — the whole serving
  stack is MFL

## The product shape

The dispatcher pattern is abstention-first — a wrong dispatch requires the
typed head *and* the generative path to be wrong in the same direction:

1. `/v1/assess` → route + confidence + escalate? + complexity, ~15ms
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
expert selection, ECE 0.035**. Live demo on rbm4 routes helpdesk/tools/chat
requests correctly in ~22ms end-to-end; wrong-gate cases degrade to
`escalate` on the fallback head — a wrong gate delegates instead of
misrouting. Weak lane is `rpg` (64 real rows) — thin domains need label
volume, same rule as everywhere else.

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

## Appliance

```
tar xzf mtlm-router-m7router3s384-linux-amd64.tar.gz   # v0.1.0 release
cd mtlm-router-m7router3s384-linux-amd64 && ./start.sh  # serves :8097
```

7.5MB total: static MFL binary + int8 model + three heads + systemd unit +
start.sh. No Python, no GPU, no cloud key. `tools/package_appliance.sh`
rebuilds the tarball from any trunk+heads set.

## Stack

- model + heads: [javimosch/mtlm-7m-router3s384](https://huggingface.co/javimosch/mtlm-7m-router3s384)
  (previous: [mtlm-7m-router2s384](https://huggingface.co/javimosch/mtlm-7m-router2s384))
- runtime: [machin-anvil](https://github.com/javimosch/machin-anvil) (pure MFL,
  OpenAI-compatible + decision endpoints)
- training + evals + reference dispatcher: this repo (`tools/`)
