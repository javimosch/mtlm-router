"""Synthetic-fixture tests for tools/lane_verify.py.

Each check gets a mutated pack that must fail it plus the clean pack
that must pass — Guerrilla's PASS/FAIL/NOT-ASSESSED pattern applied to
the pre-publish gate. Run: python3 -m unittest tests.test_lane_verify -v
"""
import hashlib, io, json, os, struct, sys, tarfile, tempfile, unittest
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import lane_verify


def head_bytes(labels=("alpha", "beta"), taps=((2, 4), (2, 5)), temp=1.0):
    """mhd3 writer-side fixture: taps as (kind, layer_plus1), kind 2=mean."""
    nr, fd = len(labels), 4
    W = np.zeros((nr, fd), np.float32)
    b = np.zeros(nr, np.float32)
    out = io.BytesIO()
    out.write(b"mhd3")
    out.write(struct.pack("<ii", nr, fd))
    out.write(struct.pack("<f", temp))
    out.write(struct.pack("<B", len(taps)))
    for k, lp1 in taps:
        out.write(struct.pack("<BB", k, lp1))
    out.write(W.tobytes())
    out.write(b.tobytes())
    for l in labels:
        out.write(bytes([len(l)]))
        out.write(l.encode())
    return out.getvalue()


def make_pack(tmpdir, name="t", version="0.1.0", labels=("alpha", "beta"),
              manifest_over=None, head=None, drop=(), eval_over=None,
              taps_decl="mean@-2,-3"):
    """Build a .lanepack.tar.gz; returns path."""
    head = head if head is not None else head_bytes(labels)
    man = {
        "format": "lanepack/1", "name": name, "version": version,
        "created": 1, "head_sha256": hashlib.sha256(head).hexdigest(),
        "taxonomy": list(labels),
        "metrics": {"holdout_acc": 0.9, "n_holdout": 100, "taps": taps_decl},
        "status": "certified", "live_verified": True,
        "provenance": "test", "license": "LICENSE.txt", "runtime": "anvil-serve >= v0.3.0",
    }
    man.update(manifest_over or {})
    ev = {"holdout_acc": 0.9, "n_holdout": 100}
    ev.update(eval_over or {})
    members = {
        "manifest.json": json.dumps(man).encode(),
        "eval.json": json.dumps(ev).encode(),
        "labels.txt": "\n".join(f"{l} :: {l}" for l in labels).encode(),
        "LICENSE.txt": b"test license",
        "t.head": head,
    }
    for k in drop:
        members.pop(k)
    path = os.path.join(tmpdir, f"{name}-{version}.lanepack.tar.gz")
    with tarfile.open(path, "w:gz") as t:
        for n, b in members.items():
            ti = tarfile.TarInfo(n)
            ti.size = len(b)
            t.addfile(ti, io.BytesIO(b))
    return path


class TestVerify(unittest.TestCase):
    def v(self, **kw):
        with tempfile.TemporaryDirectory() as d:
            return lane_verify.verify_pack(make_pack(d, **kw))

    def test_clean_pack_passes(self):
        rep, code = self.v()
        self.assertEqual(code, 0, rep["errors"])
        self.assertTrue(rep["ok"])

    def test_missing_member(self):
        rep, code = self.v(drop=("eval.json",))
        self.assertEqual(code, 1)
        self.assertIn("missing eval.json", rep["errors"][0])

    def test_head_sha_mismatch(self):
        rep, code = self.v(manifest_over={"head_sha256": "0" * 64})
        self.assertEqual(code, 1)
        self.assertTrue(any("sha256" in e for e in rep["errors"]))

    def test_taxonomy_labels_mismatch(self):
        rep, code = self.v(manifest_over={"taxonomy": ["alpha", "gamma"]})
        self.assertEqual(code, 1)
        self.assertTrue(any("taxonomy/labels" in e for e in rep["errors"]))

    def test_bad_magic(self):
        rep, code = self.v(head=b"XXXX" + head_bytes()[4:])
        self.assertEqual(code, 1)
        self.assertTrue(any("magic" in e for e in rep["errors"]))

    def test_embedded_label_drift(self):
        """head embeds labels taxonomy doesn't declare — the 0.1.1 class."""
        rep, code = self.v(head=head_bytes(labels=("alpha", "gamma")))
        self.assertEqual(code, 1)
        self.assertTrue(any("non-taxonomy" in e or "lacks" in e for e in rep["errors"]))

    def test_declared_taps_mismatch(self):
        rep, code = self.v(taps_decl="mean@-2")
        self.assertEqual(code, 1)
        self.assertTrue(any("taps" in e for e in rep["errors"]))

    def test_certified_needs_holdout(self):
        rep, code = self.v(manifest_over={"metrics": {"n_holdout": 10}})
        self.assertEqual(code, 1)
        self.assertTrue(any("certified" in e for e in rep["errors"]))

    def test_abstain_class_no_oos_metrics_warns(self):
        rep, code = self.v(labels=("alpha", "oos"), taps_decl="mean@-2,-3")
        self.assertEqual(code, 0, rep["errors"])
        self.assertTrue(any("abstention" in w or "oos" in w for w in rep["warnings"]))

    def test_live_verified_grandfather_warns(self):
        rep, code = self.v(manifest_over={"live_verified": False})
        self.assertEqual(code, 0)
        self.assertTrue(any("live_verified" in w for w in rep["warnings"]))

    def test_demo_status_no_certified_gate(self):
        rep, code = self.v(manifest_over={"status": "demo", "metrics": {}})
        self.assertTrue(rep["ok"], rep["errors"])


if __name__ == "__main__":
    unittest.main()
