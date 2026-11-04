# Reproducing the numerical claims

[Overview](../README.md) · [Claim scope](CLAIMS.md) ·
[Script catalog](../scripts/README.md) · [Results](RESULTS.md)

Run one claim at a time and retain its configuration, executable identity,
measurements, capture receipts, and summary. The current integration pins
Toolkit v0.17.0 at
`0cc3f9acf5f0886aeb9f4b6bfc4bcd36327b6f99`.

## Build and inspect

Use Linux or WSL2, Bash, Git, Python 3, and current stable Rust. The numerical
driver and Toolkit calculations use Rust with MPFR/GMP high precision. The
existing standard-library Python helper coordinates the claim grids and fits.

```bash
sudo apt-get install build-essential m4 libgmp-dev libmpfr-dev libmpc-dev
cargo build --release --locked --features hp --bin ccm-convergence-rate
bash scripts/claim2_precision_slope.sh --plan
bash scripts/claim2_precision_slope.sh --validate-only
```

`--plan` prints the selected grid without building or calculating it.
`--validate-only` checks the locked executable and numerical policies, without
starting numerical acquisition. It is not a resource guarantee or a successful
claim. The scripts build the matching executable when needed; a stale explicitly
selected executable must not be used as current evidence.

Independent complete-root discovery additionally requires the `arb` feature
and FLINT 3 or later. The standard scalar reproductions use seeded refinement,
which should not be relabeled independent discovery. Keep the source revision,
Cargo manifest, and lockfile together.

## Capture and external inputs

The wrappers default to Ultra capture, even-sector primary states, the automatic
eigenstate solver, and a five-root seeded window analyzed at zero 1. C4, C7, C8,
and C9 use a one-root window because their smallest mode counts do not support
the same multi-root comparison. Sector-gap certificates are off; increasing
capture does not silently enable that separate proof.

The default ground-index policy is `require`. The precision-floor controls
C1, C2, and C3 explicitly select `record-outcome`: the directed proof runs and
retains whether the selected stored state is established as the ground state.
An unsuccessful result retains its reason, without ground-state gap or angle
claims. The policy is bound into the request, artifact identity, and resume
checks; it is not an automatic fallback after an error. All declared `C,N,P`
values stay unchanged. Other numerical claims retain `require`.

Some Ultra diagnostics require a compatible target specification and
source-dependent prepared inputs. Those inputs are not bundled here. Missing
inputs produce explicit incomplete coverage; retaining a primary measurement
does not make that coverage complete. External preparation must validate its
join to the acquired source and preserve its numerical qualifications.

For a grid with several cutoff or precision settings, `XC_TARGET_SPEC_DIR`
selects a directory containing the exact per-row files `c{C}-d{P}.json`.
For one fixed target, use `XC_TARGET_SPEC_FILE` instead; setting both is refused.
Resume binds the target bytes, preparer recipe and referenced sources, and
provider/native helper identities. Changing those inputs requires new evidence.

Large finite arithmetic captures can require more than the 1000 bundled
reference ordinates. An explicit extension can be supplied with the paired
`XC_ARITHMETIC_REFERENCE_JSON` and `XC_ARITHMETIC_REFERENCE_IDENTITY` files.
The Toolkit authenticates the declared digest, record count, decimal precision,
strict ordering, and unchanged original 1000-record prefix. The selected file
must cover the required `N - min(N, 64)` prefix. Its identity and exact bytes
are retained with the run and checked during result sealing and resume.

This selection supplies supplemental arithmetic inputs. It does not change
the primary matrix, eigenstate, or root-reference selection. Configurations
whose required prefix fits the bundled table retain their original inputs.
The numerical provenance of any extension must accompany its identity;
structural validation alone does not establish that supplied numbers are zeros.

For a primary experiment without the full target-dependent Ultra scope,
explicitly select the lighter profile:

```bash
bash scripts/claim2_precision_slope.sh --research-capture claim
```

That run can assess the stated finite precision fit, but is not a completed
Ultra campaign. A managed Ultra run must supply all required inputs and inspect
the final diagnostic receipt. Acquisition completeness is separate from the
resolution of every numerical row within an acquired artifact.

Precision-starved controls may legitimately block diagnostics that require a
separated ground state. Those outcomes must remain visible. A completed finite
measurement, a successful finite fit, and complete Ultra acquisition are
different results; a successful fit does not establish a missing ground-state
premise or erase incomplete capture.

C1, C2, and C3 explicitly enable `--precision-control-capture`, implementing
`paper3-precision-control-v3`. Every requested diagnostic is attempted and the
raw receipt is preserved. The separate assessment can recognize specified
stored-precision separation failures only when their actual proof and source
binding support that classification. It cannot excuse missing inputs, resource
failures, or an unknown error. `--ground-index-policy require` disables this
control assessment; the other claim wrappers always retain the strict policy.

