#!/usr/bin/env bash
# Claim 11: prime-ceiling anchor.
# Configuration: lambda^2=100, N=1000, P=700.
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/claim_common.sh"
run_convergence_claim prime-anchor "$@"
