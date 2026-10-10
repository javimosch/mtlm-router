#!/bin/sh
# mtlm-router appliance — start the server (no systemd needed).
# Env knobs: PORT (8097), ANVIL_ROUTE_MINCONF (0.55), ANVIL_GATE_MINCONF,
# ANVIL_POOL=max|mean, ANVIL_LOG (decisions.jsonl),
# ANVIL_EXPERT_QHAT — conformal abstention per lane (default: mairie_c:0.648,
# the calibrated alpha=0.02 point on the municipal calibration split;
# recalibrate per client with tools/conformal_eval.py before trusting it),
# ANVIL_DELEGATE_URL/KEY/MODEL/SYS (optional upstream for delegated requests).
cd "$(dirname "$0")"
PORT=${PORT:-8097}
export ANVIL_TOOLS_INJECT=0
export ANVIL_HEAD=models/decide_mt.head ANVIL_NOUL=models/noul_mt.head ANVIL_SCORE=models/score_mt.head ANVIL_GATE=models/gate_biz_mt.head ANVIL_EXPERTS=it_helpdesk:models/helpdesk_pool_L-3_mean.head,mairie:models/mairie_mt3.head,mairie_c:models/mairie_mt3c.head,clinc:models/clinc150_mt3.head
export ANVIL_EXPERT_QHAT=${ANVIL_EXPERT_QHAT:-mairie_c:0.648}
export ANVIL_LOG=logs/decisions.jsonl
mkdir -p logs
echo "mtlm-router on http://0.0.0.0:$PORT  (logs: logs/decisions.jsonl)"
exec ./anvil-serve models/model.bin "$PORT"
