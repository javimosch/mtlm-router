#!/usr/bin/env python3
"""mtlm mail sorter — on-prem sidecar that sorts a shared mailbox with the local mtlm engine.

Runs next to the appliance on the client's machine. Reads new mail over IMAP (read-only peek,
never marks as read), asks the local decision engine (d1 /v1/systemone, choice question over
the client's own categories) and files each mail into "<prefix>/<category>", or into
"<prefix>/<review>" when confidence is below the threshold. Nothing leaves the network:
the only network calls are to the client's IMAP server and to the local engine.

  python3 mail_sorter.py run    --config sorter.json [--once]
  python3 mail_sorter.py report --config sorter.json [--days 7] [--out rapport.md]
  python3 mail_sorter.py check  --config sorter.json      # connectivity + folder listing

Modes (config "mode"):
  "dry-run" (default) — classify + log only, mailbox untouched. Use for the first days.
  "copy"              — copy into the category folder, original stays in the inbox.
  "move"              — move into the category folder (requires the server MOVE extension;
                        refuses otherwise, never falls back to delete+expunge).
Python 3.8+ stdlib only. Config example: sorter.example.json. Secrets: password may be given
via env MTLM_IMAP_PASSWORD instead of the file.
"""
import argparse, email, email.header, html, imaplib, json, os, re, sys, time, urllib.request
from email import policy

DEFAULTS = {"mode": "dry-run", "imap_port": 993, "imap_ssl": True, "source_folder": "INBOX",
            "prefix": "Tri", "review_folder": "A verifier", "threshold": 0.6,
            "engine": "http://127.0.0.1:8410/v1/systemone", "poll_seconds": 60,
            "state_file": "sorter.state.json", "log_file": "decisions.jsonl", "batch": 50}
INSTRUCTION = "Which category does this email received by the company belong to?"  # English: see AGENTS gotcha


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, file=sys.stderr, flush=True)


def load_config(path):
    cfg = dict(DEFAULTS)
    cfg.update(json.load(open(path)))
    cfg["imap_password"] = os.environ.get("MTLM_IMAP_PASSWORD", cfg.get("imap_password", ""))
    for k in ("imap_host", "imap_user", "imap_password", "categories"):
        if not cfg.get(k):
            sys.exit(f"config: missing {k}")
    if cfg["mode"] not in ("dry-run", "copy", "move"):
        sys.exit("config: mode must be dry-run, copy or move")
    base = os.path.dirname(os.path.abspath(path))
    for k in ("state_file", "log_file"):
        if not os.path.isabs(cfg[k]):
            cfg[k] = os.path.join(base, cfg[k])
    return cfg


def connect(cfg):
    cls = imaplib.IMAP4_SSL if cfg["imap_ssl"] else imaplib.IMAP4
    m = cls(cfg["imap_host"], cfg["imap_port"])
    m.login(cfg["imap_user"], cfg["imap_password"])
    return m


def quote(folder):
    return '"' + folder.replace("\\", "\\\\").replace('"', '\\"') + '"'


def folder_name(cfg, m, leaf):
    # use the server's hierarchy delimiter
    typ, data = m.list('""', '""')
    delim = "/"
    if typ == "OK" and data and data[0]:
        mt = re.search(rb'\(.*?\) "(.)"', data[0])
        if mt:
            delim = mt.group(1).decode()
    return f"{cfg['prefix']}{delim}{leaf}"


def ensure_folder(m, name, made):
    if name in made:
        return
    m.create(quote(name))  # fails harmlessly if it exists
    m.subscribe(quote(name))
    made.add(name)


def text_of(msg):
    subj = str(msg.get("Subject", "") or "")
    body = ""
    part = msg.get_body(preferencelist=("plain", "html")) if hasattr(msg, "get_body") else None
    if part is not None:
        try:
            body = part.get_content()
        except Exception:
            body = ""
        if part.get_content_type() == "text/html":
            body = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style).*?</\1>", " ", body)))
    body = re.sub(r"\s+", " ", body).strip()
    return subj, body


def classify(cfg, subj, body):
    state = f"Subject: {subj}\n\n{body[:1200]}"
    req = {"state": state, "questions": {"cat": {"type": "choice", "instructions": INSTRUCTION,
                                                 "criteria": cfg["categories"]}}}
    r = urllib.request.Request(cfg["engine"], json.dumps(req).encode(), {"content-type": "application/json"})
    ans = json.load(urllib.request.urlopen(r, timeout=120))["answers"]["cat"]
    return ans["choice"], float(ans["confidence"])


def load_state(cfg):
    try:
        return json.load(open(cfg["state_file"]))
    except (OSError, ValueError):
        return {}


def save_state(cfg, st):
    tmp = cfg["state_file"] + ".tmp"
    json.dump(st, open(tmp, "w"))
    os.replace(tmp, cfg["state_file"])


