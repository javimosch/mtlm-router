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

    # label-free drift check — flags rising set_size / falling auto% per lane
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
