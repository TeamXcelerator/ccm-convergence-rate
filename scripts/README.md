# Individual claim runners

Run one claim at a time with its numbered Bash script. The mathematical calculations remain in the Rust executable. The existing Python driver performs scalar fits, retains logs, and checks the resulting evidence.

```bash
# Inspect the four fixed configurations without building or computing.
bash scripts/claim2_precision_slope.sh --plan

# Build the locked source and verify configuration, without computing a claim.
bash scripts/claim2_precision_slope.sh --validate-only

# Reproduce the declared grid and retain its evidence locally.
bash scripts/claim2_precision_slope.sh
```

Every normal invocation builds the locked Rust source. Supplying `BIN` selects a prebuilt executable, which must report the same source digest, Toolkit revision, and required features. Reusing an old executable merely because it exists is not supported. `CARGO_TARGET_DIR` and `CARGO_BUILD_JOBS` control the local build.

Defaults are seeded reference-indexed root refinement, the even sector, the automatic eigenstate solver, Ultra capture, eight retained eigenpairs per sector, and no optional sector gap certificate. Seeded refinement reproduces the historical reference-indexed experiment; it is not independent spectral identification. `--root-acquisition independent` requests complete independent positive-root discovery and requires an Arb build with FLINT 3. `--parallel-gl-roots` is an explicit native-Linux runtime option and is unsupported on WSL. No hard elapsed-time limit is imposed by these runners.

C1, C2, and C3 are explicit precision-floor controls: they use `--ground-index-policy record-outcome`, retain the algebraic ground-index proof outcome, and may report a selected finite state whose ground index is unresolved or conclusively nonground. Their explicit `--precision-control-capture` assessment uses `paper3-precision-control-v3` and can complete applicable coverage while raw requested capture remains incomplete: it preserves four narrowly identified sector or response outcomes unavailable at the retained precision. Nonground and counted-cluster cases must also satisfy conservative bounds below the storage policy scale; the selected state is never promoted to a ground state. Unknown errors, resource limits, and missing inputs still stop execution. An unestablished ground index makes the overall hypothesis verdict UNASSESSED; individual numerical fit checks and source qualifications remain visible. Other claims require the ground-index proof and all requested capture to succeed. `--ground-index-policy require` makes the controls strict and disables their applicability assessment. See [the reproduction notes](../docs/REPRODUCTION.md) for the exact scope and published evidence.

`XC_CLAIM_MEMORY_GIB` defaults to 32 GiB. `XC_CLAIM_STREAM_SCALAR_BYTES` defaults to 274877906944 cumulative scalar-text bytes; it is a work budget, not a resident-memory allocation. A large grid may require a larger admitted memory budget. The Toolkit still performs numerical and resource admission.

| Claim | Script | Fixed executable grid | Finite evaluation |
|---|---|---|---|
| C1 | `claim1_budget_switch.sh` | C=13, N=80, P=30,45,90,180 | Descriptive precision sweep; UNASSESSED |
| C2 | `claim2_precision_slope.sh` | C=50, N=400, P=50,100,150,200 | Absolute slope difference from 1 at most 0.005; R² at least 0.999 |
| C3 | `claim3_floor_artifact.sh` | C=50, N=400, P=50,150,300; matching and natural/forced evenness | Descriptive floor diagnostic; UNASSESSED |
| C4 | `claim4_nmode_ramp.sh` | Shared ramp grid below | Maximum normalized fitted RMSE at most 0.05 |
| C5, C6 | No executable wrapper | Analytical arguments in the manuscript | Not numerical claim runs |
| C7 | `claim7_archimedean_slope.sh` | C=7, N=2 through 8, P=200 | Relative fitted slope difference below 15%; all seven rows required |
| C8 | `claim8_mode_exponent.sh` | Shared ramp grid below | Regression intercept and slope within 0.12 of γ and 1/2 |
| C9 | `claim9_onset_constant.sh` | Shared ramp grid below | Mean fitted onset within 0.1 of 4/π |
| C10 | `claim10_shannon.sh` | C=100, N=100 through 1200 by 100, P=700 | First 98% model-floor crossing at N/(C ln C) in [1.8,2.6] |
| C11 | `claim11_prime_anchor.sh` | C=100, N=1000, P=700 | Matching digits within 3 of historical 526.08 |
| C12 | `claim12_matching_floor.sh` | C=200, N=2400,2800, P=1250 | Last row within 3 digits of the matching-floor model |
| C13 | `claim13_prime_smooth.sh` | C=4 through 30 by 1, N=300, P=200 | Mean unit-step increase in [4.5,6.0] digits |
| C14 | `claim14_bottleneck.sh` | C=13, (N,P)=(40,100),(80,200),(120,400),(200,800) | Last finite row within 4 digits of the model floor |

