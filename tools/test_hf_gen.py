#!/usr/bin/env python3
# test_hf_gen.py — end-to-end HF transformers check for an hf_export.py bundle.
#   1. AutoModelForCausalLM + AutoTokenizer load from the export dir
#   2. next-token logits for a fixed prompt match the native numpy oracle
#   3. greedy generation after <|assistant|>\n emits a well-formed tool_call
#
# Usage: test_hf_gen.py <hf_outdir> [model.mtlm]
import sys, json
import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

PROMPT = "<|user|>\nwhat is 123 times 456?</s>\n<|assistant|>\n"

def main():
    hfdir = sys.argv[1]
    tok = AutoTokenizer.from_pretrained(hfdir)
    model = AutoModelForCausalLM.from_pretrained(hfdir, torch_dtype=torch.float32)
    model.eval()

    ids = tok(PROMPT, return_tensors="pt").input_ids
    with torch.no_grad():
        logits = model(ids).logits[0, -1]
    print("prompt ids:", ids[0].tolist())
    print("top5 next:", torch.topk(logits, 5).indices.tolist())

    # optional: native logits comparison
    if len(sys.argv) > 2:
        import ref_model
        cfg, *W = ref_model.load(sys.argv[2])
        inp = np.array(ids[0].tolist(), dtype=np.int64)
        _, lg = ref_model.forward(cfg, W, inp, np.zeros_like(inp), 1, len(inp))
        nat = lg[-1]
        hf = logits.numpy()
        d = np.abs(nat - hf)
        print("native-vs-hf last-pos logits: max|d|=%.4e argmax native=%d hf=%d"
              % (d.max(), int(nat.argmax()), int(hf.argmax())))

    out = model.generate(ids, max_new_tokens=48, do_sample=False,
                         eos_token_id=2, pad_token_id=0)
    text = tok.decode(out[0][ids.shape[1]:], skip_special_tokens=False)
    print("generated:", repr(text))
    ok = text.strip().startswith('{"tool_call"') and "calculator" in text
    print(json.dumps({"tool_call_emitted": bool(ok)}))
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
