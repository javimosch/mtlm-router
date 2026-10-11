#!/bin/sh
# verify_catalog.sh — one-command whole-catalog parity check.
# Spins up a scratch anvil instance with every shipped head as an expert,
# runs bench/catalog_parity.py against it, tears down. Exit 1 on divergence.
#
# Usage (on a host with anvil + HF features, e.g. rbm21):
#   HOSTED=/root/mtlm/hosted bench/verify_catalog.sh            # default ports/dirs
#   ANVIL=./anvil-serve-mixed MODEL=models/m7router3s384.bin PORT=8398 \
#     bench/verify_catalog.sh
set -e
HOSTED=${HOSTED:-/root/mtlm/hosted}
MODELS2=${MODELS2:-/root/mtlm/models}
ANVIL=${ANVIL:-$HOSTED/anvil-serve-mixed}
MODEL=${MODEL:-$HOSTED/models/m7router3s384.bin}
PORT=${PORT:-8398}
HEAD=${HEAD:-$HOSTED/models/decide_mt.head}
BENCH=${BENCH:-/root/mtlm/bench}

EXPERTS="civic:$HOSTED/models/civic_v2_mt.head,\
civic_fr:$HOSTED/models/civic_fr_v2_mt.head,\
clinc:$HOSTED/models/clinc150_mt3.head,\
clinc2:$MODELS2/clinc150_v2.head,\
helpdesk1:$HOSTED/models/helpdesk_pool_L-3_mean.head,\
helpdesk2:$MODELS2/helpdesk_v2_mt.head,\
mairie:$HOSTED/models/mairie_mt3.head,\
eq:$MODELS2/eq_tone_mt.head"

echo "[verify_catalog] starting scratch anvil on :$PORT" >&2
cd "$HOSTED"
ANVIL_HEAD="$HEAD" ANVIL_EXPERTS="$EXPERTS" \
  "$ANVIL" "$MODEL" "$PORT" >/tmp/verify_catalog_$$.log 2>&1 &
PID=$!
trap 'kill $PID 2>/dev/null' EXIT
for i in 1 2 3 4 5 6 7 8 9 10; do
  curl -sf "http://localhost:$PORT/readyz" >/dev/null 2>&1 && break
  sleep 1
done
# a readyz hit means nothing if OUR instance died on bind — a stale server
# on the same port would silently answer with the wrong expert set
if ! kill -0 "$PID" 2>/dev/null; then
  echo "[verify_catalog] scratch anvil died (port $PORT in use?)" >&2
  tail -5 "/tmp/verify_catalog_$$.log" >&2
  exit 1
fi
python3 "$BENCH/catalog_parity.py" --url "http://localhost:$PORT"
RC=$?
kill $PID 2>/dev/null
exit $RC
