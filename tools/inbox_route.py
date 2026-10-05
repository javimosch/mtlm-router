#!/usr/bin/env python3
"""inbox_route.py — route a mailbox through an mtlm-router head.

Reads a maildir (or a directory of .eml files, or an mbox), sends each
message's subject + body to POST <router>/v1/route, and either:

  --jsonl out.jsonl   write one decision per line
  --sort DIR          copy each message into DIR/<route>/ as .eml
                      ('delegate'/'unrouted' get their own folders)

No dependencies beyond the stdlib. This is the integrator-facing connector:
plug a mailbox export in, get routed folders + an auditable decision log out.

Usage:
  inbox_route.py --router http://localhost:8401 --maildir ./inbox \
      --jsonl decisions.jsonl --sort sorted/
  inbox_route.py --router http://localhost:8401 --mbox mbox --jsonl d.jsonl
"""
import argparse, email, json, mailbox, sys, urllib.request
from pathlib import Path

def msg_text(msg, limit=2000):
    subj = str(msg.get("Subject", ""))
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    body = part.get_payload(decode=True).decode(
                        part.get_content_charset() or "utf-8", "replace")
                    break
                except Exception:
                    pass
    else:
        try:
            body = msg.get_payload(decode=True).decode(
                msg.get_content_charset() or "utf-8", "replace")
        except Exception:
            body = str(msg.get_payload())
    return f"{subj}\n{body}".strip()[:limit]

def iter_msgs(args):
    p = Path(args.mbox or args.maildir)
    if args.mbox:
        for m in mailbox.mbox(str(p)):
            yield None, m.as_bytes(), m
    elif (p / "cur").is_dir():
        for key in mailbox.Maildir(str(p), create=False):
            m = mailbox.Maildir(str(p), create=False)[key]
            yield key, m.as_bytes(), m
    else:
        for f in sorted(p.glob("*.eml")):
            yield f.name, f.read_bytes(), email.message_from_bytes(f.read_bytes())

def route(router, state, timeout):
    req = urllib.request.Request(
        router.rstrip("/") + "/v1/route",
        data=json.dumps({"state": state}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--router", required=True)
    ap.add_argument("--maildir"); ap.add_argument("--mbox")
    ap.add_argument("--jsonl"); ap.add_argument("--sort")
    ap.add_argument("--timeout", type=float, default=10.0)
    a = ap.parse_args()
    out = open(a.jsonl, "w") if a.jsonl else None
    n = {"routed": 0, "delegated": 0, "failed": 0}
    for i, (key, raw, msg) in enumerate(iter_msgs(a)):
        state = msg_text(msg)
        try:
            r = route(a.router, state, a.timeout)
            rec = {"i": i, "subject": str(msg.get("Subject", ""))[:120],
                   "route": r.get("route"), "confidence": r.get("confidence"),
                   "action": r.get("action"), "p_yes": r.get("p_yes"),
                   "latency_ms": r.get("latency_ms")}
        except Exception as e:
            rec = {"i": i, "subject": str(msg.get("Subject", ""))[:120],
                   "error": str(e)}
        lane = "routed" if rec.get("action") == "tool_call" else \
               "failed" if "error" in rec else "delegated"
        n[lane] += 1
        if out: out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if a.sort:
            d = Path(a.sort) / (rec.get("route") or lane)
            d.mkdir(parents=True, exist_ok=True)
            (d / f"{i:05d}.eml").write_bytes(raw)
        print(f"[{lane}] {rec.get('route')} {rec.get('confidence','')} {rec['subject'][:60]}")
    print(json.dumps(n))
    if out: out.close()

if __name__ == "__main__":
    main()
