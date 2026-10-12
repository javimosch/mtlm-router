# Changelog

All notable changes to the mtlm-router appliance, runtime tooling, and lane
ecosystem. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Lane packs version independently — see the
[mtlm-heads catalog](https://github.com/javimosch/mtlm-heads).

## [Unreleased]

## [0.8.0] - 2026-10-12

### Added
- `banking77@0.1.0` lane published: 50 banking intents + `oos`, 73.3% in-scope,
  84.4% ID-OOS recall, certified + live-verified (catalog v45).
- `site/pricing.html` — public free/custom/commercial/hosted pricing page.
- `bench/verify_catalog.sh` now asserts the answering server's expert set via
  `/v1/lanes`, closing the stale-server race where a slow bind failure let
  probes hit whoever already owned the port.
- `emit_banking77.py`: F-feature caching, wider taps/l2 grid, valid split in
  train, balanced selection. Grid re-run confirmed the shipped config remains
  the best operating point.
- `eq_tone@0.2.0` lane published (demo): hard-negative retrain adds an
  explicit `oos` class — 87.9% recall on non-tone text; `eq_tone@0.1.1`
  deprecated. Its `floors.json` entry now carries a measured `min_conf` 0.5.
- `site/llms.txt` — agent-facing index of product, docs, registry links, and
  measured numbers.
- Hosted API (`api.mtlm-router.intrane.fr`) now serves all 10 certified lanes
  with catalog floors wired as `ANVIL_EXPERT_MINCONF`; `ops/RUNBOOK.md` §9
  documents the meter → upstream topology.
- Appliance bundles `bank77` + upgraded `eq` (v2) heads; `start.sh` wires both.

### Changed
- `check_docs.py` also validates the docs' route-example field names against
  the declared `RouteDecision` schema.
- `lane_verify --dir` exempts yanked packs from warning gates (deprecation
  lifecycle applied to all 5 non-latest versions; catalog is `--strict` clean).
- `lane_install --apply` writes each lane's registry `min_conf` floor into the
  managed env block — recommended floors are now enforced, not advisory.

## [0.7.0] - 2026-10-11

### Added
- `bench/api_contract.py` — live-vs-`openapi.yaml` drift guard on all five
  typed endpoints.
- `bench/route_latency.py` — client-perspective p50/p95/p99 for `/v1/route`
  (measured: 61/75/77 ms on plain CPU; head matmul adds ~0).
- `tests/test_lane_verify.py` — 11 synthetic packs pinning every verifier
  check. `tests/test_lane_install.py` — 9 fixture tests for install/check/
  uninstall/yank paths.
- `lane_verify --strict` — exit 2 on warnings-only, 1 on errors (commitlint
  convention). Two new content checks: head-embedded label names vs taxonomy,
  and declared `metrics.taps` vs embedded taps.
- Catalog shows recommended confidence floors, leak/coverage operating points,
  latest-per-lane grid with older versions under "other versions".
- `lane_install` is fully yank-aware: warns on pinned yanked installs, flags
  installed-yanked lanes in `--check`, never auto-picks a yanked version.
- Appliance ships `clinc2` (clinc150@0.1.4 hard-negative head), `helpdesk2`,
  `eq`, plus the full toolset (`lane_verify`, `lane_pack`, `api_contract`).

### Fixed
- `openapi.yaml` response shapes for `/v1/decide`, `/v1/noul`, `/v1/score`,
  `/v1/assess` rewritten to match the real live contract (found by the new
  drift guard on its first run).
- `lane_verify`: four `fail()` calls missing their error list were swallowed
  by a broad `except` in the taps check — declared-taps mismatches silently
  downgraded to warnings. Caught by the new test suite.
- `pick()` could select a yanked version as newest on unpinned installs.

## [0.6.0] - 2026-10-11

### Added
- `tools/lane_install.py` — fetch/verify/install from the mtlm-heads index:
  `--list`, `--check` (update report with latest metrics), `--uninstall`,
  `--apply` (idempotent managed env block in `start.sh`).
- `bench/oos_eval.py` — generic leak-vs-coverage curve for any head.
- `bench/head_parity.py`, `bench/catalog_parity.py`, `bench/verify_catalog.sh`
  — offline-vs-live parity gates for single heads and the whole catalog.
- `bench/head_capacity.py` — linear vs MLP64 on identical frozen features
  (negative result: feature space is the bottleneck, not head capacity).
- `bench/gen_speed.py` — decode throughput (~470 tok/s on the 7M int8 trunk).
- `tools/render_catalog.py` — generates `site/catalog.html` + README lane table
  from `index.json`, with `--check` freshness gate.
- `tools/check_docs.py` — docs-drift gate (endpoint coverage + numeric claims).
- `monitor.py` two-sample KS on confidence distribution — label-free
  statistical drift signal.
- civic lane (FixMyStreet Open311, 13 routes, 96.8% certified), civic_fr lane
  (DansMaRue taxonomy), `mairie` OOS hard-negative experiment (documented
  no-ship), helpdesk@0.2.0 with explicit `oos` class.

### Fixed
- `head_io` kind map (1=max, 2=mean per emit writer); mhd2 has no tap metadata.

## [0.5.0] - 2026-10-10

### Added
- `ops/RUNBOOK.md` — probes, maintenance loop, canary promotion,
  recalibration, incidents.
- `tools/shadow_report.py` — Wilson-bound promotion gate for `ANVIL_SHADOW`
  canaries; `bench/shadow_overhead.py` measured ~0% shadow cost.
- `/livez`, `/readyz`, `/v1/lanes` endpoints; `smoke.sh` grew to 12 checks.
- `tools/lane_verify.py` — lanepack integrity + schema + honesty verifier.
- eq_tone lane (GoEmotions, honest demo-grade 51.4%).

## [0.4.0] - 2026-10-10

### Added
- `tools/lane_pack.py` — certified lane pack format (`.lanepack.tar.gz`).
- `openapi.yaml` — machine-readable contract for the whole API surface.
- `tools/monitor.py` — label-free drift detection on `decisions.jsonl`.
- `tools/mcp.src` — stdio MCP adapter (`route_request`, `typed_questions`),
  pure MFL.
- `bench/systemone/contract.sh` — 19-check Jev contract conformance suite.
- `tools/smoke.sh` — instance validator shipped in appliance packages.
- `bench/perf.sh` — measured 38 ms p50, ~35 req/s @ 10 concurrency.
- `bench/risk_coverage.py` — risk-coverage curve + AURC.
- `site/docs.html` — full API/user documentation page.

### Changed
- Municipal corpus moved to the private `mtlm-data` repo (geored naming
  scrubbed).

## [0.3.0] - 2026-10-09

### Added
- CLINC150 generic-intent lane: 73.8% holdout, 0.842 OOS AUROC, live as
  expert `clinc`.
- `/v1/systemone` — Jev-compatible typed-questions endpoint.
- Conformal abstention shipped in the runtime (`ANVIL_EXPERT_QHAT`):
  coverage-guaranteed gate, Mondrian per-route error budgets, selective
  risk control (CP-95% bound among automated answers).
- `tools/aci_qhat.py` — adapts lane qhat from labeled outcomes via `/_qhat`.
- `mtlm-router` CLI: `guide`, `feedback`, `update`/`uninstall` with sha256
  content-hash verify and smoke-tested atomic swap; conformance 28/28.
- Landing: few-shot learning curve, ready-made lanes catalog section.

### Changed
- Honest latency on the site: ~30 ms p50 measured live (was "~15 ms").

## [0.2.0] - 2026-10-08

### Added
- First appliance release: frozen `m7router3s384` 7M trunk + specialist
  `.head` lanes, `anvil-serve` runtime, `start.sh`, manifest.
- Typed endpoints: `/v1/route`, `/v1/decide`, `/v1/noul`, `/v1/score`,
  `/v1/assess`, `/v1/chat/completions`; `/health`, `/_health`, `/_qhat`,
  `/_shutdown`, `/metrics`.
- `docs/MODEL-CARD.md`, `PRODUCT.md`.

[Unreleased]: https://github.com/javimosch/mtlm-router/compare/v0.8.0...HEAD
[0.8.0]: https://github.com/javimosch/mtlm-router/releases/tag/v0.8.0
[0.7.0]: https://github.com/javimosch/mtlm-router/releases/tag/v0.7.0
[0.6.0]: https://github.com/javimosch/mtlm-router/releases/tag/v0.6.0
[0.5.0]: https://github.com/javimosch/mtlm-router/releases/tag/v0.5.0
[0.4.0]: https://github.com/javimosch/mtlm-router/releases/tag/v0.4.0
[0.3.0]: https://github.com/javimosch/mtlm-router/releases/tag/v0.3.0
[0.2.0]: https://github.com/javimosch/mtlm-router/releases/tag/v0.2.0
