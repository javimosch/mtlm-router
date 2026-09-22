#!/usr/bin/env python3
# verify_hf.py — verify an hf_export.py bundle against the source .mtlm checkpoint.
#   1. safetensors parses, tensor names/shapes sane
#   2. weights are bit-exact after un-permuting q/k back to interleaved layout
#   3. HF-semantics forward (rotate-half RoPE on permuted weights) reproduces
#      the native interleaved forward logits on a fixed token sequence
#
# Usage: verify_hf.py <model.mtlm> <hf_outdir> [tok_ids_csv]
import sys, struct, json
import numpy as np
import ref_model

def load_safetensors(path):
    data = open(path, "rb").read()
    hlen = struct.unpack_from("<Q", data, 0)[0]
    hdr = json.loads(data[8:8 + hlen])
    base = 8 + hlen
    out = {}
    for name, meta in hdr.items():
        if name == "__metadata__": continue
        assert meta["dtype"] == "F32", meta
        a, b = meta["data_offsets"]
        out[name] = np.frombuffer(data, dtype="<f4", count=(b - a) // 4,
                                  offset=base + a).reshape(meta["shape"]).copy()
    return out

# inverse of hf_export.perm_qk: rotate-half rows → interleaved rows
def unperm_qk(w, nheads, head_dim):
    shp = w.shape
    half = head_dim // 2
    w2 = w.reshape(shp[:-2] + (nheads, head_dim, shp[-1]))
    out = np.zeros(shp, dtype=w.dtype)
    out2 = out.reshape(shp[:-2] + (nheads, head_dim // 2, 2, shp[-1]))
    out2[..., 0, :] = w2[..., :half, :]
    out2[..., 1, :] = w2[..., half:, :]
    return out

def rope_hf(x, T, head, theta):
    """rotate-half RoPE (HF Llama convention) on [bt, ndim] with per-head blocks."""
    bt, ndim = x.shape
    half = head // 2
    freqs = 1.0 / theta ** (np.arange(0, head, 2.0) / head)
    pos = np.arange(bt) % T
    ang = pos[:, None] * freqs[None, :]
    c, s = np.cos(ang)[:, None, :], np.sin(ang)[:, None, :]
    xh = x.reshape(bt, ndim // head, head)
    out = np.empty_like(xh)
    out[..., :half] = xh[..., :half] * c - xh[..., half:] * s
    out[..., half:] = xh[..., :half] * s + xh[..., half:] * c
    return out.reshape(bt, ndim)

def forward_hf(cfg, tensors, inp, tgt, B, T):
    """ref_model.forward re-implemented over HF-named tensors with rotate-half rope."""
    dim, nl, nh, nkv = cfg["dim"], cfg["nl"], cfg["nh"], cfg["nkv"]
    head, kvdim = cfg["head"], cfg["kvdim"]
    emb = tensors["model.embed_tokens.weight"]
    bt = B * T
    x = emb[inp]
    for l in range(nl):
        p = "model.layers.%d." % l
        h = ref_model.rmsnorm(x, tensors[p + "input_layernorm.weight"])
        q = rope_hf(h @ tensors[p + "self_attn.q_proj.weight"].T, T, head, cfg["rope_theta"])
        k = rope_hf(h @ tensors[p + "self_attn.k_proj.weight"].T, T, head, cfg["rope_theta"])
        v = h @ tensors[p + "self_attn.v_proj.weight"].T
        ao = np.zeros((bt, dim), dtype=x.dtype)
        for b in range(B):
            for hh in range(nh):
                kr = (hh // (nh // nkv)) * head
                for t in range(T):
                    qh = q[b * T + t, hh * head:(hh + 1) * head]
                    sc = np.array([np.dot(qh, k[b * T + s, kr:kr + head])
                                   for s in range(t + 1)]) / np.sqrt(head)
                    sc = np.exp(sc - sc.max()); sc /= sc.sum()
                    ao[b * T + t, hh * head:(hh + 1) * head] = sc @ v[b * T:b * T + t + 1, kr:kr + head]
        x = x + ao @ tensors[p + "self_attn.o_proj.weight"].T
        h2 = ref_model.rmsnorm(x, tensors[p + "post_attention_layernorm.weight"])
        g = ref_model.silu(h2 @ tensors[p + "mlp.gate_proj.weight"].T) * (h2 @ tensors[p + "mlp.up_proj.weight"].T)
        x = x + g @ tensors[p + "mlp.down_proj.weight"].T
    logits = ref_model.rmsnorm(x, tensors["model.norm.weight"]) @ tensors["lm_head.weight"].T
    return logits

def main():
    ckpt, hfdir = sys.argv[1], sys.argv[2]
    ids = [1, 260, 300, 500, 700, 900, 1100, 1300]
    if len(sys.argv) > 3:
        ids = [int(t) for t in sys.argv[3].split(",")]
    cfg, *W = ref_model.load(ckpt)
    nl, nh, nkv, head = cfg["nl"], cfg["nh"], cfg["nkv"], cfg["head"]
    T = load_safetensors(hfdir + "/model.safetensors")

    # --- check 1: shape/name sanity ---
    dim, hidden, vocab = cfg["dim"], cfg["hidden"], cfg["vocab"]
    assert T["model.embed_tokens.weight"].shape == (vocab, dim)
    assert T["lm_head.weight"].shape == (vocab, dim)
    for l in range(nl):
        p = "model.layers.%d." % l
        assert T[p + "self_attn.q_proj.weight"].shape == (dim, dim)
        assert T[p + "self_attn.k_proj.weight"].shape == (cfg["kvdim"], dim)
        assert T[p + "self_attn.v_proj.weight"].shape == (cfg["kvdim"], dim)
        assert T[p + "self_attn.o_proj.weight"].shape == (dim, dim)
        assert T[p + "mlp.gate_proj.weight"].shape == (hidden, dim)
        assert T[p + "mlp.down_proj.weight"].shape == (dim, hidden)
        assert T[p + "mlp.up_proj.weight"].shape == (hidden, dim)
    assert len(T) == 3 + nl * 9, len(T)  # embed + lm_head + norm + 9/layer
    print("check1 names+shapes: ok (%d tensors)" % len(T))

    # --- check 2: bit-exact weights after un-permutation ---
    rms_att, rms_ffn, rms_fin, tok_emb, wq, wk, wv, wo, w1, w2, w3 = W
    bad = []
    def eq(name, a, b):
        if not np.array_equal(a, np.asarray(b, dtype=np.float32)): bad.append(name)
    eq("tok_emb", T["model.embed_tokens.weight"], tok_emb)
    eq("lm_head", T["lm_head.weight"], tok_emb)
    eq("rms_fin", T["model.norm.weight"], rms_fin)
    for l in range(nl):
        p = "model.layers.%d." % l
        eq(p + "input_layernorm", T[p + "input_layernorm.weight"], rms_att[l])
        eq(p + "post_attn_ln", T[p + "post_attention_layernorm.weight"], rms_ffn[l])
        eq(p + "q_proj", unperm_qk(T[p + "self_attn.q_proj.weight"], nh, head), wq[l])
        eq(p + "k_proj", unperm_qk(T[p + "self_attn.k_proj.weight"], nkv, head), wk[l])
        eq(p + "v_proj", T[p + "self_attn.v_proj.weight"], wv[l])
        eq(p + "o_proj", T[p + "self_attn.o_proj.weight"], wo[l])
        eq(p + "gate", T[p + "mlp.gate_proj.weight"], w1[l])
        eq(p + "down", T[p + "mlp.down_proj.weight"], w2[l])
        eq(p + "up", T[p + "mlp.up_proj.weight"], w3[l])
    if bad:
        print("check2 MISMATCH: %s" % ", ".join(bad)); sys.exit(1)
    print("check2 weights bit-exact: ok")

    # --- check 3: HF forward (permuted + rotate-half) == native forward ---
    B, Tn = 1, len(ids)
    inp = np.array(ids, dtype=np.int64)
    tgt = np.zeros_like(inp)
    _, logits_native = ref_model.forward(cfg, W, inp, tgt, B, Tn)
    logits_hf = forward_hf(cfg, T, inp, tgt, B, Tn)
    d = np.abs(logits_native - logits_hf)
    am_nat = logits_native.argmax(-1); am_hf = logits_hf.argmax(-1)
    print("check3 forward parity: max|dlogit|=%.3e  argmax_match=%s  native_top=%d hf_top=%d"
          % (d.max(), bool((am_nat == am_hf).all()), am_nat[-1], am_hf[-1]))
    if d.max() > 1e-4 or not (am_nat == am_hf).all():
        print("check3 FAIL"); sys.exit(1)
    print("all checks passed")

if __name__ == "__main__":
    main()
