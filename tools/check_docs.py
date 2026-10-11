"""check_docs.py — drift gate for site/docs.html.

Three claims classes that rotted before (pass-38 audit found them by hand):

1. Endpoint coverage — every path declared in openapi.yaml must appear in
   site/docs.html (a documented API table that silently lags the spec).
2. Numeric claims — "12 checks" for smoke.sh, "19/19" for contract.sh are
   re-counted from the scripts themselves, not trusted.
3. Plumbing exception — internal endpoints (_health, _shutdown) are exempt
   from doc coverage but still listed in the report.

Exit 1 on any drift, naming what to fix. JSON report on stdout.
Usage: python3 tools/check_docs.py [--docs site/docs.html] [--spec openapi.yaml]
"""
import argparse, json, re, sys

INTERNAL = {"/_health", "/_shutdown", "/livez", "/readyz", "/_qhat", "/health"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default="site/docs.html")
    ap.add_argument("--spec", default="openapi.yaml")
    ap.add_argument("--smoke", default="tools/smoke.sh")
    ap.add_argument("--contract", default="bench/systemone/contract.sh")
    a = ap.parse_args()

    docs = open(a.docs).read()
    spec_paths = re.findall(r"^  (/\S+):", open(a.spec).read(), re.M)
    smoke_n = len(re.findall(r"^\s*check ", open(a.smoke).read(), re.M))
    contract_n = len(re.findall(r'^\s*t "', open(a.contract).read(), re.M))

    problems, undocumented = [], []
    for p in spec_paths:
        if p in INTERNAL:
            continue
        if p not in docs:
            undocumented.append(p)
    if undocumented:
        problems.append(f"openapi paths missing from docs.html: {undocumented}")

    for claim in re.findall(r"(\d+)\s*(?:endpoint\+gate\s*)?checks", docs):
        if int(claim) != smoke_n:
            problems.append(f"smoke.sh has {smoke_n} checks, docs.html claims {claim}")
            break
    if "smoke" in docs and not re.search(r"(\d+)\s*(?:endpoint\+gate\s*)?checks", docs):
        problems.append("docs.html mentions smoke.sh but no check count")

    for claim in re.findall(r"(\d+)/\d+\s*(?:Jev-contract\s*)?conformance", docs):
        if int(claim) != contract_n:
            problems.append(f"contract.sh has {contract_n} checks, docs.html claims {claim}")
            break

    print(json.dumps({
        "ok": not problems,
        "problems": problems,
        "spec_paths": len(spec_paths),
        "documented": len(spec_paths) - len(undocumented) - len([p for p in spec_paths if p in INTERNAL]),
        "internal_skipped": sorted(p for p in spec_paths if p in INTERNAL),
        "smoke_checks": smoke_n, "contract_checks": contract_n,
    }))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
