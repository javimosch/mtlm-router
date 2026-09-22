#!/usr/bin/env python3
# verify_tok.py — parity between HF tokenizer.json and `mtlm encode`.
# HF encode(text) [post_processor adds BOS]  ==  mtlm encode --no-prefix (bos=1, prefix=0)
# which is exactly the anvil chat-path encoding (bpe_encode_raw segments + BOS once).
#
# Usage: verify_tok.py <tokenizer.bin> <hf_outdir>
import sys, json, subprocess
from tokenizers import Tokenizer

TESTS = [
    "hello world",
    "Hello, world!",
    "the quick brown fox jumps over the lazy dog",
    "  leading  double   spaces",
    "trailing space ",
    "line one\nline two\n\nline four",
    "tab\tseparated\tvalues",
    "What's the weather in Lyon?",
    "{\"tool_call\": {\"name\": \"get_weather\", \"arguments\": {\"city\": \"Paris\"}}}",
    "Tool result: {\"temp_c\": 18.5, \"wind_kph\": 12}",
    "<|user|>\nwhat is 123 times 456?",
    "<|assistant|>\n{\"tool_call\": {\"name\": \"calculator\"}}",
    "numbers 0 1 42 -7 3.14159 999999999 2024-01-15",
    "UTF-8: café résumé naïve über",
    "CJK: 你好世界 日本語 テスト",
    "emoji: \U0001f600 \U0001f680",
    "symbols: @#$%^&*()_+-=[]{}|;':\",./<>?`~",
    "mixed a  b\tc\nd  é中x\U0001f600z",
    "supercalifragilisticexpialidocious",
]

def mtlm_encode(tok, text):
    r = subprocess.run(["./mtlm", "encode", "--tok", tok, "--no-prefix", text],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("mtlm encode failed: " + r.stderr)
    return json.loads(r.stdout)["ids"]

def main():
    tok_bin, hfdir = sys.argv[1], sys.argv[2]
    hf = Tokenizer.from_file(hfdir + "/tokenizer.json")
    nfail = 0
    for t in TESTS:
        native = mtlm_encode(tok_bin, t)
        got = hf.encode(t).ids
        if got != native:
            nfail += 1
            print("MISMATCH %r\n  native: %s\n  hf:     %s" % (t, native, got))
    # decode round-trip spot check
    dec = hf.decode(mtlm_encode(tok_bin, TESTS[0])[1:])
    print("decode spot check: %r" % dec)
    print(json.dumps({"tests": len(TESTS), "mismatches": nfail}))
    sys.exit(1 if nfail else 0)

if __name__ == "__main__":
    main()
