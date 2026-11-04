#!/usr/bin/env bash
# Run every empirical claim in paper order. Individual claim launchers are
# preferred when inspecting or publishing one claim at a time.
set -euo pipefail

source "$(dirname -- "${BASH_SOURCE[0]}")/claim_common.sh"
claim_run all "$@"
