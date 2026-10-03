# mtlm-router

**Route natural-language requests to the right lane — on your own hardware,
with an honest "I don't know".**

Every company has an inbox nobody wants to read: support tickets, citizen
complaints, ops requests, shared mailboxes. Someone reads each line, decides
*what kind* it is, and sends it to the right team or tool. mtlm-router is the
component that makes that decision — typed, confidence-scored, and safe
enough to abstain instead of guessing wrong.

It's a **7M-parameter decision layer**, trained end-to-end in pure
[machin/MFL](https://github.com/javimosch/machin), made in Europe. ~15 ms per
decision on CPU, fully self-hosted — data never leaves your network.

## Proof on real production data

Trained a draft head on an **anonymized export of a real municipal
citizen-request inbox** (6,402 labeled requests, 15 routes):

| | |
|---|---|
| Holdout accuracy | **76.9%** |
| Confident-wrong (≥90% conf) | **~0%** — it abstains instead of misrouting |
| Head size | 18.7 KB |
| Latency | ~180 ms on plain CPU |

Live trace:

```text
» "mon bac jaune n'a pas été ramassé"    → dotation_bacs @ 0.89   — routed
» "dépôt sauvage rue des lilas"           → abstains @ 0.53        — human reviews
» "what's the weather in lyon"            → delegate               — off-domain, refuses to guess
» "attack the dragon"                     → escalate @ 0.98        — absurd input, safely out
```

The weak routes aren't model failures — they're overlapping labels citizens
pick wrong in the form itself. That's a route-table design problem, which is
exactly the kind of thing a pilot fixes. [The honest breakdown is in the
proposal report](https://hart.intrane.fr/a/javimosch/mtlm-router-realdata-report).

## The input is just your labeled inbox

No ML engineering required. One line per historical request:

```text
depot_illicite :: il y a un dépôt sauvage de gravats rue des lilas
dotation_bacs  :: je voudrais obtenir un bac pour le compost
collecte_om    :: mon bac jaune n'a pas été ramassé ce matin
```

`route :: request text` — or JSONL `{"user": ..., "expect_tool": "route"}`.
~1,000 rows per frequent route is enough for a first draft; ambiguous and
refused requests belong in too (they teach abstention). No PII needed —
hash identifiers if you want grouping.

```bash
python3 tools/head_studio.py --config your_routes.json \
    --hf /path/to/hf-bundle --name helpdesk --outdir out/
```

One command produces a calibrated ~7–20 KB `.head` you swap into the
appliance. Per-client routing vocabulary = a file, not a fine-tune.

## The one-call API

```bash
curl localhost:8097/v1/route \
  -H 'content-type: application/json' \
  -d '{"state":"remind me to call the dentist tomorrow at 6pm"}'
```

```json
{"action":"tool_call","route":"set_reminder","confidence":0.9999,
 "p_yes":1.8e-06,"reason":"ok",
 "call":{"name":"set_reminder","arguments":{"text":"call the dentist","when":"tomorrow at 6pm"}}}
```

`action` is one of `tool_call` / `chat` / `delegate` — the safety gates are
built in (low confidence, `escalate`, head↔generation disagreement all
delegate rather than misroute). See [PRODUCT.md](PRODUCT.md) for the full
endpoint surface.

## Mixture of experts — one trunk, many heads

A frozen 7M trunk; domain knowledge lives in kilobyte `.head` files:

```bash
ANVIL_GATE=moe_gate.head \
ANVIL_EXPERTS="it_helpdesk:helpdesk.head,fleet_gate:fit.head,mairie:geored.head" \
./anvil-serve model.bin 8401
```

- **Per-head pooling** — each head declares its own feature tap
  (`last-token` / `mean@-k` / `max@-k`); the eval picks the recipe, the
  server obeys.
- **Expert pin** — `{"state":..., "expert":"mairie"}` skips the gate for
  known-domain traffic; the head's own `escalate` class is the abstention path.
- **Tenants** — `ANVIL_TENANTS="key:head"` binds API keys to their own
  heads — multi-customer on one trunk.

## Numbers — held-out *and* live

| metric | value |
|---|---|
| route accuracy | **97.6%** (ECE 0.012) |
| gate accuracy (holdout) | **95.4%** (5 domains) |
| gate accuracy (live canary) | **98.0%** aggregate — verified per-domain before swap |
| real-corpus domain head | **76.9%** (~0% conf-wrong) |
| latency | ~15 ms / decision, no GPU |
| size | 7.2M params, 8.06 MB int8 |

We publish holdout and live-eval side by side because they disagree —
candidates pass holdout and still regress a dominant lane live.
`tools/eval_gate_live.py` judges per lane, not in aggregate.

## The flywheel — it trains on its own traffic

Every `/v1/route` decision is logged (`decisions.jsonl`). The flywheel
harvests uncertain real requests into a review queue → labeled rows →
new head. A daily timer runs the loop; the gate thickens on real traffic,
never on its own confident predictions.

## Appliance — the whole product in 7.5 MB

```bash
# https://github.com/javimosch/mtlm-router/releases
tar xzf mtlm-router-*.tar.gz && cd mtlm-router-* && ./start.sh
# /v1/route on :8097 — or install mtlm-router.service
```

Static binary + int8 model + tokenizer + heads + launcher. No deps, no GPU,
no cloud. `manifest.json` ships sha256s and the eval it was verified with —
the honesty contract is a file.

## Who this is for

- **SME / integrator**: a shared mailbox or ticket queue that should route
  itself — your client's vocabulary, their on-prem box, flat cost.
- **Ops / platform**: typed ops actions (`set_reminder`, `unlock_account`)
  behind an API that escalates risky or ambiguous requests instead of
  firing them.
- **Compliance-sensitive**: EU-hosted, air-gap capable, no LLM calls, no
  per-request cost, no data egress.

## Links

- **Landing**: [mtlm-router.intrane.fr](https://mtlm-router.intrane.fr) (EN/FR)
- **Model**: [javimosch/mtlm-7m-router3s384](https://huggingface.co/javimosch/mtlm-7m-router3s384)
  · [Model card](docs/MODEL-CARD.md)
- **Runtime**: [machin-anvil](https://github.com/javimosch/machin-anvil)
- **Hosted API**: `https://api.mtlm-router.intrane.fr` —
  [onboarding](https://api.mtlm-router.intrane.fr/llms.txt), pay-per-decision
- **Demo**: [machin-game-mtlm-rpg-poc](https://github.com/javimosch/machin-game-mtlm-rpg-poc)
  (an agent plays a dungeon through the router)

## Layout

- `tools/head_studio.py` — self-serve head pipeline (config → `.head`)
- `tools/head_probe.py` — layer/pooling sweep + `mhd2` emit
- `tools/gen_routespec.py`, `tools/train_head.py` — spec → `.head`
- `tools/route_audit.py` — lead requests → audit report + appliance package
- `tools/synth_tools.py` — trunk training corpus generator
- `tools/eval_gate_live.py`, `tools/probe_gate.py` — per-domain canary + CI gate
- `tools/harvest_gate.py`, `tools/judge_review.py`, `tools/build_gate_spec.py`,
  `tools/shadow_feed.py` — the flywheel
- `tools/calibrate.py`, `tools/refit_temp.py`, `tools/health_check.py` — ops
- `tools/package_appliance.sh` — build the self-hosted tarball
- `docs/MODEL-CARD.md` — bilingual model card
- `data/geored/` — real-corpus extraction notes + provenance (production-derived)

## License

Apache-2.0 — see [LICENSE](LICENSE).
