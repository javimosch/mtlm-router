#!/usr/bin/env python3
"""Numpy reference oracle for the mtlm1 → ak42 exporter.
Reads an mtlm1 checkpoint, performs the SAME Q8_0 quantization as the MFL
exporter, and writes the ak42 file. test-export asserts byte-identity.

Rounding rule (MUST match the MFL exporter): round-half-away-from-zero.
  MFL:   q = int(qf + 0.5) if qf >= 0 else int(qf - 0.5)   [int() truncates toward 0]
  Numpy: q = sign(qf) * floor(|qf| + 0.5)                  [mathematically identical]

All arithmetic is done in float64 to match MFL's float (which is float64).
The f32 scale stored on disk is the float64 scale cast to float32 (round-to-nearest-even),
but the quantization itself uses the float64 scale (before the cast), exactly as MFL does.
"""
import struct, sys
import numpy as np

def read_mtlm1(path):
    with open(path, "rb") as f:
        data = f.read()
    magic, ver = struct.unpack_from("<ii", data, 0)
    assert magic == 0x316C746D, f"bad magic {magic:#x}"
    assert ver == 1, f"bad version {ver}"
    dim, hidden, layers, heads, kvh, vocab, seq = struct.unpack_from("<7i", data, 8)
    shared = data[36]
    assert shared == 1
    kv_dim = (dim * kvh) // heads
    off = 256
    def rd(n):
        nonlocal off
        arr = np.frombuffer(data, dtype=np.float32, count=n, offset=off).astype(np.float64)
        off += n * 4
        return arr
    rms_att = rd(layers * dim)
    rms_ffn = rd(layers * dim)
    rms_fin = rd(dim)
    tok_emb = rd(vocab * dim)
    wq = rd(layers * dim * dim)
    wk = rd(layers * kv_dim * dim)
    wv = rd(layers * kv_dim * dim)
    wo = rd(layers * dim * dim)
    w1 = rd(layers * hidden * dim)
    w2 = rd(layers * dim * hidden)
    w3 = rd(layers * hidden * dim)
    return dict(dim=dim, hidden=hidden, layers=layers, heads=heads, kvh=kvh,
                vocab=vocab, seq=seq, kv_dim=kv_dim,
                rms_att=rms_att, rms_ffn=rms_ffn, rms_fin=rms_fin,
                tok_emb=tok_emb, wq=wq, wk=wk, wv=wv, wo=wo, w1=w1, w2=w2, w3=w3)

def round_half_away(x):
    """Round half away from zero, matching MFL's int(qf +/- 0.5)."""
    return np.sign(x) * np.floor(np.abs(x) + 0.5)

def quant_q8_0(w, gs=64):
    """Q8_0 quantization: per group of gs, scale=max|w|/127, q=round_half_away(w/scale)."""
    n = len(w)
    assert n % gs == 0, f"tensor size {n} not multiple of {gs}"
    ng = n // gs
    w_groups = w.reshape(ng, gs)
    maxabs = np.max(np.abs(w_groups), axis=1)  # float64
    scale = maxabs / 127.0  # float64
    # quantize using float64 scale (before f32 cast), matching MFL
    qf = w_groups / scale[:, None]  # float64
    q = round_half_away(qf)
    q = np.clip(q, -127, 127).astype(np.int8)
    return q.ravel().tobytes(), np.float32(scale).tobytes()

def write_ak42(m, path, gs=64):
    buf = bytearray(256)
    struct.pack_into("<ii", buf, 0, 0x616B3432, 2)
    struct.pack_into("<7i", buf, 8, m["dim"], m["hidden"], m["layers"],
                     m["heads"], m["kvh"], m["vocab"], m["seq"])
    buf[36] = 1  # shared_classifier
    struct.pack_into("<i", buf, 37, gs)
    # fp32 norms (copied directly)
    for arr in (m["rms_att"], m["rms_ffn"], m["rms_fin"]):
        buf += np.float32(arr).tobytes()
    # Q8_0 tensors in order: tok_emb, wq, wk, wv, wo, w1, w2, w3
    qb, sb = quant_q8_0(m["tok_emb"], gs)
    buf += qb + sb
    # layer tensors: one Q8_0 block PER LAYER (llama2.c export.py v2 quantizes layer by layer)
    L = m["layers"]
    for key in ("wq", "wk", "wv", "wo", "w1", "w2", "w3"):
        per = m[key].size // L
        for l in range(L):
            qb, sb = quant_q8_0(m[key][l*per:(l+1)*per], gs)
            buf += qb + sb
    with open(path, "wb") as f:
        f.write(buf)

def main():
    mtlm_path = sys.argv[1] if len(sys.argv) > 1 else "models/rnd.mtlm"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "models/rnd_ref.bin"
    m = read_mtlm1(mtlm_path)
    write_ak42(m, out_path)
    params = (m["layers"]*m["dim"]*2 + m["dim"] + m["vocab"]*m["dim"] +
              m["layers"]*(m["dim"]*m["dim"] + m["kv_dim"]*m["dim"] + m["kv_dim"]*m["dim"] +
                            m["dim"]*m["dim"] + m["hidden"]*m["dim"] + m["dim"]*m["hidden"] +
                            m["hidden"]*m["dim"]))
    import os
    sz = os.path.getsize(out_path)
    print(f'{{"ref":"{out_path}","params":{params},"bytes":{sz}}}')

if __name__ == "__main__":
    main()
