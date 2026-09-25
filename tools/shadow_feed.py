#!/usr/bin/env python3
"""Shadow-feed real requests into the router — observation only.

Fetches recent GitHub issues and fires each at /v1/route. The server's
ANVIL_LOG records the decisions; harvest_gate.py later turns the confident
agreed ones into gate corpus rows. Nothing is executed — this is the
flywheel's raw-material pump. Runs against real repos so the fleet_gate
lane thickens on real distribution, not synthetic prompts.

  python3 tools/shadow_feed.py \
    --router http://100.67.28.60:8401 \
    --repos javimosch/machin,javimosch/mtlm-router --limit 20 \
    --seen /root/mtlm/logs/shadow_seen.txt
"""
import argparse, json, subprocess, sys, urllib.request

def issues(repo, limit):
    out = subprocess.run(
        ["gh", "issue", "list", "--repo", repo, "--state", "open",
         "--limit", str(limit), "--json", "number,title,body"],
        capture_output=True, text=True)
    if out.returncode != 0:
        print(f"gh failed for {repo}: {out.stderr.strip()}", file=sys.stderr)
        return []
    return json.loads(out.stdout or "[]")

def route(router, state):
    body = json.dumps({"state": state}).encode()
    req = urllib.request.Request(router + "/v1/route", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--router", required=True)
    ap.add_argument("--repos", required=True, help="comma-separated owner/name")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--seen", required=True)
    a = ap.parse_args()

    try:
        seen = set(open(a.seen).read().split())
    except FileNotFoundError:
        seen = set()

    fed, skipped, errors = 0, 0, 0
    for repo in a.repos.split(","):
        repo = repo.strip()
        for iss in issues(repo, a.limit):
            k = f"{repo}#{iss['number']}"
            if k in seen:
                skipped += 1
                continue
            # 384-token context: serving prompt + template eats ~110 tok —
            # ~450 chars is the safe state budget (verified vs head_probe).
            title = iss.get("title") or ""
            body = (iss.get("body") or "")[:400]
            state = (title + "\n\n" + body)[:450]
            r = route(a.router, state)
            if "error" in r and "400" in r["error"]:
                r = route(a.router, state[:220])  # dense text: retry halved
            if "error" in r:
                errors += 1
                print(f"{k}: {r['error']}", file=sys.stderr)
                continue  # not seen — retry next run
            seen.add(k)
            fed += 1
            print(f"{k}: {r.get('domain')}({r.get('gate_confidence',0):.2f}) "
                  f"-> {r.get('route')} {r.get('action')}")

    with open(a.seen, "w") as f:
        f.write("\n".join(sorted(seen)))
    print(json.dumps({"fed": fed, "skipped": skipped, "errors": errors}))
    return 0

if __name__ == "__main__":
    sys.exit(main())