Here C=λ² and P is requested decimal precision. The default retained zero window is 1–5, limited by the finite dimension. C4, C7, C8, and C9 retain zero 1 only. The declared historical fit is for zero 1; selecting another ordinal produces an exploratory, UNASSESSED hypothesis result.

The C4/C8/C9 grid contains eight N values for each cutoff:

| C | N values | P |
|---|---|---|
| 7 | 3,5,7,9,11,13,15,18 | 200 |
| 13 | 7,11,16,21,27,33,39,44 | 200 |
| 20 | 12,20,28,38,48,58,68,78 | 300 |
| 25 | 16,28,40,55,70,85,98,108 | 300 |
| 50 | 40,70,105,140,175,210,240,260 | 500 |
| 100 | 90,170,250,330,410,490,560,620 | 700 |

Historical C=150 and C=200 ramp-fit rows remain reference values because their exact source grids were not preserved. The C7 acceptance band is the runner's 15% tolerance, not a new verification of the manuscript's historical 3% comparison. C12 and C14 test their stated finite endpoints; they do not establish an infinite-parameter plateau, a supremum, or a necessary convergence condition.

## Evidence, resume, and publication

`RESULTS_DIR` (or `--results-dir`) selects the parent directory. Each invocation creates a unique `claim-<name>-<UTC>-<id>` directory containing its request, verified build identity, measurement JSON files, logs, Rust capture journals, execution receipts, and a JSON claim summary under `claims/`. Existing reports are not overwritten.

`--resume-dir /path/to/prior/run` explicitly permits reuse. A retained result must match the source and executable hashes, exact configuration and policies, report and log hashes, and complete applicable capture. Legacy reports without these bindings remain available for inspection but are not silently accepted as current measurements. Identical sealed rows within one invocation may also be reused.

When publishing across several claims, retain one shared `XC_PUBLISH_STAGING_ROOT` for that sequence. Each row binds its canonical staged artifact identities and destination; reuse requires that closure to remain present in the same staging root. This permits C8 and C9 to analyze C4's completed rows without repeating the numerical work. Every final publication rechecks the complete shared inventory. Each claim keeps immutable copies of its publication report, inventory, and phase reports, so later claims do not change earlier publication evidence.

For a sweep with prepared runtime targets, set `XC_TARGET_SPEC_DIR` to a directory containing an exact `c<C>-d<P>.json` file for every cutoff and requested precision. The driver validates the complete target list before starting the first numerical point, then supplies the corresponding `XC_TARGET_SPEC_FILE` to each Rust process. Alternatively, supply a single compatible `XC_TARGET_SPEC_FILE` explicitly; using both settings is rejected as ambiguous. Target contents and configured preparer, provider, and native-helper files are hashed into the execution receipt, so a changed external source does not silently reuse an earlier target-dependent result.

The summary separates:

- `execution_integrity`: PASS only when the complete planned measurement grid, required roots, applicable capture, and requested publication succeed; otherwise INCOMPLETE.
- `hypothesis_verdict`: PASS, FAIL, or UNASSESSED for the declared finite empirical check. A false hypothesis does not imply a computation failure.
- `claim_complete`: false for incomplete execution or a `--quick` subset. Quick mode is useful for development and does not complete the full claim.

`--publish` opts into configured **private** artifact publication, which is off by default. The runner defers publication during the sweep and verifies the final publication report. Authentication and repository configuration must already be available. Incomplete numerical execution stops the sweep and retains its staging and journals for inspection. Research artifact acquisition and a finite hypothesis verdict have distinct meanings; neither establishes an asymptotic theorem.

The aggregate `retest_all_claims.sh` retains paper order and reuses compatible sealed rows. Prefer the individual scripts for a paid server, a first migration check, or an interrupted campaign.
