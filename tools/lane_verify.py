#!/usr/bin/env python3
"""Verify a .lanepack.tar.gz artifact — integrity + schema + honesty.

Checks:
  1. tarball sha256 matches an optional SHA256SUMS line (--sums file)
  2. head file sha256 matches manifest.head_sha256
  3. manifest schema: format/name/version/taxonomy/metrics/provenance/license present
  4. labels.txt taxonomy agrees with manifest.taxonomy
  5. honesty gate: 'certified' claims require metrics.holdout_acc + n_holdout
  6. head magic 0x3364686d (mhd3) and embedded label count vs taxonomy

Exit 0 ok / 1 failure. Stdlib only.

  python3 tools/lane_verify.py eq_tone-0.1.0.lanepack.tar.gz [--sums SHA256SUMS.txt]
"""
import argparse, hashlib, json, os, struct, sys, tarfile


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fail(msg, errs):
    errs.append(msg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pack")
    ap.add_argument("--sums", help="SHA256SUMS.txt-style file to check tarball against")
    a = ap.parse_args()
    errs = []

    if a.sums:
        want = None
        base = os.path.basename(a.pack)
        for line in open(a.sums):
            parts = line.split()
            if len(parts) >= 2 and os.path.basename(parts[-1]) == base:
                want = parts[0]
        if want is None:
            fail(f"{base} not listed in {a.sums}", errs)
        elif sha256(a.pack) != want:
            fail(f"tarball sha256 mismatch vs {a.sums}", errs)

    if not tarfile.is_tarfile(a.pack):
        fail("not a tar.gz", errs)
        print(json.dumps({"pack": a.pack, "ok": False, "errors": errs}))
        sys.exit(1)

    members = {}
    with tarfile.open(a.pack) as t:
        for m in t.getmembers():
            if m.isfile():
                members[os.path.basename(m.name)] = t.extractfile(m).read()

    for req in ("manifest.json", "eval.json", "labels.txt", "LICENSE.txt"):
        if req not in members:
            fail(f"missing {req}", errs)
    heads = [n for n in members if n.endswith(".head")]
    if len(heads) != 1:
        fail(f"expected exactly one .head, got {heads}", errs)

    if errs:
        print(json.dumps({"pack": a.pack, "ok": False, "errors": errs}))
        sys.exit(1)

    man = json.loads(members["manifest.json"])
    for k in ("format", "name", "version", "head_sha256", "taxonomy", "metrics", "provenance", "license"):
        if k not in man:
            fail(f"manifest missing {k}", errs)
    if man.get("format") != "lanepack/1":
        fail(f"unknown format {man.get('format')}", errs)

    head = members[heads[0]]
    if hashlib.sha256(head).hexdigest() != man.get("head_sha256"):
        fail("head sha256 != manifest.head_sha256", errs)

    tax_labels = set(man.get("taxonomy", []))
    file_labels = {l.split("::")[0].strip() for l in members["labels.txt"].decode().splitlines() if "::" in l}
    if tax_labels != file_labels:
        fail(f"taxonomy/labels mismatch: {sorted(tax_labels ^ file_labels)}", errs)

    # head binary sanity: magic + label count
    if len(head) >= 8:
        magic, ncls = struct.unpack("<ii", head[:8])
        if magic not in (0x3164686D, 0x3264686D, 0x3364686D):
            fail(f"bad head magic {magic:#x}", errs)
        else:
            # mhd2+ embeds label names at file end; mhd2 can carry a "chat" fallback
            extra = ncls - len(tax_labels)
            if extra < 0 or extra > 1:
                fail(f"head declares {ncls} classes, taxonomy has {len(tax_labels)}", errs)
            elif extra == 1:
                tail = members[heads[0]][-512:]
                if not any(t in tail for t in (b"chat", b"oos")):
                    fail(f"head has {ncls} classes vs {len(tax_labels)} taxonomy; extra is not a known fallback", errs)

    # honesty gate: 'certified' must carry a leak-free eval
    metrics = man.get("metrics", {})
    certified = man.get("status") == "certified" or man.get("certified") is True
    if certified and not (metrics.get("holdout_acc") is not None and metrics.get("n_holdout")):
        fail("claimed certified but metrics lack holdout_acc/n_holdout", errs)
    if "status" in man and man["status"] not in ("certified", "demo"):
        fail(f"unknown status {man['status']}", errs)

    ok = not errs
    print(json.dumps({
        "pack": a.pack, "ok": ok,
        "name": man.get("name"), "version": man.get("version"),
        "classes": len(tax_labels), "holdout_acc": metrics.get("holdout_acc"),
        "errors": errs}))
    sys.exit(0 if ok else 1)


main()
