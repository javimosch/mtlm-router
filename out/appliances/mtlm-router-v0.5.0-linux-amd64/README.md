# mtlm-router appliance

Self-hosted typed decision layer — 7M-param router + decision heads, pure MFL,
no dependencies beyond a Linux x86_64 box.

## Run

    ./start.sh                 # systemd-free
    ./smoke.sh                 # verifies all endpoints + the conformal gate
    python3 tools/monitor.py logs/decisions.jsonl   # label-free drift check (exit 1 on drift)
    python3 tools/shadow_report.py logs/decisions.jsonl  # canary verdict: promote(0)/hold(2)/wait(3)
    cat ops/RUNBOOK.md                # day-2 ops: probes, maintenance loop, canary, recalibration
    # or: cp mtlm-router.service ~/.config/systemd/user/ && systemctl --user start mtlm-router

## Use

    curl localhost:8097/v1/route -H 'content-type: application/json' \
        -d '{"state":"remind me to call the dentist tomorrow","execute":true}'
    # {"action":"tool_call","route":"set_reminder","confidence":0.99,...}

With a gate head + experts loaded, the same call answers domain/expert too:

    {"action":"tool_call","route":"ticket_status","confidence":0.86,
     "domain":"it_helpdesk","gate_confidence":0.99,"expert":"it_helpdesk",...}

Endpoints: /v1/route (dispatcher), /v1/decide /v1/noul /v1/score /v1/assess
(typed heads), /v1/chat/completions (generative), /health.

manifest.json records sha256 of every shipped artifact and the eval of the
gate/head set at packaging time — check it before trusting confidences.

Docs: github.com/javimosch/mtlm-router · HF: javimosch/mtlm-7m-router3s384
