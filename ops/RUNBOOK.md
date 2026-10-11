# mtlm-router operations runbook

Day-2 operations for a self-hosted appliance. Assumes the tarball layout:
`anvil-serve`, `models/`, `start.sh`, `smoke.sh`, `tools/`, `logs/decisions.jsonl`.

## 1. Health model

| probe | endpoint | meaning | wire to |
|---|---|---|---|
| liveness | `GET /livez` | process alive, cheap | k8s `livenessProbe`, systemd watchdog |
| readiness | `GET /readyz` | model + heads loaded (503 until ready) | k8s `readinessProbe`, LB health check |
| lane detail | `GET /v1/lanes` | per-lane routes, qhat, gate (auth-gated with `/v1/*`) | ops dashboard |

`/readyz` is the traffic gate: it returns 503 when no heads are loaded —
orchestrators should drain on it, not on `/livez`.

Kubernetes sketch:

    livenessProbe:  {httpGet: {path: /livez,  port: 8097}, periodSeconds: 10}
    readinessProbe: {httpGet: {path: /readyz, port: 8097}, periodSeconds: 5}

## 2. Install / restart

    ./start.sh                          # foreground/simple
    cp mtlm-router.service ~/.config/systemd/user/ && systemctl --user start mtlm-router

Gotchas that have actually bitten:

- `cp` onto a running `anvil-serve` → `Text file busy`. Stop first.
- `pkill -f anvil` can match your own shell command line — use `pgrep -x` or kill by PID.
- `/v1/*` is auth-gated when `ANVIL_KEYS` is set; `/readyz` and `/livez` stay open for probes.
- If a systemd unit exists for the instance (check `systemctl list-units | grep mtlm`), deploy through it — a hand-launched replacement loses the env baked into the unit (incl. `ANVIL_KEYS`).

## 3. Verification after any change

    sh smoke.sh http://localhost:8097          # 12 checks: probes, route, conformal, gate, systemone
    sh bench/systemone/contract.sh             # 19 checks: Jev/System One shape conformance (needs repo checkout)

## 4. Daily / weekly maintenance loop

    # label-free drift check — flags rising set_size, falling auto%, and
    # conf-distribution shift (two-sample KS, alpha=0.01) per lane
    python3 tools/monitor.py logs/decisions.jsonl --window 500 --baseline 500
    # exit 1 = drifted lane(s) → calibration aging, BEFORE labels exist

Suggested cadence:

- **daily**: `smoke.sh` (CI or cron), `monitor.py` on the last 500 decisions
- **weekly**: review `decisions.jsonl` delegate/abstain rate per lane; check
  `/metrics` counters for delegate-reason mix shifting
- **monthly or on drift**: recalibrate (`§6`)

## 5. Canary a candidate head (zero risk)

    ANVIL_SHADOW=mylane:models/candidate.head ./start.sh

The candidate is scored on the *same features* as the served head (~0%
measured overhead — `bench/shadow_overhead.py`) and logged, never served.
Each `decisions.jsonl` row gains `shadow{route,conf,agree}`.

Promotion gate after burn-in:

    python3 tools/shadow_report.py logs/decisions.jsonl --lane mylane
    # exit 0 promote / 2 hold / 3 insufficient_data
    # gate: n>=200 AND agree>=0.9 AND Wilson 95% lower bound >=0.85

`promote` → swap `candidate.head` into `ANVIL_EXPERTS`, restart, re-run
`smoke.sh`. `hold` → inspect `top_disagreements`: if the candidate's picks
look *better*, that's a taxonomy/quality divergence — run a labeled eval
(`lane_verify` / `risk_coverage`), agreement alone can't prove it.

## 5b. Publishing a lane pack (pre-publish gate)

Offline eval is necessary but NOT sufficient — the civic 0.2.0 incident
shipped a head whose emit-time label alignment was broken; offline metrics
were green because they came from a different fit, and only live probing
exposed it. Gate (enforced by `lane_pack.py` for `certified`):

1. Load the candidate head in a real anvil instance:
   `ANVIL_EXPERTS=probe:models/candidate.head ./start.sh`
2. Send ≥3 probe texts — one clearly in-scope, one clearly out-of-scope —
   and eyeball `route`/`confidence` sanity.
3. **Parity gate (stronger than eyeballing):**
   `bench/head_parity.py --head <file> --url <instance> --expert <lane>
   --probes <txt> --tol 0.05` — scores every probe offline (`head_io` +
   HF features) AND live via `/v1/route`, exit 1 if any probe disagrees
   on top route or conf delta > tol. Catches wrong taps, transposed
   weights, and stale artifacts — the failure modes live eyeballing misses.
   NOTE: anvil serves expert features under `DECIDE_SYS` regardless of the
   corpus's training prompt — parity checks always use `DECIDE_SYS`.
4. Pack with `--live-verified`; the manifest records it and
   `lane_verify` reports it. `certified` packs built without the flag are
   refused; older certified packs verify with a warning.
   CI should run `lane_verify --strict` — exit codes: 0 clean, 2
   warnings-only, 1 errors (a warning is a gate to fix, not noise to keep).

