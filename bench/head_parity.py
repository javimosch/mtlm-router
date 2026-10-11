"""head_parity.py — golden-records parity gate: offline head_io scoring vs
live anvil /v1/route. Catches train/serve skew, wrong taps, transposed W,
stale artifacts — the class of bug that made civic-0.2.0 ship broken.

Usage (rbm21):
  python3 bench/head_parity.py --head models/mairie_mt3.head \
      --url http://localhost:8402 --expert mairie --key mk_... \
      --probes probes.txt            # one text per line
      --tol 0.05

Exit 0 = parity (every probe: same top route AND |dconf| <= tol).
Exit 1 = divergence found.
"""
import sys, json, argparse, urllib.request
sys.path.insert(0, "/root/mtlm/tools")
import numpy as np
import head_probe as hp
import head_io


def live(url, key, expert, text):
    body = json.dumps({"state": text, "expert": expert}).encode()
    req = urllib.request.Request(url + "/v1/route", data=body,
        headers={"content-type": "application/json", "authorization": f"Bearer {key}"})
    r = json.loads(urllib.request.urlopen(req, timeout=60).read())
    return r["route"], float(r["confidence"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--head", required=True)
    ap.add_argument("--url", default="http://localhost:8402")
    ap.add_argument("--expert", required=True)
    ap.add_argument("--key", default="")
    ap.add_argument("--probes", required=True, help="text file, one probe per line")
    ap.add_argument("--hf", default="/root/mtlm/hf/router3s384")
    ap.add_argument("--tol", type=float, default=0.05)
    a = ap.parse_args()

    texts = [l.strip() for l in open(a.probes) if l.strip()]
    h = head_io.load_head(a.head)
    rows = [(hp.DECIDE_SYS, [], t, "?") for t in texts]
    F = hp.features(a.hf, rows)
    X = np.concatenate([F[t] for t in h["taps"]], axis=1)
    P = head_io.probs(h, X)

    bad = 0
    rows_out = []
    for i, t in enumerate(texts):
        j = int(P[i].argmax())
        off_route, off_conf = h["labels"][j], float(P[i, j])
        lv_route, lv_conf = live(a.url, a.key, a.expert, t)
        ok = off_route == lv_route and abs(off_conf - lv_conf) <= a.tol
        bad += not ok
        rows_out.append({"text": t, "offline": [off_route, round(off_conf, 3)],
                         "live": [lv_route, round(lv_conf, 3)],
                         "dconf": round(abs(off_conf - lv_conf), 4), "ok": bool(ok)})
        mark = "ok " if ok else "BAD"
        print(f"{mark} {t[:45]:45s} off={off_route}@{off_conf:.3f} live={lv_route}@{lv_conf:.3f}")
    print(json.dumps({"probes": len(texts), "diverged": bad,
                      "parity": bad == 0, "tol": a.tol, "rows": rows_out}, indent=1))
    sys.exit(0 if bad == 0 else 1)


if __name__ == "__main__":
    main()