A conclusive nonground result remains nonground even when its residual interval
contains zero. For the nonground and counted-cluster cases, the assessment
requires consistent finite source metadata and a conservative factor-of-two
margin below the matrix rounding policy scale. Both a sign-resolved value below
that scale and a sign-unresolved interval may qualify. This concerns the selected
state's bracket, not all lower eigenvalues or an analytic assembly-error bound.
It never establishes the missing ground-state premise.

Read `all_requested_capture_complete` alongside `applicable_capture_complete`.
The latter can be true while the raw receipt and `capture_complete` remain
false. The assessment retains each qualified diagnostic's original outcome
and basis. Report such a run as a completed applicable precision control,
with the listed Ultra diagnostics unavailable, rather than as full Ultra
completion. Ground-dependent scientific conclusions remain `UNASSESSED`.

Cross-configuration analysis requires compatible independent configurations;
it is not inferred from one measurement. The historical scalar fits and later
indexed studies retain their original source and comparison definitions.

## Output and reuse

Each invocation creates a new results directory under `claim-runs/` by
default. `RESULTS_DIR` selects its parent; the final path is printed. The
retained records bind the requested
configuration and numerical policies to the current executable and sources.
The run stores logs, lossless primary data, source dependencies, capture
receipts, and finite-check results. Missing final status is not success.

`--resume-dir` selects a previous invocation explicitly. Reuse requires its
configuration and executable/source identities and recorded result hashes to
match. A failed or partial record must not be promoted merely because a JSON
file exists. New identities require new calculations; previous records remain
historical evidence.

C4, C8, and C9 share a measurement grid. Reuse those measurements through the
explicit resume mechanism instead of repeating a costly sweep. `--quick`
reduces the declared grid and skips large saturation claims; the summary must
retain that restricted scope.

Toolkit cache reuse is also identity-bound. `XC_CACHE_ROOT` chooses the local
cache; `XC_CACHE_REMOTE=none` disables remote lookup. A numerical comparison
uses the same checks whether a compatible artifact is reused or computed.
Older Toolkit artifacts are not made current by editing their metadata.

## Resources and precision

`P` denotes requested decimal digits. The initial source allocation and the
evaluation precision used by guarded solves, root refinement, and diagnostics
are separate. Retain the actual source and work precision; historical formulas
with a 64-bit reserve do not prescribe all current evaluation guards.

The public wrappers default to a 32 GiB working-memory admission budget.
Set `XC_CLAIM_MEMORY_GIB` explicitly for the selected host and workload;
this default does not admit every large claim. `XC_CLAIM_STREAM_SCALAR_BYTES`
sets the separate endpoint budget, defaulting to 256 GiB in the wrappers.

For a server campaign, derive the worker count and memory budget from the
current CPU affinity and effective container limits, retaining system
headroom. Host-wide core and RAM totals can exceed what the container may
use; fixed settings from a previous server are not a reliable resource plan.

U-flow selects its stage worker count from the live working-memory budget,
including retained sources and nested action workspace. Other stages retain
the available worker pool. This changes concurrency, not precision, arithmetic
order, or the requested diagnostics. Insufficient capacity for one worker
remains an explicit refusal.

Large retained even matrices can share the already validated, reserved runtime
allocation with prefix diagnostics. The handoff checks the original canonical
payload digest and byte count; it does not replace or reassemble the source.

More CPU workers are not automatically faster: concurrent arbitrary-precision
operations can increase memory and scheduling costs. The working-memory
admission budget is distinct from measured peak resident memory. The stream
scalar budget limits cumulative serialized scalar endpoints rather than RAM.
Use the claim plan and recorded timings instead of extrapolating from GPU count
alone.

CUDA accelerates admitted exact integer products; reconstruction and other
stages still use the CPU. GPU dispatch does not convert the research arithmetic
into an approximate single-precision calculation. Numerical controls and
artifact identities must remain recorded when comparing CPU and GPU runs.
Native-Linux parallel Gauss–Legendre roots are a separate optional capability;
they are not a supported WSL execution path.

## Publication

Ordinary reproduction requires no publishing credentials and makes no remote
changes. `--publish` explicitly requests private artifact publication for
these claim scripts. Public source-code availability does not grant access to
private cached artifacts; absent compatible inputs are computed locally when
the selected scope permits it.

Publication completion needs the final inventory and verified destination
coverage, separately from execution and finite hypothesis outcomes. Keep
retained staging if publication fails. Do not rerun expensive primary work
solely because a destination was temporarily unavailable.

## Read the final result

The summary separates execution integrity (`PASS` or `INCOMPLETE`) from a
finite hypothesis (`PASS`, `FAIL`, or `UNASSESSED`). Descriptive demonstrations
do not acquire a positive hypothesis verdict by printing a conclusion.
Unresolved roots, missing planned rows, or invalid evidence cannot silently
drop out of an accepted fit.

An execution pass is evidence of a completed declared computation. It is not
a proof of the continuum or asymptotic statement. Consult [claim scope](CLAIMS.md)
and [results](RESULTS.md) alongside the machine-readable receipt.