After a catalog change (new pack, retrained head, or a `head_io`/serve
parser change), run the whole-catalog regression:
`bench/catalog_parity.py --url <multi-expert instance>` — ~4 probes per
lane across every shipped head, exit 1 on any offline↔live divergence.
First run caught a real mhd2 layout bug in the parser (29/29 green after).

Any `index.json` mutation also requires regenerating the catalog page —
`python3 tools/render_catalog.py` — and redeploying the landing. The
freshness gate `python3 tools/render_catalog.py --check` exits 1 when
`site/catalog.html` differs from a fresh render; run it in CI or before
deploy so the funnel surface can't silently lag the registry.

Companion gate for the docs page: `python3 tools/check_docs.py` exit-1s
when `site/docs.html` drifts — openapi.yaml paths missing from the
endpoint table, or stale numeric claims (smoke check count, contract
conformance count are re-counted from the scripts). Run it before any
landing deploy that touches `docs.html`.

## 5c. Per-lane operating points (confidence floors)

The argmax route is only half the decision — `ANVIL_EXPERT_MINCONF=lane:t`
(or per-request `min_conf`) gates low-confidence decisions to `delegate`.
Recommended floors measured by `bench/oos_eval.py` on each lane's
held-out in-scope + OOS probes (snapshot: `bench/oos_eval_catalog.json`):

| lane | recommended floor | leak@floor | coverage@floor | note |
|---|---|---|---|---|
| helpdesk | none needed | 0% | 100% | abstains correctly at argmax |
| civic | 0.5 | 4.2% | 96% | strong; 0.7 → 2% leak, 76% cov |
| civic_fr | none needed | 9% | ~100% | conf ~1.0 everywhere — gating useless, argmax abstain does the work |
| clinc150 | **0.7** | 7.5% | 70% | 15% argmax abstain; leaks are low-conf (median 0.23) so the floor does the work |
| mairie | 0.9 (strict) / 0.7 (balanced) | 0% / 13% | 25% / 62% | no `oos` class — floor is the only OOS defense; pick per risk appetite |
| eq_tone | none — use conformal | — | — | tone lane: `neutral` is its negative class; conf naturally ~0.4, conformal qhat is the calibrated gate |

Setting a floor per request beats env: `"min_conf": 0.7` in `/v1/route`.
`lane_install --apply` now writes the registry-recommended floor
(`floors.json` → `index.json operating.min_conf`) into the managed block as
`ANVIL_EXPERT_MINCONF=<lane>:<floor>` automatically — floors are enforced at
install time, not advisory.
Re-measure with `bench/oos_eval.py --head X.head --in-scope p.jsonl
--oos q.jsonl` after any head or corpus change — floors are per-artifact.

## 5d. Route latency (measured)

`bench/route_latency.py` — 100 mixed-length probes, localhost client:

| mode | p50 | p95 | p99 |
|---|---|---|---|
| trunk only | 61ms | 75ms | 78ms |
| + expert head (civic_fr) | 61ms | 74ms | 77ms |

The head matmul is free at these sizes — latency is the frozen-trunk
forward pass (~300-token cap). Budget ~80ms per route call; set client
timeouts from p95, not p50. Latest run: `bench/route_latency_latest.json`.

## 5e. API contract drift guard

`bench/api_contract.py --url http://localhost:PORT` probes every typed
endpoint (`route`, `decide`, `noul`, `score`, `assess`) and fails if a live
response carries a field `openapi.yaml` doesn't declare, or an enum value
outside the spec. Run it after touching a route handler — spec drift found
2026-10 (conf→confidence, p_yes→probability, probabilities blocks added)
sat unshipped until this check existed. Endpoints that 400 on a lane-pinned
instance (no noul/score heads) are skipped.

## 6. Recalibration (conformal)

When `monitor.py` reports drift, or a lane's abstain rate creeps:

1. Collect a fresh labeled calibration split for the lane (≥ a few hundred
   rows matching current traffic distribution).
2. `python3 tools/conformal_eval.py` → new qhat per lane.
3. Update `ANVIL_EXPERT_QHAT=lane:<new qhat>` and restart — no head
   retraining needed; the guarantee follows the data.

ACI (`/_qhat`) adapts online between recalibrations; treat its drift as an
early-warning signal, not a fix.

## 7. Incidents

| symptom | likely cause | action |
|---|---|---|
| `/readyz` 503 | heads failed to load (bad path in `ANVIL_EXPERTS`) | check startup log lines `pool tap:` / errors |
| all routes → `delegate` | qhat too tight, or gate misrouted | `/_qhat` to inspect; `ANVIL_EXPERT_MINCONF` as temporary floor |
| `/v1/*` 401 everywhere | `ANVIL_KEYS` set but missing/rotated client key | confirm env; `/_health` and probes are unaffected |
| port already bound, stale responses | old `anvil-serve` still listening | `ss -tlnp | grep <port>`, kill by PID |
| auto% collapsing in monitor | distribution shift | recalibrate (`§6`); if persistent, retrain the lane on fresh examples |

## 8. Logs and audit

`logs/decisions.jsonl` — one JSON row per decision: state, action, route,
conf, reason, set_size, gate, expert, `shadow{}` when canarying. This is the
audit trail AND the input to `monitor.py` / `shadow_report.py`. Rotate with
logrotate; keep enough history for `--baseline` comparisons (≥ 2× window).
