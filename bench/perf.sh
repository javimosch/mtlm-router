#!/bin/bash
# Throughput + latency bench for a running mtlm-router instance.
# Usage: HOST=localhost:8421 sh bench/perf.sh
# On rbm21 a scratch instance: see comments — reuses hosted models, port 8421.
HOST=${HOST:-localhost:8097}
BODY='{"state":"green bin not collected again"}'
for i in 1 2 3; do curl -s "$HOST/v1/route" -H 'content-type: application/json' -d "$BODY" >/dev/null; done
for i in $(seq 1 20); do
  t0=$(date +%s%N); curl -s "$HOST/v1/route" -H 'content-type: application/json' -d "$BODY" >/dev/null
  echo $(( ($(date +%s%N)-t0)/1000000 ))
done | sort -n | awk '{a[NR]=$1} END{printf "seq p50=%dms p95=%dms min=%dms max=%dms\n",a[int(NR/2)],a[int(NR*0.95)],a[1],a[NR]}'
t0=$(date +%s%N)
seq 1 60 | xargs -P10 -I{} curl -s "$HOST/v1/route" -H 'content-type: application/json' -d "$BODY" >/dev/null
t1=$(date +%s%N)
echo "concurrent10: $(( 60000 / ((t1-t0)/1000000) )) req/s"
