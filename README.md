# mtlm-router

**A 7M-parameter typed decision layer, trained end-to-end in pure
[machin/MFL](https://github.com/javimosch/machin).** It sits in front of
your tools and assistants and turns natural-language requests into typed,
calibrated routing decisions — in ~15ms on CPU, fully self-hosted — and
knows when to say "not my job".

- **Model**: [javimosch/mtlm-7m-router3s384](https://huggingface.co/javimosch/mtlm-7m-router3s384)
  ([Hugging Face](https://huggingface.co/javimosch/mtlm-7m-router3s384) ·
  [ModelScope](https://www.modelscope.ai/models/javimosch/mtlm-7m-router3s384)) —
  weights, tokenizer, three decision heads. [Model card](docs/MODEL-CARD.md) (EN/中文).
- **Runtime**: [machin-anvil](https://github.com/javimosch/machin-anvil) —
  pure-MFL OpenAI-compatible server with the typed decision endpoints.
- **This repo**: training/eval tooling, the self-serve customer-head
  pipeline, and the dispatcher contract.

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

## Numbers (held-out — m7router3s384)

| metric | value |
|---|---|
| route accuracy | **97.6%** (ECE 0.012) |
| head↔generation agreement | **100%** |
| escalate (noul) | **98.9%** |
| complexity (score 1–4) | **97.9%** |
| latency | ~15ms / decision, 6-core LXC, no GPU |
| size | 7.2M params, 8.06 MB int8 |

## Appliance — the whole product in 7.5 MB

```bash
# https://github.com/javimosch/mtlm-router/releases (v0.1.1)
tar xzf mtlm-router-m7router3s384-linux-amd64.tar.gz
cd mtlm-router-m7router3s384-linux-amd64
./start.sh        # /v1/route on :8097 — or install mtlm-router.service
```

Static binary + int8 model + tokenizer + three heads + launcher — no
dependencies, no GPU, no cloud. Auth and multi-tenancy are env vars:
`ANVIL_KEYS="k1,k2"` gates `/v1/*` behind Bearer tokens, and
`ANVIL_TENANTS="k1:helpdesk.head"` gives a key its own decision head —
per-customer routing on one trunk, hot-swapped per request.

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
artifact + manifest. Demo helpdesk head: **100%** held-out on router3.

## Layout

- `tools/head_studio.py` — self-serve head pipeline (config → `.head`)
- `tools/gen_routespec.py` — route config → labeled spec
- `tools/train_head.py` — spec → `.head` (linear head on frozen trunk)
- `tools/synth_tools.py` — trunk training corpus generator
- `tools/eval_*.py`, `*_probes.json` — acceptance evals (agreement,
  natural, edge, exact)
- `tools/calibrate.py`, `tools/refit_temp.py`, `tools/health_check.py` — ops tooling (confidence histograms, temperature refit on your labeled traffic, prod smoke)
- `tools/probe_gate.py` — probe-suite regression gate for CI
- `tools/package_appliance.sh` — build the self-hosted tarball
- `tools/router_demo.py`, `tools/jev_demo.py` — reference dispatchers
- `docs/MODEL-CARD.md` — bilingual (EN/中文) model card

## License

Apache-2.0 — see [LICENSE](LICENSE).
