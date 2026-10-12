#!/usr/bin/env python3
"""api_contract — drift guard: validate live responses against openapi.yaml.

Probes every typed endpoint, then checks:
  - every key the server returns is declared in the response schema
  - enum fields (action, reason) only carry declared values
Undeclared field or enum value = drift = exit 1.

  python3 bench/api_contract.py --url http://localhost:8097
"""
import argparse, json, sys, urllib.request

import yaml

SPEC = "openapi.yaml"
PROBES = {
    "/v1/route": [{"state": "ma poubelle n'a pas été ramassée"},
                  {"state": "reset my password", "expert": "civic_fr"}],
    "/v1/decide": [{"state": "bonjour"}],
    "/v1/noul": [{"state": "delete all users"}],
    "/v1/score": [{"state": "prove the riemann hypothesis"}],
    "/v1/assess": [{"state": "unlock the account"}],
}


def schema_props(spec, path):
    """Collect declared property names for an endpoint's 200 JSON response,
    resolving one level of local $ref."""
    op = spec["paths"].get(path, {}).get("post")
    if not op:
        return None, None
    sch = op["responses"]["200"]["content"]["application/json"]["schema"]
    ref = sch.get("$ref")
    if ref:
        name = ref.split("/")[-1]
        sch = spec["components"]["schemas"][name]
    props = set((sch.get("properties") or {}).keys())
    enums = {}
    for k, v in (sch.get("properties") or {}).items():
        if "enum" in v:
            enums[k] = set(v["enum"])
    return props, enums


def post(url, path, body):
    r = urllib.request.Request(url + path, data=json.dumps(body).encode(),
                               headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}


def get(url, path):
    try:
        with urllib.request.urlopen(url + path, timeout=30) as resp:
            body = resp.read()
            try:
                return resp.status, json.loads(body)
            except Exception:
                return resp.status, {}
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}


def check_public(url):
    """Probe the metered public surface: free metadata endpoints must be 200,
    POST /v1/* without a wallet must be 402 (metered, not accidentally free)."""
    drifts = []
    for path in ("/health", "/pricing", "/llms.txt", "/v1/lanes"):
        st, _ = get(url, path)
        if st != 200:
            drifts.append(f"GET {path}: HTTP {st}, want 200 (free)")
    st, res = get(url, "/v1/lanes")
    if st == 200 and not isinstance(res.get("lanes"), list):
        drifts.append("GET /v1/lanes: no lanes array in body")
    st, _ = post(url, "/v1/route", {"state": "probe"})
    if st != 402:
        drifts.append(f"POST /v1/route without wallet: HTTP {st}, want 402 (metered)")
    return drifts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8097")
    ap.add_argument("--spec", default=SPEC)
    ap.add_argument("--public", action="store_true",
                    help="probe the public metered surface instead of the upstream schema checks")
    a = ap.parse_args()
    if a.public:
        drifts = check_public(a.url)
        print(json.dumps({"url": a.url, "surface": "public",
                          "drift": drifts, "ok": not drifts}, indent=1))
        sys.exit(1 if drifts else 0)
    spec = yaml.safe_load(open(a.spec))
    drifts, checked = [], 0
    for path, bodies in PROBES.items():
        props, enums = schema_props(spec, path)
        if props is None:
            drifts.append(f"{path}: not in spec")
            continue
        for body in bodies:
            st, res = post(a.url, path, body)
            checked += 1
            if st != 200:
                print(f"  {path} -> HTTP {st} (skip schema check)")
                continue
            extra = set(res.keys()) - props
            if extra:
                drifts.append(f"{path}: undeclared fields {sorted(extra)} in {sorted(res.keys())}")
            for k, allowed in enums.items():
                if res.get(k) is not None and res[k] not in allowed:
                    drifts.append(f"{path}: {k}={res[k]!r} not in enum {sorted(allowed)}")
    print(json.dumps({"url": a.url, "probes": checked,
                      "drift": drifts, "ok": not drifts}, indent=1))
    sys.exit(1 if drifts else 0)


if __name__ == "__main__":
    main()
