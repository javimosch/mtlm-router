#!/usr/bin/env python3
"""Verify an mtlm-router appliance tarball or extracted tree against its manifest.

manifest.json records the sha256 of every shipped artifact (model, tokenizer,
heads, gate, expert lanes). This checks those digests against the files on
disk — a corruption/tamper tripwire short of a signature (checksums prove the
bytes match the manifest, not who wrote the manifest).

Usage:
    python3 tools/verify_appliance.py mtlm-router-v0.10.0-linux-amd64.tar.gz
    python3 tools/verify_appliance.py ./mtlm-router-v0.10.0-linux-amd64/
    python3 tools/verify_appliance.py <path> --json
Exit 0 when every manifest digest verifies; 1 otherwise.
"""
import hashlib, io, json, os, sys, tarfile

def digests(manifest):
    want = {}
    for k in ("model", "tokenizer", "gate"):
        if k in manifest and isinstance(manifest[k], dict):
            want[manifest[k]["file"]] = manifest[k]["sha256"]
    for name, sha in (manifest.get("heads") or {}).items():
        want["models/" + name] = sha
    for lane, spec in (manifest.get("experts") or {}).items():
        if isinstance(spec, dict):
            want[spec["file"]] = spec["sha256"]
    return want

def sha256_stream(f):
    h = hashlib.sha256()
    for chunk in iter(lambda: f.read(1 << 20), b""):
        h.update(chunk)
    return h.hexdigest()

def verify_dir(root, want):
    out = {}
    for rel, sha in want.items():
        p = os.path.join(root, rel)
        if not os.path.exists(p):
            out[rel] = {"ok": False, "error": "missing"}
            continue
        with open(p, "rb") as f:
            got = sha256_stream(f)
        out[rel] = {"ok": got == sha, "sha256": got}
    return out

def verify_tar(path, want):
    out = {}
    with tarfile.open(path) as t:
        names = {m.name: m for m in t.getmembers() if m.isfile()}
        for rel, sha in want.items():
            hit = [n for n in names if n == rel or n.endswith("/" + rel)]
            if not hit:
                out[rel] = {"ok": False, "error": "missing"}
                continue
            got = sha256_stream(t.extractfile(names[hit[0]]))
            out[rel] = {"ok": got == sha, "sha256": got}
    return out

def load_manifest(path):
    if os.path.isdir(path):
        return json.load(open(os.path.join(path, "manifest.json")))
    with tarfile.open(path) as t:
        for m in t.getmembers():
            if m.name.endswith("manifest.json"):
                return json.load(t.extractfile(m))
    sys.exit("manifest.json not found in " + path)

def main():
    as_json = "--json" in sys.argv
    path = next(a for a in sys.argv[1:] if not a.startswith("--"))
    manifest = load_manifest(path)
    want = digests(manifest)
    res = verify_dir(path, want) if os.path.isdir(path) else verify_tar(path, want)
    bad = {k: v for k, v in res.items() if not v["ok"]}
    report = {"package": manifest.get("name"), "built": manifest.get("built"),
              "artifacts": len(res), "verified": len(res) - len(bad),
              "failures": bad, "ok": not bad}
    if as_json:
        print(json.dumps(report, indent=1))
    else:
        print(f"{report['package']} (built {report['built']}): "
              f"{report['verified']}/{len(res)} artifact digests verified")
        for k, v in bad.items():
            print(f"  FAIL {k}: {v.get('error') or 'digest mismatch'}")
        if not bad:
            print("verify: all manifest digests match")
    sys.exit(0 if not bad else 1)

if __name__ == "__main__":
    main()