def process_once(cfg):
    m = connect(cfg)
    try:
        typ, _ = m.select(quote(cfg["source_folder"]))
        if typ != "OK":
            raise RuntimeError(f"cannot open folder {cfg['source_folder']}")
        uidvalidity = m.response("UIDVALIDITY")[1][0].decode()
        st = load_state(cfg)
        if st.get("uidvalidity") != uidvalidity:  # first run or mailbox rebuilt: start from now
            typ, data = m.uid("search", None, "ALL")
            uids = data[0].split()
            st = {"uidvalidity": uidvalidity, "last_uid": int(uids[-1]) if uids else 0}
            save_state(cfg, st)
            log(f"initialised at uid {st['last_uid']} (existing mail is not touched; use --backfill N to sort recent mail)")
            if not cfg.get("_backfill"):
                return 0
            st["last_uid"] = max(0, st["last_uid"] - cfg["_backfill"])
        typ, data = m.uid("search", None, f"UID {st['last_uid'] + 1}:*")
        uids = [int(u) for u in data[0].split() if int(u) > st["last_uid"]][: cfg["batch"]]
        if not uids:
            return 0
        caps = m.capabilities
        if cfg["mode"] == "move" and "MOVE" not in caps:
            raise RuntimeError("server lacks the IMAP MOVE extension; use mode 'copy'")
        made = set()
        n = 0
        with open(cfg["log_file"], "a") as lf:
            for uid in uids:
                typ, data = m.uid("fetch", str(uid), "(BODY.PEEK[])")
                raw = next((d[1] for d in data if isinstance(d, tuple)), None)
                if raw is None:
                    st["last_uid"] = uid
                    continue
                msg = email.message_from_bytes(raw, policy=policy.default)
                subj, body = text_of(msg)
                choice, conf = classify(cfg, subj, body)
                leaf = choice if conf >= cfg["threshold"] else cfg["review_folder"]
                action = "logged"
                if cfg["mode"] != "dry-run":
                    dest = folder_name(cfg, m, leaf)
                    ensure_folder(m, dest, made)
                    typ, resp = m.uid("move" if cfg["mode"] == "move" else "copy", str(uid), quote(dest))
                    if typ != "OK":
                        raise RuntimeError(f"{cfg['mode']} uid {uid} -> {dest} failed: {resp}")
                    action = f"{cfg['mode']}:{dest}"
                lf.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "uid": uid,
                                     "message_id": str(msg.get("Message-ID", "")), "subject": subj[:200],
                                     "choice": choice, "confidence": round(conf, 4),
                                     "auto": conf >= cfg["threshold"], "action": action},
                                    ensure_ascii=False) + "\n")
                lf.flush()
                st["last_uid"] = uid
                save_state(cfg, st)  # after every mail: a crash never re-sorts or skips
                n += 1
                log(f"uid {uid} -> {leaf} ({conf:.0%}) [{action}] {subj[:60]}")
        return n
    finally:
        try:
            m.logout()
        except Exception:
            pass


def cmd_run(cfg, once):
    while True:
        try:
            n = process_once(cfg)
            cfg["_backfill"] = 0
            if once:
                print(json.dumps({"ok": True, "sorted": n}))
                return
        except Exception as e:  # keep the daemon alive across IMAP/engine hiccups
            log(f"error: {e}")
            if once:
                print(json.dumps({"ok": False, "error": str(e)}))
                sys.exit(1)
        time.sleep(cfg["poll_seconds"])


def cmd_check(cfg):
    out = {"engine": None, "imap": None}
    try:
        classify(cfg, "test", "test")
        out["engine"] = "ok"
    except Exception as e:
        out["engine"] = f"error: {e}"
    try:
        m = connect(cfg)
        typ, data = m.select(quote(cfg["source_folder"]), readonly=True)
        out["imap"] = f"ok, {data[0].decode()} messages in {cfg['source_folder']}, MOVE={'MOVE' in m.capabilities}"
        m.logout()
    except Exception as e:
        out["imap"] = f"error: {e}"
    print(json.dumps(out, ensure_ascii=False))
    sys.exit(0 if out["engine"] == "ok" and out["imap"].startswith("ok") else 1)


def cmd_report(cfg, days, out):
    cutoff = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() - days * 86400))
    rows = []
    if os.path.exists(cfg["log_file"]):
        rows = [json.loads(l) for l in open(cfg["log_file"]) if l.strip()]
    rows = [r for r in rows if r["ts"] >= cutoff]
    # a mail seen in dry-run and later filed for real appears twice: keep its latest decision
    latest = {}
    for r in rows:
        latest[r.get("message_id") or f"uid{r['uid']}"] = r
    rows = list(latest.values())
    auto = [r for r in rows if r["auto"]]
    per = {}
    for r in auto:
        per[r["choice"]] = per.get(r["choice"], 0) + 1
    L = [f"# Rapport de tri — {days} derniers jours", "",
         f"- Mails traités : {len(rows)}",
         f"- Triés automatiquement : {len(auto)}" + (f" ({len(auto) / len(rows):.0%})" if rows else ""),
         f"- Mis de côté pour vérification : {len(rows) - len(auto)}", "",
         "| catégorie | mails |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in sorted(per.items(), key=lambda x: -x[1])]
    review = [r for r in rows if not r["auto"]][:20]
    if review:
        L += ["", "## Mis de côté (extrait)", "", "| objet | proposé | confiance |", "|---|---|---|"]
        L += [f"| {r['subject'][:70].replace('|', '/')} | {r['choice']} | {r['confidence']:.0%} |" for r in review]
    text = "\n".join(L) + "\n"
    if out:
        open(out, "w").write(text)
    print(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("run", "report", "check"))
    ap.add_argument("--config", required=True)
    ap.add_argument("--once", action="store_true", help="one pass then exit (cron-friendly)")
    ap.add_argument("--backfill", type=int, default=0, help="on first run, also sort the last N existing mails")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--out")
    a = ap.parse_args()
    cfg = load_config(a.config)
    cfg["_backfill"] = a.backfill
    if a.cmd == "run":
        cmd_run(cfg, a.once)
    elif a.cmd == "check":
        cmd_check(cfg)
    else:
        cmd_report(cfg, a.days, a.out)


if __name__ == "__main__":
    main()
