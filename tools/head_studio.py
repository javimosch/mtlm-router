#!/usr/bin/env python3
"""head_studio.py — customer self-serve route head, one command.

Takes a route config (routes = name -> [example phrases], optional slots),
validates it, synthesizes a labeled spec, trains a decision head on the frozen
trunk, evaluates on a held-out split, and writes a deployable .head artifact
plus a manifest. No fine-tuning — the trunk is never touched.

  python3 tools/head_studio.py --config tools/demo_helpdesk.json \
      --hf /path/to/hf-bundle --name helpdesk --outdir out/

Then serve:  ANVIL_HEAD=out/helpdesk.head ./anvil-serve model.bin 8097

Config format (see tools/demo_helpdesk.json):
  {"system": "...",                      # optional system prompt
   "routes": {"route_name": ["phrase", "phrase with {slot}", ...], ...},
   "slots":  {"slot": ["value", ...]},   # optional {slot} fillers
   "_num_range": [lo, hi]}               # optional {num} range
"""
import argparse, json, os, re, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROUTE_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")


def die(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def validate(cfg):
    routes = cfg.get("routes")
    if not isinstance(routes, dict) or len(routes) < 2:
        die("config needs a 'routes' object with at least 2 route names")
    probs = []
    seen = {}  # normalized stem -> route (cross-route dup = ambiguous label)
    for name, stems in routes.items():
        if not ROUTE_RE.match(name):
            die(f"route name '{name}' must match {ROUTE_RE.pattern} "
                "(it becomes a tool name in generated calls)")
        if not isinstance(stems, list) or not stems:
            die(f"route '{name}' has no example phrases")
        if len(stems) < 5:
            probs.append(f"route '{name}': only {len(stems)} phrases — "
                         "accuracy scales with stem count (10+ recommended)")
        for s in stems:
            if not isinstance(s, str) or not s.strip():
                die(f"route '{name}' contains an empty phrase")
            key = re.sub(r"\{[a-z_]+\}", "{}", s.strip().lower())
            if key in seen and seen[key] != name:
                die(f"ambiguous phrase '{s}' appears in both "
                    f"'{seen[key]}' and '{name}'")
            seen[key] = name
    return probs


def run(cmd, **kw):
    p = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if p.returncode != 0:
        sys.stderr.write(p.stderr[-3000:])
        die(f"{' '.join(cmd[:2])} failed (rc={p.returncode})")
    return p


def last_jsons(text):
    return [json.loads(l) for l in text.strip().splitlines() if l.startswith("{")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="route config JSON")
    ap.add_argument("--hf", required=True, help="HF-format trunk dir (tokenizer + weights)")
    ap.add_argument("--name", default=None, help="head name (default: config filename)")
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--train-rows", type=int, default=2400)
    ap.add_argument("--eval-rows", type=int, default=400)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--iters", type=int, default=600)
    ap.add_argument("--lr", type=float, default=0.05)
    a = ap.parse_args()

    cfg = json.load(open(a.config))
    probs = validate(cfg)
    name = a.name or re.sub(r"\.json$", "", os.path.basename(a.config))
    os.makedirs(a.outdir, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        spec = os.path.join(td, "spec.jsonl")
        espec = os.path.join(td, "eval.jsonl")
        gen = os.path.join(HERE, "gen_routespec.py")
        tr = run([sys.executable, gen, a.config, str(a.train_rows), str(a.seed)])
        ev = run([sys.executable, gen, a.config, str(a.eval_rows), str(a.seed + 1)])
        # leakage guard: eval phrases that literally appear in train get dropped
        train_users = {json.loads(l)["user"].strip().lower() for l in tr.stdout.splitlines() if l.strip()}
        kept = [l for l in ev.stdout.splitlines()
                if l.strip() and json.loads(l)["user"].strip().lower() not in train_users]
        dropped = a.eval_rows - len(kept)
        open(spec, "w").write(tr.stdout)
        open(espec, "w").write("\n".join(kept) + "\n")

        out_head = os.path.join(a.outdir, f"{name}.head")
        p = run([sys.executable, os.path.join(HERE, "train_head.py"),
                 "--hf", a.hf, "--spec", spec, "--eval-spec", espec,
                 "--out", out_head, "--standardize",
                 "--iters", str(a.iters), "--lr", str(a.lr)])
        sys.stderr.write(p.stderr[-800:])
        stats = last_jsons(p.stdout)

    val, evm, wrote = stats[0], stats[1], stats[2]
    manifest = {
        "name": name, "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "head": os.path.basename(out_head),
        "routes": sorted(cfg["routes"]),
        "train_rows": a.train_rows, "eval_rows": len(kept),
        "eval_dropped_leaked": dropped,
        "val": val, "eval": {k: v for k, v in evm.items() if k != "confusion"},
        "confusion": evm.get("confusion"), "T": wrote["T"],
        "serve": f"ANVIL_HEAD={name}.head ./anvil-serve model.bin <port>",
    }
    mpath = os.path.join(a.outdir, f"{name}.head.json")
    json.dump(manifest, open(mpath, "w"), indent=2)

    print(json.dumps({"head": out_head, "manifest": mpath,
                      "eval_acc": evm["acc"], "eval_ece": evm["ece"],
                      "warnings": probs}, indent=2))


if __name__ == "__main__":
    main()
