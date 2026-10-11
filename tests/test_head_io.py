"""Golden-fixture tests for tools/head_io.py — the canonical mhd2/mhd3 parser.

Each fixture is built from the WRITER side of the spec (same byte layout
anvil's read_head expects), so a parser regression fails here before it
ships. Run: python3 -m unittest tests.test_head_io -v
"""
import struct, sys, tempfile, os, unittest
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import head_io


def write_mhd3(path, labels, W, b, temp, taps):
    """taps: list of (kind, layer_plus1); kind 1=max 2=mean."""
    nr, fd = W.shape
    with open(path, "wb") as f:
        f.write(b"mhd3")
        f.write(struct.pack("<ii", nr, fd))
        f.write(struct.pack("<f", temp))
        f.write(struct.pack("<B", len(taps)))
        for k, lp1 in taps:
            f.write(struct.pack("<BB", k, lp1))
        f.write(W.astype(np.float32).tobytes())
        f.write(b.astype(np.float32).tobytes())
        for l in labels:
            f.write(bytes([len(l)]))
            f.write(l.encode())


def write_mhd2(path, labels, W, b, temp, kind, layer):
    """flags = pool_kind | ((layer+1) << 4) at byte 16; weights at 20."""
    nr, fd = W.shape
    flags = kind | ((layer + 1) << 4)
    with open(path, "wb") as f:
        f.write(b"mhd2")
        f.write(struct.pack("<ii", nr, fd))
        f.write(struct.pack("<f", temp))
        f.write(struct.pack("<I", flags))
        f.write(W.astype(np.float32).tobytes())
        f.write(b.astype(np.float32).tobytes())
        for l in labels:
            f.write(bytes([len(l)]))
            f.write(l.encode())


def rng_W(nr, fd):
    g = np.random.default_rng(3)
    return g.normal(0, 1, (nr, fd)).astype(np.float32)


class TestMhd3(unittest.TestCase):
    def test_taps_from_header(self):
        """mairie-style taps: 3x max at anvil layers 2,4,3 -> hf -4,-2,-3."""
        W, b = rng_W(3, 8), np.zeros(3, np.float32)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "h.head")
            write_mhd3(p, ["a", "b", "c"], W, b, 1.0,
                       [(1, 3), (1, 5), (1, 4)])  # max @ layers 2,4,3
            h = head_io.load_head(p, n_layers=6)
        self.assertEqual(h["taps"], [(-4, "max"), (-2, "max"), (-3, "max")])
        self.assertEqual(h["magic"], "mhd3")
        self.assertEqual(h["n_classes"], 3)

    def test_kind_map_mean_not_last(self):
        """kind=2 is mean — the regression from the mhd2-fix pass."""
        W, b = rng_W(2, 4), np.zeros(2, np.float32)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "h.head")
            write_mhd3(p, ["x", "y"], W, b, 1.0, [(2, 7)])  # mean @ layer 6
            h = head_io.load_head(p, n_layers=6)
        self.assertEqual(h["taps"], [(0, "mean")])

    def test_W_row_major(self):
        """W is (n_classes, featdim): swapping a row must move the logit."""
        W = np.array([[1.0, 0.0, 0.0, 0.0],
                      [0.0, 1.0, 0.0, 0.0]], np.float32)
        b = np.zeros(2, np.float32)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "h.head")
            write_mhd3(p, ["first", "second"], W, b, 1.0, [(2, 7)])
            h = head_io.load_head(p)
        X = np.array([[1.0, 0, 0, 0], [0, 1.0, 0, 0]], np.float32)
        P = head_io.probs(h, X)
        self.assertEqual(int(P[0].argmax()), 0)  # row 0 fires class 0
        self.assertEqual(int(P[1].argmax()), 1)


class TestMhd2(unittest.TestCase):
    def test_flags_word_layout(self):
        """0x42 = mean(kind2) @ layer3 — the byte-16 flags regression."""
        W, b = rng_W(6, 8), np.zeros(6, np.float32)
        labels = [f"c{i}" for i in range(6)]
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "h.head")
            write_mhd2(p, labels, W, b, 1.5, kind=2, layer=3)  # flags=0x42
            h = head_io.load_head(p)
        self.assertEqual(h["taps"], [(-3, "mean")])  # layer3 -> 3-6 = -3
        self.assertEqual(h["temp"], 1.5)
        self.assertEqual(h["labels"], labels)
        np.testing.assert_array_equal(h["W"], W)

    def test_weights_start_at_20_not_16(self):
        """If the parser read W at 16 it would see the flags word as floats —
        verified by a W whose first value differs from any flags bit pattern."""
        W = rng_W(2, 4)
        W[0, 0] = 12345.678
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "h.head")
            write_mhd2(p, ["p", "q"], W, np.zeros(2, np.float32), 1.0, kind=1, layer=0)
            h = head_io.load_head(p)
        self.assertAlmostEqual(float(h["W"][0, 0]), 12345.678, places=3)


class TestErrors(unittest.TestCase):
    def test_bad_magic(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "h.head")
            open(p, "wb").write(b"mhd9" + b"\x00" * 40)
            with self.assertRaises(ValueError):
                head_io.load_head(p)

    def test_truncated(self):
        W, b = rng_W(4, 16), np.zeros(4, np.float32)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "h.head")
            write_mhd3(p, ["a", "b", "c", "d"], W, b, 1.0, [(2, 7)])
            raw = open(p, "rb").read()[:30]  # cut inside weights
            p2 = os.path.join(d, "t.head")
            open(p2, "wb").write(raw)
            with self.assertRaises(ValueError):
                head_io.load_head(p2)


class TestProbs(unittest.TestCase):
    def test_temperature_sharpens(self):
        W = np.array([[2.0, 0.0], [0.0, 1.0]], np.float32)
        b = np.zeros(2, np.float32)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "h.head")
            write_mhd3(p, ["hot", "cold"], W, b, 0.25, [(2, 7)])
            h = head_io.load_head(p)
        X = np.array([[1.0, 1.0]], np.float32)
        P = head_io.probs(h, X)
        self.assertGreater(float(P[0, 0]), 0.85)  # temp<1 sharpens


if __name__ == "__main__":
    unittest.main()
