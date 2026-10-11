"""Canonical .head parser — the ONLY place mhd2/mhd3 bytes are decoded.

Format (little-endian):
  magic 4B  "mhd2" or "mhd3"
  int32     n_classes
  int32     featdim
  float32   temperature
  mhd3: u8 ntaps, then ntaps x (u8 kind, u8 layer_plus1)
        kind: 1=max 2=mean (see tools/emit_civic.py writer) ;
        layer_plus1 = anvil layer + 1
  mhd2: u32 flags at byte 16 — flags = pool_kind | ((layer+1) << 4)
        (single tap; 0 = last-token). Weights start at byte 20.
        (spec: machin-anvil engine.src read_head)
  float32[n_classes * featdim]  W  — ROW-MAJOR (n_classes, featdim); logits = X @ W.T + b
  float32[n_classes]            b
  per class: u8 len + utf-8 name

Gotchas this file exists to prevent (paid for in bench/oos_eval_mairie):
  - Taps MUST be read from the header, never assumed: mairie uses
    3x max at layers {2,4,3}; civic uses 3x mean at {-4,-3,-2}. Wrong taps
    yield confident garbage (~0.9 prob on a single class).
  - W is (n_classes, featdim) — reshape(nr, fd), NOT (fd, nr).
  - hf_layer index: anvil layer L -> hidden_states index (L - n_layers),
    i.e. stored layer_plus1-1 converted to negative-index form.
"""
import struct
import numpy as np

_KIND = {1: "max", 2: "mean"}


def load_head(path, n_layers=6):
    """Return dict(W, b, labels, temp, taps, n_classes, featdim, magic).
    taps: list of (hf_index, kind) where hf_index is the negative index
    into hidden_states usable with head_probe.features().
    n_layers: model depth (anvil layers) for converting stored layer+1
    -> hf negative index. Default 6 for m7router3s384.
    """
    with open(path, "rb") as f:
        d = f.read()
    if len(d) < 17:
        raise ValueError(f"{path}: too short for a head file")
    magic = d[:4].decode()
    if magic not in ("mhd2", "mhd3"):
        raise ValueError(f"{path}: bad magic {magic!r}")
    nr, fd = struct.unpack("<ii", d[4:12])
    temp = struct.unpack("<f", d[12:16])[0]
    if magic == "mhd3":
        ntaps = d[16]
        taps_meta = [struct.unpack("<BB", d[17 + 2 * i:19 + 2 * i]) for i in range(ntaps)]
        off = 17 + 2 * ntaps
    else:  # mhd2: u32 flags = pool_kind | ((layer+1)<<4), then weights
        flags = struct.unpack("<I", d[16:20])[0]
        k, lay = flags & 15, (flags >> 4) - 1
        taps_meta = [(k, lay + 1)] if k > 0 and lay >= 0 else []
        off = 20
    need = off + 4 * nr * fd + 4 * nr
    if len(d) < need:
        raise ValueError(f"{path}: truncated weights (need {need}, have {len(d)})")
    W = np.frombuffer(d[off:off + 4 * nr * fd], dtype=np.float32).reshape(nr, fd)
    off += 4 * nr * fd
    b = np.frombuffer(d[off:off + 4 * nr], dtype=np.float32)
    off += 4 * nr
    labels = []
    for _ in range(nr):
        ln = d[off]; off += 1
        labels.append(d[off:off + ln].decode()); off += ln
    taps = []
    for kind, lp1 in taps_meta:
        anvil_layer = lp1 - 1
        taps.append((anvil_layer - n_layers if anvil_layer <= n_layers else anvil_layer,
                     _KIND.get(kind, f"k{kind}")))
    return {"W": W, "b": b, "labels": labels, "temp": temp,
            "taps": taps, "n_classes": nr, "featdim": fd, "magic": magic}


def probs(head, X):
    """softmax((X @ W.T + b) / temp) -> (n, n_classes)"""
    Z = X @ head["W"].T + head["b"]
    Z = Z / head["temp"]
    P = np.exp(Z - Z.max(axis=1, keepdims=True))
    return P / P.sum(axis=1, keepdims=True)
