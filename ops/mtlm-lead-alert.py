#!/usr/bin/env python3
"""Poll bkn forms (form name mtlm-*) for new submissions and alert via perrus's Telegram bot.

Runs on dk1 (installed at /home/dk1/mtlm-lead-alert.py). State: ~/.mtlm-lead-alert.state
(last seen created_at). The bot token is read from perrus config at runtime, never copied.
  --seed   mark everything currently in the db as seen (no alerts)
"""
import json, os, re, sqlite3, sys, urllib.parse, urllib.request

DB = "/opt/bkn/home/bkn.db"
CFG = "/home/dk1/perrus-cli/config.yaml"
STATE = os.path.expanduser("~/.mtlm-lead-alert.state")

con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
if "--seed" in sys.argv:
    m = con.execute("select max(created_at) from records where ns='forms' and coll='submissions'").fetchone()[0] or ""
    open(STATE, "w").write(m)
    print("seeded", m)
    sys.exit(0)

cfg = open(CFG).read()
tok = re.search(r"bot_token:\s*['\"]?([^'\"\s]+)", cfg).group(1)
chat = re.search(r"chat_id:\s*['\"]?([^'\"\s]+)", cfg).group(1)
last = open(STATE).read().strip() if os.path.exists(STATE) else ""
rows = con.execute(
    "select created_at, doc from records where ns='forms' and coll='submissions' and created_at > ? order by created_at",
    (last,)).fetchall()
for created, doc in rows:
    d = json.loads(doc)
    if d.get("form", "").startswith("mtlm"):
        f = d.get("fields", {})
        lines = [f"mtlm lead ({d['form']})"] + [f"{k}: {v}" for k, v in f.items()]
        lines += [f"ref: {d.get('referer')}", f"at: {created}"]
        body = urllib.parse.urlencode({"chat_id": chat, "text": "\n".join(lines)}).encode()
        urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", body, timeout=15).read()
    open(STATE, "w").write(created)
