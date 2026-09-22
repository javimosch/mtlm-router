#!/usr/bin/env python3
# numpy reference oracle for the mtlm1 forward pass. Test-only (never in the train/infer path).
# Usage: ref_model.py <checkpoint.mtlm> <batch.txt>
# batch.txt: "B T\ninp0 inp1 ...\ntgt0 tgt1 ...\n"
# Prints JSON: {"loss": float, "logits0": float}
import sys, struct, json
import numpy as np

def load(path):
    with open(path, "rb") as f:
        data = f.read()
    magic, ver, dim, hidden, nl, nh, nkv, vocab, seq = struct.unpack_from("<9i", data, 0)
    shared = data[36]
    rope_theta = struct.unpack_from("<f", data, 37)[0]
    assert magic == 0x316c746d, hex(magic)
    kvdim = dim * nkv // nh
    head = dim // nh
    off = 256
    def rd(n):
        nonlocal off
        a = np.frombuffer(data, dtype=np.float32, count=n, offset=off).copy()
        off += n * 4
        return a
    rms_att = rd(nl * dim).reshape(nl, dim)
    rms_ffn = rd(nl * dim).reshape(nl, dim)
    rms_final = rd(dim)
    tok_emb = rd(vocab * dim).reshape(vocab, dim)
    wq = rd(nl * dim * dim).reshape(nl, dim, dim)
    wk = rd(nl * kvdim * dim).reshape(nl, kvdim, dim)
    wv = rd(nl * kvdim * dim).reshape(nl, kvdim, dim)
    wo = rd(nl * dim * dim).reshape(nl, dim, dim)
    w1 = rd(nl * hidden * dim).reshape(nl, hidden, dim)
    w2 = rd(nl * dim * hidden).reshape(nl, dim, hidden)
    w3 = rd(nl * hidden * dim).reshape(nl, hidden, dim)
    cfg = dict(dim=dim, hidden=hidden, nl=nl, nh=nh, nkv=nkv, vocab=vocab, seq=seq,
               head=head, kvdim=kvdim, rope_theta=rope_theta)
    return cfg, rms_att, rms_ffn, rms_final, tok_emb, wq, wk, wv, wo, w1, w2, w3

def rmsnorm(x, w, eps=1e-5):
    ms = np.mean(x * x, axis=-1, keepdims=True)
    return x * (1.0 / np.sqrt(ms + eps)) * w

def silu(x):
    return x / (1.0 + np.exp(-x))

def rope(q, T, head, theta):
    # q: [bt, ndim], position = row % T
    bt, ndim = q.shape
    out = q.copy()
    freqs = 1.0 / theta ** (np.arange(0, head, 2.0) / head)  # [head/2]
    for i in range(0, ndim, 2):
        hd = i % head
        freq = freqs[hd // 2]
        pos = np.arange(bt) % T
        ang = pos * freq
        c, s = np.cos(ang), np.sin(ang)
        a0 = q[:, i] * c - q[:, i+1] * s
        a1 = q[:, i] * s + q[:, i+1] * c
        out[:, i] = a0
        out[:, i+1] = a1
    return out

def forward(cfg, W, inp, tgt, B, T):
    dim, nl, nh, nkv, vocab = cfg["dim"], cfg["nl"], cfg["nh"], cfg["nkv"], cfg["vocab"]
    head, kvdim = cfg["head"], cfg["kvdim"]
    rms_att, rms_ffn, rms_final, tok_emb, wq, wk, wv, wo, w1, w2, w3 = W
    bt = B * T
    x = tok_emb[inp]  # [bt, dim]
    for l in range(nl):
        h = rmsnorm(x, rms_att[l])
        q = h @ wq[l].T
        k = h @ wk[l].T
        v = h @ wv[l].T
        q = rope(q, T, head, cfg["rope_theta"])
        k = rope(k, T, head, cfg["rope_theta"])
        # attention per head
        ao = np.zeros((bt, dim), dtype=x.dtype)
        for b in range(B):
            for hh in range(nh):
                kr = (hh // (nh // nkv)) * head
                for t in range(T):
                    qh = q[b*T+t, hh*head:(hh+1)*head]
                    scores = np.zeros(T, dtype=x.dtype)
                    for s in range(t+1):
                        kh = k[b*T+s, kr:kr+head]
                        scores[s] = np.dot(qh, kh) / np.sqrt(head)
                    scores = scores[:t+1]
                    scores = np.exp(scores - scores.max())
                    scores = scores / scores.sum()
                    vh = v[b*T: b*T+t+1, kr:kr+head]
                    ao[b*T+t, hh*head:(hh+1)*head] = scores @ vh
        x = x + ao @ wo[l].T
        h2 = rmsnorm(x, rms_ffn[l])
        g = silu(h2 @ w1[l].T) * (h2 @ w3[l].T)
        x = x + g @ w2[l].T
    hfin = rmsnorm(x, rms_final)
    logits = hfin @ tok_emb.T  # [bt, vocab]
    # cross-entropy loss
    probs = np.zeros_like(logits)
    loss = 0.0
    for r in range(bt):
        lr = logits[r]
        mx = lr.max()
        e = np.exp(lr - mx)
        p = e / e.sum()
        probs[r] = p
        loss += -np.log(max(p[tgt[r]], 1e-10))
    loss /= bt
    return loss, logits

def fd_check(ckpt, batch, grads_json, eps=1e-4):
    """float64 central finite differences at the sampled indices; compare with MFL analytic grads."""
    cfg, *W = load(ckpt)
    W = [np.asarray(w, dtype=np.float64) for w in W]
    with open(batch) as f:
        lines = f.read().split("\n")
    B, T = map(int, lines[0].split())
    inp = np.array(list(map(int, lines[1].split())), dtype=np.int64)
    tgt = np.array(list(map(int, lines[2].split())), dtype=np.int64)
    names = ["rms_att", "rms_ffn", "rms_final", "tok_emb", "wq", "wk", "wv", "wo", "w1", "w2", "w3"]
    samples = json.load(open(grads_json))
    worst = 0.0; per = {}
    for ti, name in enumerate(names):
        flat = W[ti].reshape(-1)
        tmax = 0.0
        for idx, ana in samples[name]:
            old = flat[idx]
            flat[idx] = old + eps; lp, _ = forward(cfg, W, inp, tgt, B, T)
            flat[idx] = old - eps; lm, _ = forward(cfg, W, inp, tgt, B, T)
            flat[idx] = old
            num = (lp - lm) / (2 * eps)
            den = max(abs(ana), abs(num), 1e-6)
            re = abs(ana - num) / den
            tmax = max(tmax, re)
        per[name] = tmax; worst = max(worst, tmax)
    print(json.dumps({"max_relerr": worst, "per_tensor": per}))

def main():
    if sys.argv[1] == "--fd":
        fd_check(sys.argv[2], sys.argv[3], sys.argv[4]); return
    ckpt, batch = sys.argv[1], sys.argv[2]
    cfg, *W = load(ckpt)
    with open(batch) as f:
        lines = f.read().split("\n")
    B, T = map(int, lines[0].split())
    inp = list(map(int, lines[1].split()))
    tgt = list(map(int, lines[2].split()))
    inp = np.array(inp, dtype=np.int64)
    tgt = np.array(tgt, dtype=np.int64)
    loss, logits = forward(cfg, W, inp, tgt, B, T)
    print(json.dumps({"loss": float(loss), "logits0": float(logits[0, 0]),
                      "logits": [float(logits[0, i]) for i in range(min(8, cfg["vocab"]))]}))

if __name__ == "__main__":
    main()
