#!/usr/bin/env python3
# hf_export.py — mtlm1 fp32 checkpoint + llama2.c-style tokenizer.bin → HF bundle
#   model.safetensors  (LlamaForCausalLM naming, q/k rows permuted interleaved→rotate-half)
#   config.json, generation_config.json
#   tokenizer.json     (byte-fallback BPE, Metaspace "▁" pre-tokenizer, merges reconstructed)
#   tokenizer_config.json, special_tokens_map.json
#
# RoPE: mtlm rotates adjacent pairs (x[2j], x[2j+1]) per head (llama2.c style).
# HF Llama uses rotate-half: pairs (x[j], x[j+hd/2]). To preserve behavior we permute the
# OUTPUT ROWS of wq/wk so that HF index j ↔ mtlm index 2j and HF index j+hd/2 ↔ mtlm index 2j+1.
#
# Tokenizer: mtlm pieces store literal " "; HF vocab/merges use "▁" via a Metaspace
# pre-tokenizer (split on space, prepend_scheme="never" — anvil's chat path encodes each
# rendered segment with no prefix). Merges are reconstructed by, for each piece in id order,
# simulating greedy merge-by-rank over merges emitted so far and emitting the final 2-token
# split — which reproduces the training-time merge tree exactly.
#
# Usage: hf_export.py --model m.mtlm --tok tok.bin --out outdir/
import sys, struct, json, os
import numpy as np

