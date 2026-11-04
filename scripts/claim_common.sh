#!/usr/bin/env bash
# Shared public reproduction launcher. Numerical work stays in the Rust binary.

CLAIM_REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)

claim_run() {
  local claim=$1
  shift
  cd "$CLAIM_REPO_ROOT"
  local plan=false help=false publish=false parallel=false arg strict_ground=false next_ground=false
  local -a args=()
  for arg in "$@"; do
    if [[ $next_ground == true ]]; then
      [[ $arg != require ]] || strict_ground=true
      next_ground=false
    fi
    case "$arg" in
      --ground-index-policy) next_ground=true ;;
      --ground-index-policy=require) strict_ground=true ;;
    esac
  done
  case "$claim" in
    budget-switch|precision-slope|floor-artifact|all)
      [[ $strict_ground == true ]] || args+=(--precision-control-capture) ;;
  esac
  for arg in "$@"; do
    case "$arg" in
      --publish) publish=true ;;
      --plan) plan=true; args+=("$arg") ;;
      --help|-h) help=true; args+=("$arg") ;;
      --parallel-gl-roots) parallel=true; args+=("$arg") ;;
      *) args+=("$arg") ;;
    esac
  done
  command -v python3 >/dev/null || {
    echo 'Python 3 is required for the existing fit and journal orchestration.' >&2
    return 2
  }
  export PYTHONDONTWRITEBYTECODE=1
  export XC_RUN_PROFILE=${XC_RUN_PROFILE:-normal}
  export XC_PUBLISH_TARGET=none XC_PUBLISH_EXECUTE=false
  if [[ $publish == true ]]; then
    export XC_RUN_PROFILE=author XC_PUBLISH_TARGET=private
    export XC_PUBLISH_EXECUTE=true XC_PUBLISH_REPLACE=false
  fi
  if [[ $plan != true && $help != true ]]; then
    local memory=${XC_CLAIM_MEMORY_GIB:-32}
    [[ $memory =~ ^[1-9][0-9]{0,9}$ ]] && ((memory <= 8589934591)) || {
      echo 'XC_CLAIM_MEMORY_GIB must be an integer in 1..8589934591.' >&2
      return 2
    }
    export XC_RESEARCH_WORKING_BYTES=$((memory << 30))
    if [[ -z ${BIN+x} ]]; then
      command -v cargo >/dev/null || {
        echo 'Load the Rust environment or supply BIN matching these locked sources.' >&2
        return 2
      }
      local target=${CARGO_TARGET_DIR:-"$CLAIM_REPO_ROOT/target"}
      local features=hp
      # Complete independent discovery needs FLINT; seeded historical reproduction
      # does not require it. Build Arb when independent was selected by either path.
      local independent=${ROOT_ACQUISITION_MODE:-seeded} next=false
      for arg in "${args[@]}"; do
        if [[ $next == true ]]; then independent=$arg; next=false; fi
        case "$arg" in
          --root-acquisition) next=true ;;
          --root-acquisition=*) independent=${arg#*=} ;;
        esac
      done
      if [[ $independent == independent ]]; then
        command -v pkg-config >/dev/null && pkg-config --atleast-version=3 flint || {
          echo 'Complete independent discovery requires FLINT 3 and pkg-config.' >&2
          return 2
        }
        features+=,arb
      fi
      local -a build=(cargo build --release --locked --features "$features"
        --bin ccm-convergence-rate --target-dir "$target")
      [[ -z ${CARGO_BUILD_JOBS:-} ]] || build+=(--jobs "$CARGO_BUILD_JOBS")
      "${build[@]}"
      BIN="$target/release/ccm-convergence-rate"
    fi
    [[ -x $BIN ]] || { echo "Binary is not executable: $BIN" >&2; return 2; }
  fi
  python3 -B scripts/reproduce.py "$claim" \
    --bin "${BIN:-$CLAIM_REPO_ROOT/target/release/ccm-convergence-rate}" \
    --root-acquisition "${ROOT_ACQUISITION_MODE:-seeded}" \
    --parity-policy "${PARITY_POLICY:-even-sector}" \
    --eigenstate-solver "${EIGENSTATE_SOLVER:-auto}" \
    --research-capture "${RESEARCH_CAPTURE_LEVEL:-ultra}" \
    --research-sector-eigenpairs "${RESEARCH_SECTOR_EIGENPAIRS:-8}" \
    --capture-maximum-stream-scalar-bytes "${XC_CLAIM_STREAM_SCALAR_BYTES:-274877906944}" \
    --first-zero-index "${FIRST_ZERO_INDEX:-1}" \
    --zero-count "${ZERO_COUNT:-5}" \
    --analysis-zero-index "${ANALYSIS_ZERO_INDEX:-1}" \
    --results-dir "${RESULTS_DIR:-$CLAIM_REPO_ROOT/claim-runs}" \
    "${args[@]}"
}
