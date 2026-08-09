#!/usr/bin/env python3
from pathlib import Path
import re


root = Path(__file__).resolve().parents[3]
workflow = (root / ".github/workflows/main-delivery.yml").read_text()
quality = (root / ".github/workflows/quality.yml").read_text()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


jobs_index = workflow.index("\njobs:\n")
queue = "\nconcurrency:\n  group: main-delivery\n  cancel-in-progress: false\n"
require(queue in workflow[:jobs_index], "workflow queue must precede every job")

for job in ("build-runtime", "build-worker-cpu", "build-web"):
    match = re.search(rf"^  {re.escape(job)}:\n(?P<body>.*?)(?=^  [a-z][a-z0-9-]*:|\Z)", workflow, re.M | re.S)
    require(match is not None, f"missing {job} job")
    require(re.search(r"^    needs: gate$", match.group("body"), re.M) is not None, f"{job} must depend directly on gate")

deploy = re.search(r"^  deploy-production:\n(?P<body>.*)\Z", workflow, re.M | re.S)
require(deploy is not None, "missing deploy-production job")
require("    concurrency:\n      group: production-deploy\n      cancel-in-progress: false\n" in deploy.group("body"), "deploy must retain production-deploy serialization")

release = re.search(r"^  release:\n(?P<body>.*?)(?=^  deploy-production:)", workflow, re.M | re.S)
require(release is not None, "missing release job")
body = release.group("body")
require("ref: ${{ github.sha }}" in body, "release must check out the pushed SHA")
require("run: scripts/ci/resolve-release-reconciliation.sh" in body, "release must run reconciliation resolver")
require(body.count("if: steps.reconcile.outputs.release_tag != ''") == 3, "all alias setup/publication steps must use the reconciled tag")
require("RELEASE: ${{ steps.reconcile.outputs.release_tag }}" in body, "release publication must use the reconciled tag")
require("gh release upload \"$RELEASE\" release-manifest.json --clobber" in body, "release manifest upload must remain idempotent")
require("docker/build-push-action" not in body and "ssh " not in body, "release job must neither rebuild nor deploy")

require("scripts/ci/tests/resolve-release-reconciliation_test.sh" in quality, "deferred quality must execute resolver harness")
require("scripts/ci/tests/main-delivery-workflow-contract_test.py" in quality, "deferred quality must execute workflow contracts")

print("main delivery concurrency and release contracts passed")
