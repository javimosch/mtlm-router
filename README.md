# mtlm-router

**A 7M-parameter typed decision layer, trained end-to-end in pure
[machin/MFL](https://github.com/javimosch/machin), made in Europe.** It sits in
front of your tools and assistants and turns natural-language requests into
typed, calibrated routing decisions — in ~15ms on CPU, fully self-hosted —
and knows when to say "not my job".

Built for SME and on-prem workflows: email/ticket triage, typed ops actions,
compliance-safe escalation — flat cost, data never leaves your network.

- **Model**: [javimosch/mtlm-7m-router3s384](https://huggingface.co/javimosch/mtlm-7m-router3s384)
  ([Hugging Face](https://huggingface.co/javimosch/mtlm-7m-router3s384) ·
  [ModelScope](https://www.modelscope.ai/models/javimosch/mtlm-7m-router3s384)) —
  weights, tokenizer, decision heads. [Model card](docs/MODEL-CARD.md) (EN/中文).
- **Runtime**: [machin-anvil](https://github.com/javimosch/machin-anvil) —
  pure-MFL OpenAI-compatible server with the typed decision endpoints.
- **This repo**: training/eval tooling, the self-serve customer-head
  pipeline, the gate flywheel, and the dispatcher contract.
- **Landing**: [mtlm-router.intrane.fr](https://mtlm-router.intrane.fr) (EN/FR).

## The one-call API

```bash
curl localhost:8097/v1/route \
  -H 'content-type: application/json' \
  -d '{"state":"remind me to call the dentist tomorrow at 6pm","execute":true}'
```

```json
{"action":"tool_call","route":"set_reminder","confidence":0.9999,
 "p_yes":1.8e-06,"tier":"3","reason":"ok",
 "call":{"name":"set_reminder","arguments":{"text":"call the dentist","when":"tomorrow at 6pm"}}}
```

`/v1/route` scores the request with the route head, the escalation head,
and the complexity head in **one forward pass**, applies the safety gates
(low confidence → delegate, `escalate` → delegate, head↔generation
disagreement → delegate), and optionally executes the call. Lower-level
primitives (`/v1/decide`, `/v1/noul`, `/v1/score`, `/v1/assess`,
`/v1/chat/completions`) remain available. See [PRODUCT.md](PRODUCT.md).

## Mixture of experts — one trunk, many brains

The frozen 7M trunk is shared. Domain knowledge lives in ~7 KB `.head`
files; a gate head picks the domain, the domain expert picks the route:

```bash
ANVIL_GATE=moe_gate.head \
ANVIL_EXPERTS="it_helpdesk:helpdesk.head,fleet_gate:fit.head,rpg:rpg.head" \
./anvil-serve model.bin 8401
```

- **Per-head pooling** — `mhd2` heads declare their own feature tap
  (`last-token` / `mean@-k` / `max@-k`). One instance serves a last-token
  gate, a mean@-3 helpdesk, and a mean@-4 rpg expert side by side —
  because the eval said those recipes win different lanes, and it was right.
- **Expert pin** — `{"state":"attack the goblin","expert":"rpg"}` skips the
  gate and the OOD vetoes entirely; the expert's own `escalate` class is the
  abstention path. For known-domain clients; the gate stays for mixed
  front-door traffic. Unknown pin → 400, no silent fallback.
- **Tenants** — `ANVIL_TENANTS="k1:helpdesk.head"` binds a Bearer key to its
  own head — per-customer routing vocabularies on one trunk.

## Numbers — held-out *and* live

| metric | value |
|---|---|
| route accuracy | **97.6%** (ECE 0.012) |
| gate accuracy (holdout) | **95.4%** (ECE 0.035, 5 domains) |
| gate accuracy (live canary) | **81.6%** aggregate — tools lane 62/63 |
| rpg expert, last-token → mean@-4 | 81.3% → **95.1%** |
| fleet expert, last-token → max@-3 | 48% → **63%** |
| escalate (noul) | **98.9%** |
| latency | ~15ms / decision, 6-core LXC, no GPU |
| size | 7.2M params, 8.06 MB int8 |

We publish both holdout and live-eval numbers because they disagree: two
gate retrain candidates passed holdout and were rejected by the live
canary matrix for regressing the dominant tools lane. `tools/eval_gate_live.py`
exists so the next retrain is judged lane by lane, not in aggregate.

## The flywheel — it trains on its own traffic

Every `/v1/route` decision is logged (`decisions.jsonl`). The flywheel turns
that log into corpus:

```
shadow_feed → decisions.jsonl → harvest_gate → gate_review → judge_review
                                                    ↘ train-only corpus → new head
```

- `tools/shadow_feed.py` — streams real traffic (GitHub issues, ticket
  dumps) through the router, context-capped to the 384-token window
- `tools/harvest_gate.py` — replays domain-less rows, files uncertain ones
  into a persistent review queue; `seen` = resolved only
- `tools/judge_review.py` — applies verdict rules → labeled train rows
- `tools/build_gate_spec.py` — merges corpus + harvest, deduped, train-only
  (holdout never sees harvested rows)

A daily timer runs the whole loop — the gate thickens on real requests,
never on its own confident predictions.

## Appliance — the whole product in 7.5 MB

```bash
# https://github.com/javimosch/mtlm-router/releases (v0.1.1)
tar xzf mtlm-router-m7router3s384-linux-amd64.tar.gz
cd mtlm-router-m7router3s384-linux-amd64
./start.sh        # /v1/route on :8097 — or install mtlm-router.service
```

Static binary + int8 model + tokenizer + heads + launcher — no
dependencies, no GPU, no cloud. `package_appliance.sh --gate --experts`
bundles a full MoE config; `manifest.json` carries sha256s of every
artifact plus the eval it shipped with — the honesty contract is a file.
Auth and multi-tenancy are env vars (`ANVIL_KEYS`, `ANVIL_TENANTS`).

## Customer heads — self-serve

A customer's tool vocabulary is a JSON config of example phrases, not a
fine-tune. One command produces a ~7 KB swappable `.head`:

```bash
python3 tools/head_studio.py --config tools/demo_helpdesk.json \
    --hf /path/to/hf-bundle --name helpdesk --outdir out/
# serve:  ANVIL_HEAD=out/helpdesk.head ./anvil-serve model.bin 8097
```

Validates route names, synthesizes train/eval specs (leakage-filtered),
trains on the frozen trunk, reports accuracy/ECE/confusion, writes the
artifact + manifest. Integrators: one trunk per client, one head per
vocabulary — per-client customization as a file swap.

## Layout

- `tools/head_studio.py` — self-serve head pipeline (config → `.head`)
- `tools/gen_routespec.py` — route config → labeled spec
- `tools/train_head.py` — spec → `.head` (linear head on frozen trunk)
- `tools/head_probe.py` — layer/pooling sweep + `mhd2` emit (`--emit-layer`,
  `--emit-pool`, `--emit-temp`, `--serve-system` to match anvil's prompt)
- `tools/synth_tools.py` — trunk training corpus generator
- `tools/eval_*.py`, `*_probes.json` — acceptance evals (agreement,
  natural, edge, exact) + `eval_gate_live.py` per-domain live canary
- `tools/harvest_gate.py`, `tools/judge_review.py`,
  `tools/build_gate_spec.py`, `tools/shadow_feed.py` — the flywheel
- `tools/calibrate.py`, `tools/refit_temp.py`, `tools/health_check.py` —
  ops tooling (confidence histograms, temperature refit on your labeled
  traffic, prod smoke)
- `tools/probe_gate.py` — probe-suite regression gate for CI
- `tools/package_appliance.sh` — build the self-hosted tarball
- `tools/router_demo.py`, `tools/jev_demo.py` — reference dispatchers
- `docs/MODEL-CARD.md` — bilingual (EN/中文) model card

## See it play

[machin-game-mtlm-rpg-poc](https://github.com/javimosch/machin-game-mtlm-rpg-poc)
— an agent plays a 10-room dungeon crawler through the live router: intents
route through the pinned rpg expert at ~1.0 confidence, off-domain requests
`escalate` instead of executing nonsense. `demo.sh` plays a full winning
quest and verifies the outcome.

## License

Apache-2.0 — see [LICENSE](LICENSE).
