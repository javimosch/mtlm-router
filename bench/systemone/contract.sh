#!/bin/sh
# /v1/systemone contract conformance suite.
# Asserts request-shape handling, validation errors, response shapes and
# error typing against the Jev/TypeSafe contract. Not a semantic eval —
# see bench/jevbench for scoring accuracy.
# Usage: HOST=http://localhost:8097 sh bench/systemone/contract.sh
HOST=${HOST:-http://localhost:8097}
J='content-type: application/json'
fails=0; n=0
t() { n=$((n+1)); r=$(eval "$1"); if echo "$r" | grep -qE "$2"; then echo "ok   $n $3"; else echo "FAIL $n $3 -> $(echo "$r"|head -c 140)"; fails=$((fails+1)); fi; }
s1() { curl -s "$HOST/v1/systemone" -H "$J" -d "$1"; }

# --- happy paths: each type returns its shape ---
t "s1 '{\"state\":\"ok\",\"questions\":{\"q\":{\"type\":\"noul\",\"instructions\":\"urgent?\"}}}'" '^{.*"type":"noul","noul":[01]' noul-shape
t "s1 '{\"state\":{\"a\":\"b\"},\"questions\":{\"q\":{\"type\":\"noul\",\"instructions\":\"urgent?\"}}}'" '"noul"' object-state
t "s1 '{\"state\":[\"a\",\"b\"],\"questions\":{\"q\":{\"type\":\"noul\",\"instructions\":\"urgent?\"}}}'" '"noul"' array-state
t "s1 '{\"state\":\"charged twice\",\"questions\":{\"q\":{\"type\":\"choice\",\"instructions\":\"dept\",\"criteria\":{\"billing\":\"b\",\"tech\":\"t\"}}}}'" '"type":"choice","choice":"(billing|tech)"' choice-shape
t "s1 '{\"state\":\"x\",\"questions\":{\"q\":{\"type\":\"choice\",\"instructions\":\"d\",\"criteria\":{\"a\":\"x\",\"b\":\"y\"}}}}'" '"probabilities":{[^}]*"a":[0-9]' choice-probabilities
t "s1 '{\"state\":\"x\",\"questions\":{\"q\":{\"type\":\"choice\",\"instructions\":\"d\",\"options\":[\"a\",\"b\",\"c\"]}}}'" '"choice":"(a|b|c)"' options-array-shorthand
t "s1 '{\"state\":\"terrible\",\"questions\":{\"q\":{\"type\":\"score\",\"instructions\":\"rate\",\"criteria\":[\"low\",\"medium\",\"high\"]}}}'" '"type":"score","score":[0-9]' score-shape
t "s1 '{\"state\":\"x\",\"questions\":{\"q\":{\"type\":\"score\",\"instructions\":\"r\",\"criteria\":[\"a\",\"b\"]}}}'" '"legend":{[^}]*"0":"a"' score-legend

# --- multi-question answers keyed by request ids ---
t "s1 '{\"state\":\"x\",\"questions\":{\"u\":{\"type\":\"noul\",\"instructions\":\"y?\"},\"d\":{\"type\":\"choice\",\"instructions\":\"w\",\"criteria\":{\"a\":\"x\",\"b\":\"y\"}}}}'" '"u".*"d"' multi-question-keys

# --- validation / error contract ---
t "s1 '{\"questions\":{\"u\":{\"type\":\"noul\",\"instructions\":\"x\"}}}'" 'state required' missing-state-400
t "s1 '{\"state\":\"x\"}'" 'questions required' missing-questions-400
t "s1 '{\"state\":\"x\",\"questions\":{\"q\":{\"type\":\"bogus\",\"instructions\":\"x\"}}}'" 'unknown question type' bad-type-422
t "s1 '{\"state\":\"x\",\"questions\":{\"q\":{\"type\":\"choice\",\"instructions\":\"x\",\"criteria\":{}}}}'" 'criteria must not be empty' empty-choice-422
t "s1 '{\"state\":\"x\",\"questions\":{\"q\":{\"type\":\"noul\",\"instructions\":\"x\",\"criteria\":{\"maybe\":\"no\"}}}}'" 'true/false' noul-bad-criteria-422
t "s1 '{\"state\":\"x\",\"questions\":{\"q\":{\"type\":\"score\",\"instructions\":\"x\",\"criteria\":[\"only\"]}}}'" '2..10 levels' score-min-levels-422
LONG=$(python3 -c "print('word '*800)")
t "s1 '{\"state\":\"$LONG\",\"questions\":{\"q\":{\"type\":\"noul\",\"instructions\":\"x\"}}}'" 'max_tokens_exceeded' overflow-error-type
t "curl -s -o /dev/null -w '%{http_code}' $HOST/v1/systemone -H '$J' -d '{\"state\":\"x\",\"questions\":{\"q\":{\"type\":\"bogus\",\"instructions\":\"x\"}}}'" '422' bad-type-status

# --- meta ---
t "s1 '{\"state\":\"x\",\"questions\":{\"q\":{\"type\":\"noul\",\"instructions\":\"x\"}}}'" '"usage":{"input_tokens":[0-9]+,"output_tokens":[0-9]+}' usage-fields
t "s1 '{\"model\":\"jev-latest\",\"state\":\"x\",\"questions\":{\"q\":{\"type\":\"noul\",\"instructions\":\"x\"}}}'" '"noul"' model-field-accepted

echo "---"; echo "contract: $((n-fails))/$n passed"
[ $fails = 0 ]
