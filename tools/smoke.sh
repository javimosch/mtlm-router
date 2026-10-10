#!/bin/sh
# smoke.sh — validate a running mtlm-router instance end to end.
# Usage: sh tools/smoke.sh [host]   (default http://localhost:8097)
# Exits non-zero on the first failing check; prints one line per check.
HOST=${1:-http://localhost:8097}
fails=0
check() { # name, expr-result, expected-regex
  if echo "$2" | grep -qE "$3"; then echo "ok   $1"; else echo "FAIL $1 — got: $(echo "$2" | head -c 160)"; fails=$((fails+1)); fi
}
J='content-type: application/json'

check "health"        "$(curl -s $HOST/health)"                                              '"ok":true'
check "livez"         "$(curl -s $HOST/livez)"                                               '"ok":true'
check "readyz"        "$(curl -s $HOST/readyz)"                                              '"ready":true'
check "lanes"         "$(curl -s $HOST/v1/lanes)"                                            '"lanes":\['
check "route"         "$(curl -s $HOST/v1/route -H "$J" -d '{"state":"my green bin was not collected","expert":"mairie_c"}')" '"action":"tool_call"'
check "conformal"     "$(curl -s $HOST/v1/route -H "$J" -d '{"state":"my green bin was not collected","expert":"mairie_c"}')" '"qhat":0.648'
check "abstain"       "$(curl -s $HOST/v1/route -H "$J" -d '{"state":"xyzzy quux","expert":"mairie_c"}')" 'conformal_abstain|delegate'
check "decide"        "$(curl -s $HOST/v1/decide -H "$J" -d '{"state":"reset my password please"}')" '"object":"decision"'
check "systemone"     "$(curl -s $HOST/v1/systemone -H "$J" -d '{"state":"Payouts failing for 3 days","model":"jev-latest","questions":{"u":{"type":"noul","instructions":"Does this convey urgency?"}}}')" '"answers"'
check "qhat read"     "$(curl -s $HOST/_qhat)"                                               'mairie_c'
check "gate"          "$(curl -s $HOST/v1/route -H "$J" -d '{"state":"reset my password"}')" '"domain"'
check "bad request"   "$(curl -s -o /dev/null -w '%{http_code}' $HOST/v1/route -H "$J" -d '{}')" '400|422'

echo "---"
if [ $fails = 0 ]; then echo "smoke: all checks passed on $HOST"; else echo "smoke: $fails FAILED on $HOST"; exit 1; fi