def load_ckpt(path):
    data = open(path, "rb").read()
    magic, ver, dim, hidden, nl, nh, nkv, vocab, seq = struct.unpack_from("<9i", data, 0)
    shared = data[36]
    rope_theta = struct.unpack_from("<f", data, 37)[0]
    if magic != 0x316c746d: sys.exit("bad mtlm1 magic " + hex(magic))
    if ver != 1: sys.exit("bad mtlm1 version " + str(ver))
    kvdim = dim * nkv // nh
    off = 256
    def rd(n):
        nonlocal off
        a = np.frombuffer(data, dtype=np.float32, count=n, offset=off).copy()
        off += n * 4
        return a
    W = {
        "rms_att": rd(nl * dim).reshape(nl, dim),
        "rms_ffn": rd(nl * dim).reshape(nl, dim),
        "rms_fin": rd(dim),
        "tok_emb": rd(vocab * dim).reshape(vocab, dim),
        "wq": rd(nl * dim * dim).reshape(nl, dim, dim),
        "wk": rd(nl * kvdim * dim).reshape(nl, kvdim, dim),
        "wv": rd(nl * kvdim * dim).reshape(nl, kvdim, dim),
        "wo": rd(nl * dim * dim).reshape(nl, dim, dim),
        "w1": rd(nl * hidden * dim).reshape(nl, hidden, dim),
        "w2": rd(nl * dim * hidden).reshape(nl, dim, hidden),
        "w3": rd(nl * hidden * dim).reshape(nl, hidden, dim),
    }
    if off != len(data):
        print("warning: checkpoint has %d trailing bytes" % (len(data) - off), file=sys.stderr)
    cfg = dict(dim=dim, hidden=hidden, nl=nl, nh=nh, nkv=nkv, vocab=vocab, seq=seq,
               kvdim=kvdim, head=dim // nh, rope_theta=rope_theta, shared=shared)
    return cfg, W

def load_tokenizer(path):
    data = open(path, "rb").read()
    max_len = struct.unpack_from("<i", data, 0)[0]
    pieces, scores = [], []
    o = 4
    while o + 8 <= len(data):
        sc = struct.unpack_from("<f", data, o)[0]
        ln = struct.unpack_from("<i", data, o + 4)[0]
        o += 8
        pieces.append(data[o:o + ln].decode("utf-8"))
        scores.append(sc)
        o += ln
    return pieces, scores, max_len

# interleaved → rotate-half row permutation, applied per head block
def perm_qk(w, nheads, head_dim):
    shp = w.shape
    w2 = w.reshape(shp[:-2] + (nheads, head_dim // 2, 2, shp[-1]))
    return np.concatenate([w2[..., 0, :], w2[..., 1, :]], axis=-2).reshape(shp)

def save_safetensors(tensors, path):
    header, blobs, off = {}, [], 0
    for name, arr in tensors.items():
        arr = np.ascontiguousarray(arr, dtype="<f4")
        data = arr.tobytes()
        header[name] = {"dtype": "F32", "shape": list(arr.shape), "data_offsets": [off, off + len(data)]}
        blobs.append(data)
        off += len(data)
    hj = json.dumps(header).encode()
    with open(path, "wb") as f:
        f.write(struct.pack("<Q", len(hj)))
        f.write(hj)
        for b in blobs: f.write(b)
    return off

# ---- tokenizer.json ----

import re
BYTE_PIECE_RE = re.compile(r"<0x([0-9a-fA-F]{2})>")

def hf_piece(p):
    # space → ▁ (Metaspace) and lowercase <0xnn> → uppercase <0xNN> (HF byte_fallback
    # generates uppercase names; our tokenizer.bin stores them lowercase)
    return BYTE_PIECE_RE.sub(lambda m: "<0x" + m.group(1).upper() + ">", p.replace(" ", "▁"))

def build_merges(pieces):
    """Reconstruct HF merge list. For each multi-char piece in id order, simulate greedy
    merge-by-rank over merges emitted so far; the final 2-token split is the true last merge."""
    vocab = {}
    for i, p in enumerate(pieces):
        hp = hf_piece(p)
        if hp not in vocab: vocab[hp] = i
    # initial symbols: per UTF-8 char its piece id, else <0xNN> byte tokens
    def init_syms(s):
        out = []
        for ch in s:
            hp = hf_piece(ch)
            if hp in vocab: out.append(vocab[hp])
            else:
                for b in ch.encode("utf-8"): out.append(vocab["<0x%02X>" % b])
        return out
    emitted = set()   # piece ids whose merge has been emitted (rank < current id)
    merges = []
    warn = []
    for pid in range(len(pieces)):
        s = hf_piece(pieces[pid])
        if len(s) < 2 or pid < 3: continue   # specials + single chars
        if len(s) == 6 and s[:3] == "<0x" and s[-1] == ">": continue  # byte pieces are atomic
        toks = init_syms(s)
        while True:
            best, bi = None, -1
            for i in range(len(toks) - 1):
                m = hf_piece(pieces[toks[i]] + pieces[toks[i + 1]])
                mid = vocab.get(m)
                if mid is not None and mid in emitted and mid < pid:
                    if best is None or mid < best: best, bi = mid, i
            if best is None: break
            toks = toks[:bi] + [best] + toks[bi + 2:]
        if len(toks) == 2:
            emitted.add(pid)
            merges.append(hf_piece(pieces[toks[0]]) + " " + hf_piece(pieces[toks[1]]))
        elif len(toks) == 1:
            warn.append((pid, s, "already-reachable"))
        else:
            warn.append((pid, s, "unreducible:%d" % len(toks)))
    return vocab, merges, warn

def write_tokenizer_json(pieces, path):
    vocab, merges, warn = build_merges(pieces)
    for pid, s, why in warn:
        print("warning: piece %d %r skipped (%s)" % (pid, s, why), file=sys.stderr)
    tj = {
        "version": "1.0",
        "truncation": None, "padding": None,
        "added_tokens": [
            {"id": 0, "content": "<unk>", "single_word": False, "lstrip": False, "rstrip": False, "normalized": False, "special": True},
            {"id": 1, "content": "<s>", "single_word": False, "lstrip": False, "rstrip": False, "normalized": False, "special": True},
            {"id": 2, "content": "</s>", "single_word": False, "lstrip": False, "rstrip": False, "normalized": False, "special": True},
        ],
        "normalizer": None,
        "pre_tokenizer": {
            "type": "Metaspace", "replacement": "▁",
            "add_prefix_space": False, "prepend_scheme": "never", "split": True,
        },
        "post_processor": {
            "type": "TemplateProcessing",
            "single": [{"SpecialToken": {"id": "<s>", "type_id": 0}}, {"Sequence": {"id": "A", "type_id": 0}}],
            "pair": [{"SpecialToken": {"id": "<s>", "type_id": 0}},
                     {"Sequence": {"id": "A", "type_id": 0}},
                     {"SpecialToken": {"id": "<s>", "type_id": 1}},
                     {"Sequence": {"id": "B", "type_id": 1}}],
            "special_tokens": {"<s>": {"id": "<s>", "ids": [1], "tokens": ["<s>"]}},
        },
        "decoder": {
            "type": "Sequence",
            "decoders": [
                {"type": "Replace", "pattern": {"String": "▁"}, "content": " "},
                {"type": "ByteFallback"},
                {"type": "Fuse"},
                {"type": "Strip", "content": " ", "start": 1, "stop": 0},
            ],
        },
        "model": {
            "type": "BPE", "dropout": None, "unk_token": "<unk>",
            "continuing_subword_prefix": None, "end_of_word_suffix": None,
            "fuse_unk": False, "byte_fallback": True, "ignore_merges": False,
            "vocab": vocab, "merges": merges,
        },
    }
    with open(path, "w") as f: json.dump(tj, f, ensure_ascii=False)
    return len(merges), len(warn)

CHAT_TEMPLATE = (
    "{{ bos_token }}"
    "{% for m in messages %}"
    "{% if m['role'] == 'tool' %}<|user|>\nTool result: {{ m['content'] }}"
    "{% else %}<|{{ m['role'] }}|>\n{{ m['content'] }}{% endif %}"
    "{{ eos_token }}\n"
    "{% endfor %}"
    "{% if add_generation_prompt %}<|assistant|>\n{% endif %}"
)

def write_json(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")

def main():
    args = sys.argv[1:]
    def flag(n, d=None):
        if n in args: return args[args.index(n) + 1]
        return d
    model, tok, out = flag("--model"), flag("--tok"), flag("--out", ".")
    if not model or not tok: sys.exit("usage: hf_export.py --model m.mtlm --tok tok.bin --out dir")
    os.makedirs(out, exist_ok=True)
    cfg, W = load_ckpt(model)
    dim, nl, nh, nkv, hidden, vocab_sz, seq = cfg["dim"], cfg["nl"], cfg["nh"], cfg["nkv"], cfg["hidden"], cfg["vocab"], cfg["seq"]
    head = cfg["head"]

    tensors = {}
    tensors["model.embed_tokens.weight"] = W["tok_emb"]
    tensors["lm_head.weight"] = W["tok_emb"]  # tied; materialized for loaders that don't tie
    for i in range(nl):
        p = "model.layers.%d." % i
        tensors[p + "input_layernorm.weight"] = W["rms_att"][i]
        tensors[p + "self_attn.q_proj.weight"] = perm_qk(W["wq"][i], nh, head)
        tensors[p + "self_attn.k_proj.weight"] = perm_qk(W["wk"][i], nkv, head)
        tensors[p + "self_attn.v_proj.weight"] = W["wv"][i]
        tensors[p + "self_attn.o_proj.weight"] = W["wo"][i]
        tensors[p + "post_attention_layernorm.weight"] = W["rms_ffn"][i]
        tensors[p + "mlp.gate_proj.weight"] = W["w1"][i]
        tensors[p + "mlp.down_proj.weight"] = W["w2"][i]
        tensors[p + "mlp.up_proj.weight"] = W["w3"][i]
    tensors["model.norm.weight"] = W["rms_fin"]
    nbytes = save_safetensors(tensors, os.path.join(out, "model.safetensors"))

    write_json(os.path.join(out, "config.json"), {
        "architectures": ["LlamaForCausalLM"],
        "model_type": "llama",
        "hidden_size": dim, "intermediate_size": hidden,
        "num_hidden_layers": nl, "num_attention_heads": nh,
        "num_key_value_heads": nkv, "head_dim": head,
        "vocab_size": vocab_sz, "max_position_embeddings": seq,
        "rms_norm_eps": 1e-5, "rope_theta": float(cfg["rope_theta"]),
        "rope_scaling": None, "attention_bias": False, "mlp_bias": False,
        "tie_word_embeddings": True, "pretraining_tp": 1, "use_cache": True,
        "torch_dtype": "float32", "bos_token_id": 1, "eos_token_id": 2,
        "pad_token_id": 0,
    })
    write_json(os.path.join(out, "generation_config.json"), {
        "bos_token_id": 1, "eos_token_id": 2,
        "temperature": 0.8, "top_p": 0.9, "do_sample": True,
    })

    pieces, scores, max_len = load_tokenizer(tok)
    if len(pieces) != vocab_sz:
        print("warning: tokenizer vocab %d != model vocab %d" % (len(pieces), vocab_sz), file=sys.stderr)
    n_merges, n_warn = write_tokenizer_json(pieces, os.path.join(out, "tokenizer.json"))

    write_json(os.path.join(out, "tokenizer_config.json"), {
        "tokenizer_class": "PreTrainedTokenizerFast",
        "bos_token": "<s>", "eos_token": "</s>", "unk_token": "<unk>",
        "model_max_length": seq, "chat_template": CHAT_TEMPLATE,
    })
    write_json(os.path.join(out, "special_tokens_map.json"), {
        "bos_token": "<s>", "eos_token": "</s>", "unk_token": "<unk>",
    })
    print(json.dumps({"out": out, "tensors": len(tensors), "st_bytes": nbytes,
                      "merges": n_merges, "tok_warnings": n_warn,
                      "params": int(sum(a.size for a in tensors.values()))}))

if __name__ == "__main__":
    main()
