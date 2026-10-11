#!/usr/bin/env python3
"""Fixture tests for tools/lane_install.py — synthetic index + pack tarballs
served over file://, run via the real CLI (subprocess)."""
import hashlib, io, json, os, subprocess, sys, tarfile, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(ROOT, "tools", "lane_install.py")


def make_pack(head_bytes, labels, extra_eval=None):
    head_sha = hashlib.sha256(head_bytes).hexdigest()
    man = {"name": "x", "head": "x.head", "head_sha256": head_sha}
    evalj = {"holdout": {"acc": 0.9}}
    if extra_eval:
        evalj.update(extra_eval)
    files = {"manifest.json": json.dumps(man).encode(),
             "x.head": head_bytes,
             "labels.txt": ("\n".join(labels) + "\n").encode(),
             "eval.json": json.dumps(evalj).encode()}
    bio = io.BytesIO()
    with tarfile.open(fileobj=bio, mode="w:gz") as t:
        for name, data in files.items():
            ti = tarfile.TarInfo(name)
            ti.size = len(data)
            t.addfile(ti, io.BytesIO(data))
    return bio.getvalue()


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.dir = os.path.join(self.tmp, "reg")
        os.makedirs(self.dir)
        # lane demo: 1.0 yanked -> 2.0 live; lane solo: only yanked version exists
        self.packs = {}
        for tag, blob in [("demo-1.0", make_pack(b"HEAD10", ["a", "b"])),
                          ("demo-2.0", make_pack(b"HEAD20", ["a", "b"])),
                          ("demo-9.9", make_pack(b"HEAD99", ["a", "b"])),
                          ("solo-1.0", make_pack(b"HEADS", ["a"]))]:
            p = os.path.join(self.dir, tag + ".tar.gz")
            open(p, "wb").write(blob)
            self.packs[tag] = p

        def lane(name, ver, tag, **kw):
            d = {"name": name, "version": ver,
                 "url": "file://" + self.packs[tag],
                 "sha256": hashlib.sha256(open(self.packs[tag], "rb").read()).hexdigest(),
                 "status": "certified", "holdout_acc": 0.9}
            d.update(kw)
            return d

        self.index = {"lanes": [
            lane("demo", "1.0", "demo-1.0", yanked=True,
                 superseded_by="demo@2.0", yank_reason="demo pack"),
            lane("demo", "2.0", "demo-2.0",
                 operating={"min_conf": 0.7, "note": "weak argmax, floor rescues"}),
            # newest version of demo is yanked — unpinned install must NOT pick it
            lane("demo", "9.9", "demo-9.9", yanked=True,
                 superseded_by="demo@2.0", yank_reason="bad head"),
            lane("solo", "1.0", "solo-1.0", yanked=True,
                 superseded_by=None, yank_reason="withdrawn"),
        ]}
        self.idx = os.path.join(self.dir, "index.json")
        json.dump(self.index, open(self.idx, "w"))
        self.app = os.path.join(self.tmp, "app")
        os.makedirs(os.path.join(self.app, "models"))
        open(os.path.join(self.app, "start.sh"), "w").write("#!/bin/sh\nexec anvil\n")

    def run_cli(self, *args):
        p = subprocess.run([sys.executable, CLI, "--index", "file://" + self.idx,
                            "--appliance", self.app, *args],
                           capture_output=True, text=True)
        try:
            return p.returncode, json.loads(p.stdout)
        except json.JSONDecodeError:
            return p.returncode, {"_raw": p.stdout, "_err": p.stderr}

    def test_unpinned_skips_yanked(self):
        # demo@1.0 is yanked but newest-would-be logic must still pick live 2.0
        rc, out = self.run_cli("demo")
        self.assertEqual(rc, 0, out)
        self.assertEqual(out["lane"], "demo@2.0")

    def test_unpinned_all_yanked_fails(self):
        rc, out = self.run_cli("solo")
        self.assertEqual(rc, 1)
        self.assertFalse(out["ok"])

    def test_pinned_yanked_warns_but_installs(self):
        rc, out = self.run_cli("demo@1.0")
        self.assertEqual(rc, 0, out)
        self.assertTrue(any("yanked" in w for w in out["warnings"]), out)
        self.assertTrue(os.path.exists(os.path.join(self.app, "models", "x.head")))

    def test_apply_writes_minconf_floor(self):
        rc, out = self.run_cli("demo", "--apply")
        self.assertEqual(rc, 0, out)
        text = open(os.path.join(self.app, "start.sh")).read()
        self.assertIn("ANVIL_EXPERT_MINCONF", text)
        self.assertIn("demo:0.7", text)
        self.assertIn("minconf=0.7", text)
        # uninstall regenerates the block and preserves nothing stale
        self.run_cli("--uninstall", "demo")
        self.assertNotIn("ANVIL_EXPERT_MINCONF", open(os.path.join(self.app, "start.sh")).read())

    def test_apply_writes_managed_block(self):
        rc, out = self.run_cli("demo", "--apply")
        self.assertEqual(rc, 0, out)
        rc, out = self.run_cli("--list")
        self.assertEqual(rc, 0)
        self.assertEqual(out["lanes"][0]["name"], "demo")
        self.assertEqual(out["lanes"][0]["ver"], "2.0")

    def test_check_flags_installed_yanked(self):
        # install yanked 1.0 pinned, then --check must flag outdated + yanked
        self.run_cli("demo@1.0", "--apply")
        rc, out = self.run_cli("--check")
        self.assertEqual(rc, 1)
        row = out["lanes"][0]
        self.assertEqual(row["status"], "outdated")
        self.assertTrue(row["installed_yanked"])
        self.assertEqual(row["superseded_by"], "demo@2.0")

    def test_check_current_is_clean(self):
        self.run_cli("demo", "--apply")
        rc, out = self.run_cli("--check")
        self.assertEqual(rc, 0)
        self.assertEqual(out["lanes"][0]["status"], "current")

    def test_check_no_managed_lanes(self):
        rc, out = self.run_cli("--check")
        self.assertEqual(rc, 0)
        self.assertEqual(out["lanes"], [])

    def test_unknown_lane_errors(self):
        rc, out = self.run_cli("nope")
        self.assertEqual(rc, 1)
        self.assertFalse(out["ok"])

    def test_sha_mismatch_refuses(self):
        self.index["lanes"][1]["sha256"] = "0" * 64
        json.dump(self.index, open(self.idx, "w"))
        rc, out = self.run_cli("demo")
        self.assertEqual(rc, 1)
        self.assertIn("sha256", out["error"])


if __name__ == "__main__":
    unittest.main()
