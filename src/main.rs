// Copyright (c) 2026 Ronnie Andrews, Jr. (Team Xcelerator Inc.(R))
// All rights reserved. See LICENSE file for terms.
//
// This source code is provided for verification and study purposes only.
// Modification, redistribution, and commercial use are prohibited
// without explicit written permission.

//! CCM Zeta Spectral Triple — Convergence Formula
//!
//! Measures the convergence of an explicitly indexed window of CCM roots
//! against the toolkit-owned high-precision reference-zero dataset. Root
//! acquisition, parity, eigenstate solver, and research capture are explicit
//! and independently represented in artifact and result provenance.

use anyhow::{Context, Result};
use clap::{Parser, Subcommand, ValueEnum};
use serde::Serialize;
use std::fs;
use std::path::{Path, PathBuf};

use xc_spectral::ccm::{self, CcmParams};

#[cfg(feature = "hp")]
mod capture;
mod journal;
#[cfg(feature = "hp")]
mod preparation;

const TOOLKIT_REVISION: &str = "97e9445ebbf1844a7d60b5141d3fb737fe9f00dd";

fn build_info() -> serde_json::Value {
    serde_json::json!({
        "schema_version": 1,
        "software_version": env!("CARGO_PKG_VERSION"),
        "version": env!("CARGO_PKG_VERSION"),
        "toolkit_revision": TOOLKIT_REVISION,
        "implementation_digest": journal::implementation_digest(),
        "hp_enabled": cfg!(feature = "hp"),
        "complete_positive_roots": cfg!(feature = "arb"),
        "parallel_gl_roots": cfg!(feature = "hp"),
        "features": {"hp": cfg!(feature = "hp"), "arb": cfg!(feature = "arb")}
    })
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, ValueEnum)]
#[serde(rename_all = "kebab-case")]
enum ParityPolicy {
    Natural,
    AdaptiveEven,
    EvenSector,
}

impl ParityPolicy {
    fn as_str(self) -> &'static str {
        match self {
            Self::Natural => "natural",
            Self::AdaptiveEven => "adaptive-even",
            Self::EvenSector => "even-sector",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, ValueEnum)]
#[serde(rename_all = "kebab-case")]
enum EigenstateSolver {
    LegacyInverseIteration,
    ShiftInvertKrylov,
    Auto,
}

impl EigenstateSolver {
    fn as_str(self) -> &'static str {
        match self {
            Self::LegacyInverseIteration => "legacy-inverse-iteration",
            Self::ShiftInvertKrylov => "shift-invert-krylov",
            Self::Auto => "auto",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, ValueEnum)]
#[serde(rename_all = "kebab-case")]
enum RootAcquisition {
    Seeded,
    Independent,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, ValueEnum)]
#[serde(rename_all = "kebab-case")]
enum GroundIndexPolicy {
    /// Require the Toolkit's directed ground-index and separation proof.
    Require,
    /// Retain the directed outcome for a selected stored-state experiment.
    RecordOutcome,
}

impl RootAcquisition {
    fn as_str(self) -> &'static str {
        match self {
            Self::Seeded => "seeded",
            Self::Independent => "independent",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, ValueEnum)]
#[serde(rename_all = "kebab-case")]
enum ResearchCapture {
    Claim,
    Research,
    Gap,
    Maximum,
    Ultra,
}

impl ResearchCapture {
    fn as_str(self) -> &'static str {
        match self {
            Self::Claim => "claim",
            Self::Research => "research",
            Self::Gap => "gap",
            Self::Maximum => "maximum",
            Self::Ultra => "ultra",
        }
    }
}

#[derive(Parser)]
#[command(
    name = "ccm-convergence-rate",
    version,
    about = "CCM Zeta Spectral Triple convergence measurement"
)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// Measure matching digits for an explicitly indexed window of CCM roots.
    Measure {
        /// Lambda squared. Prime powers p^m <= lambda^2 enter the Weil form.
        #[arg(long, default_value_t = 13_u64)]
        lambda_sq: u64,

        /// Mode cutoff N. Matrix size is 2N+1.
        #[arg(long, default_value_t = 120)]
        n_modes: usize,

        /// Requested decimal precision. The toolkit adds its qualified guard bits.
        #[arg(long, default_value_t = 200)]
        precision_digits: u32,

        /// One-based reference-zero ordinal at the beginning of the requested window.
        #[arg(long, default_value_t = 1)]
        first_zero_index: usize,

        /// Number of consecutive reference-zero ordinals to refine and report.
        #[arg(long, default_value_t = 5)]
        zero_count: usize,

        /// Significant digits displayed in the human-readable table.
        #[arg(long, default_value_t = 16)]
        display_digits: usize,

        /// Root acquisition policy.
        #[arg(long, value_enum, default_value_t = RootAcquisition::Seeded)]
        root_acquisition: RootAcquisition,

        /// Eigenstate parity policy.
        #[arg(long, value_enum, default_value_t = ParityPolicy::EvenSector)]
        parity_policy: ParityPolicy,

        /// Eigenstate algorithm.
        #[arg(long, value_enum, default_value_t = EigenstateSolver::Auto)]
        eigenstate_solver: EigenstateSolver,

        /// Ground-index admission. Record-outcome is an explicit selected-state
        /// experiment; an unestablished outcome never proves a ground-state claim.
        #[arg(long, value_enum, default_value_t = GroundIndexPolicy::Require)]
        ground_index_policy: GroundIndexPolicy,

        /// Separately assess unavailable diagnostics for the fixed precision-control
        /// experiments. Raw Ultra outcomes and incomplete capture remain unchanged.
        #[arg(long)]
        precision_control_capture: bool,

        /// Supplemental artifact capture level.
        #[arg(long, value_enum, default_value_t = ResearchCapture::Claim)]
        research_capture: ResearchCapture,

        /// Low eigenpairs retained per parity sector in maximum capture.
        #[arg(long, default_value_t = 8)]
        research_sector_eigenpairs: usize,

        /// Enable native-Linux parallel Gauss-Legendre roots (unsupported on WSL).
        #[arg(long)]
        parallel_gl_roots: bool,

        /// Request the separate sector-gap certificate. Off by default.
        #[arg(long)]
        capture_sector_gap_certificate: bool,

        /// Cumulative scalar-text budget for streaming finite diagnostics.
        #[arg(long, default_value_t = 274_877_906_944_u64)]
        capture_maximum_stream_scalar_bytes: u64,

        /// Parent directory for immutable request, primary, and capture journals.
        #[arg(long, default_value = "results/journals")]
        capture_output: PathBuf,

        /// Retain root-certificate outcomes separately from computed refinements.
        #[arg(long)]
        certify_roots: bool,

        /// Optional structured result file. Parent directories are created.
        #[arg(long)]
        json_output: Option<PathBuf>,
    },

    /// Compare unrestricted and forced-even smallest eigenstates.
    MeasureEvenness {
        #[arg(long)]
        lambda_sq: u64,

        #[arg(long)]
        n_modes: usize,

        #[arg(long)]
        precision_digits: u32,

        #[arg(long, default_value_t = 16)]
        display_digits: usize,

        #[arg(long, value_enum, default_value_t = EigenstateSolver::Auto)]
        eigenstate_solver: EigenstateSolver,

        /// Parent directory for immutable evenness source and measurement journals.
        #[arg(long, default_value = "results/journals")]
        capture_output: PathBuf,

        /// Retain selected-state outcomes explicitly for precision-floor controls.
        #[arg(long, value_enum, default_value_t = GroundIndexPolicy::Require)]
        ground_index_policy: GroundIndexPolicy,

        #[arg(long)]
        json_output: Option<PathBuf>,
    },

    /// Finalize all staged artifacts in the current publication root once.
    ///
    /// The reproduction driver computes every point with remote mutation
    /// temporarily disabled, then invokes this command after the whole claim
    /// succeeds. This prevents one Git transaction per numerical point.
    FinalizePublication,
}

fn main() -> Result<()> {
    let arguments = std::env::args().collect::<Vec<_>>();
    if arguments.len() == 2 && arguments[1] == "--build-info" {
        println!("{}", build_info());
        return Ok(());
    }
    let cli = Cli::parse();
    match cli.command {
        Command::Measure {
            lambda_sq,
            n_modes,
            precision_digits,
            first_zero_index,
            zero_count,
            display_digits,
            root_acquisition,
            parity_policy,
            eigenstate_solver,
            ground_index_policy,
            precision_control_capture,
            research_capture,
            research_sector_eigenpairs,
            parallel_gl_roots,
            capture_sector_gap_certificate,
            capture_maximum_stream_scalar_bytes,
            capture_output,
            certify_roots,
            json_output,
        } => run_measure(MeasureRequest {
            lambda_sq,
            n_modes,
            precision_digits,
            first_zero_index,
            zero_count,
            display_digits,
            root_acquisition,
            parity_policy,
            eigenstate_solver,
            ground_index_policy,
            precision_control_capture,
            research_capture,
            research_sector_eigenpairs,
            parallel_gl_roots,
            capture_sector_gap_certificate,
            capture_maximum_stream_scalar_bytes,
            capture_output,
            certify_roots,
            json_output,
        }),
        Command::MeasureEvenness {
            lambda_sq,
            n_modes,
            precision_digits,
            display_digits,
            eigenstate_solver,
            ground_index_policy,
            capture_output,
            json_output,
        } => run_measure_evenness(
            lambda_sq,
            n_modes,
            precision_digits,
            display_digits,
            eigenstate_solver,
            ground_index_policy,
            capture_output,
            json_output,
        ),
        Command::FinalizePublication => finalize_publication(),
    }
}

#[derive(Clone, Serialize)]
struct MeasureRequest {
    lambda_sq: u64,
    n_modes: usize,
    precision_digits: u32,
    first_zero_index: usize,
    zero_count: usize,
    display_digits: usize,
    root_acquisition: RootAcquisition,
    parity_policy: ParityPolicy,
    eigenstate_solver: EigenstateSolver,
    ground_index_policy: GroundIndexPolicy,
    precision_control_capture: bool,
    research_capture: ResearchCapture,
    research_sector_eigenpairs: usize,
    parallel_gl_roots: bool,
    capture_sector_gap_certificate: bool,
    capture_maximum_stream_scalar_bytes: u64,
    capture_output: PathBuf,
    certify_roots: bool,
    json_output: Option<PathBuf>,
}

#[derive(Serialize)]
struct MeasurementReport {
    schema_version: u32,
    application: &'static str,
    application_version: &'static str,
    toolkit_version: String,
    build_info: serde_json::Value,
    journal: PathBuf,
    capture_complete: bool,
    all_requested_capture_complete: bool,
    applicable_capture_complete: bool,
    precision_control_capture: bool,
    capture_applicability: serde_json::Value,
    capture_applicability_artifact: Option<xc_cache::ArtifactManifest>,
    capture_receipt: serde_json::Value,
    primary_sources: Vec<xc_cache::ArtifactManifest>,
    root_acquisition: RootAcquisition,
    parity_policy: ParityPolicy,
    eigenstate_solver: EigenstateSolver,
    ground_index_policy: GroundIndexPolicy,
    ground_index_admission: serde_json::Value,
    stored_state_resolution: serde_json::Value,
    selected_state_scope: &'static str,
    research_capture: ResearchCapture,
    research_sector_eigenpairs: usize,
    comparison_semantics: &'static str,
    lambda_sq: u64,
    n_modes: usize,
    matrix_size: usize,
    precision_digits_requested: u32,
    precision_bits_working: u32,
    first_zero_index: usize,
    zero_count_requested: usize,
    zero_count_returned: usize,
    reference_dataset: ReferenceDatasetReport,
    rayon_workers: usize,
    available_cpus: usize,
    elapsed_seconds: f64,
    weil_min_eigenvalue: String,
    selected_eigenvalue: String,
    roots: Vec<RootMeasurement>,
}

#[derive(Serialize)]
struct ReferenceDatasetReport {
    resource_id: String,
    content_sha256: String,
    record_count: usize,
    decimal_digits: u32,
}

#[derive(Serialize)]
struct RootMeasurement {
    reference_index: usize,
    status: &'static str,
    computed_value: Option<String>,
    reference_value: String,
    absolute_error: Option<String>,
    relative_error: Option<String>,
    matching_digits: Option<String>,
    matching_digits_f64: Option<f64>,
    iterations: usize,
    achieved_decimal_digits: Option<String>,
    final_correction: Option<String>,
    residual: Option<String>,
    failure_reason: Option<String>,
}

#[derive(Serialize)]
struct EvennessReport {
    schema_version: u32,
    application: &'static str,
    application_version: &'static str,
    toolkit_version: String,
    build_info: serde_json::Value,
    capture_complete: Option<bool>,
    capture_scope: &'static str,
    journal: PathBuf,
    primary_sources: Vec<xc_cache::ArtifactManifest>,
    claim_scope: serde_json::Value,
    assembly_error_bound: Option<String>,
    eigenstate_solver: EigenstateSolver,
    ground_index_policy: GroundIndexPolicy,
    ground_index_admission: serde_json::Value,
    source_state_resolutions: Vec<serde_json::Value>,
    selected_state_scope: &'static str,
    lambda_sq: u64,
    n_modes: usize,
    matrix_size: usize,
    precision_digits_requested: u32,
    precision_bits_working: u32,
    evenness_deviation: String,
    natural_eigenvalue: String,
    forced_even_eigenvalue: String,
    natural_sign: String,
    forced_even_sign: String,
}

#[cfg(feature = "hp")]
fn high_prec_config(
    precision_digits: u32,
    parity_policy: ParityPolicy,
    eigenstate_solver: EigenstateSolver,
    zero_count: usize,
) -> ccm::hp::HighPrecConfig {
    let mut cfg = ccm::hp::HighPrecConfig::for_decimal_digits(precision_digits);
    cfg.n_eigenvalues = zero_count;
    cfg.set_parity_policy(match parity_policy {
        ParityPolicy::Natural => ccm::hp::CcmParityPolicy::Natural,
        ParityPolicy::AdaptiveEven => ccm::hp::CcmParityPolicy::AdaptiveEven,
        ParityPolicy::EvenSector => ccm::hp::CcmParityPolicy::EvenSector,
    });
    cfg.eigenstate_solver = match eigenstate_solver {
        EigenstateSolver::LegacyInverseIteration => {
            ccm::hp::CcmEigenstateSolver::LegacyInverseIteration
        }
        EigenstateSolver::ShiftInvertKrylov => ccm::hp::CcmEigenstateSolver::ShiftInvertKrylov,
        EigenstateSolver::Auto => ccm::hp::CcmEigenstateSolver::Auto,
    };
    cfg
}

#[cfg(feature = "hp")]
fn run_measure(request: MeasureRequest) -> Result<()> {
    let journal =
        journal::Journal::start(&request.capture_output, &serde_json::to_value(&request)?)?;
    let resources = xc_core::RunResources::with_worker_limit(
        ccm::capture_runtime::CaptureResourcePolicy::from_environment()?.maximum_working_bytes,
        rayon::current_num_threads(),
    )?
    .waiting_for_independent();
    let _scope = resources.enter();
    let policy = xc_numerics::hp_runtime::HpRuntimePolicy {
        parallel_gl_roots: request.parallel_gl_roots,
        ..Default::default()
    };
    let result = xc_numerics::hp_runtime::run_hp_with_policy(&policy, || {
        run_measure_inner(&request, &journal)
    })
    .map_err(anyhow::Error::from)
    .and_then(std::convert::identity);
    if let Err(error) = &result {
        journal.save(
            "failure.json",
            &serde_json::json!({
                "error": format!("{error:#}"),
                "primary_saved": journal.directory.join("primary.json").exists(),
            "measurements_saved": journal.directory.join("measurements.json").exists()
                || journal.directory.join("primary-measurements.json").exists()
            }),
        )?;
    }
    result
}

#[cfg(feature = "hp")]
fn run_measure_inner(request: &MeasureRequest, journal: &journal::Journal) -> Result<()> {
    use rug::Float;

    if request.lambda_sq < 2 {
        anyhow::bail!("lambda-sq must be at least 2 (got {})", request.lambda_sq);
    }
    if request.n_modes == 0 {
        anyhow::bail!("n-modes must be positive");
    }
    if request.precision_digits == 0 {
        anyhow::bail!("precision-digits must be positive");
    }
    if request.first_zero_index == 0 {
        anyhow::bail!("first-zero-index is one-based and must be positive");
    }
    if request.zero_count == 0 {
        anyhow::bail!("zero-count must be positive");
    }
    if request.display_digits == 0 {
        anyhow::bail!("display-digits must be positive");
    }
    if request.research_sector_eigenpairs == 0 {
        anyhow::bail!("research-sector-eigenpairs must be positive");
    }
    anyhow::ensure!(
        (1..=1_099_511_627_776).contains(&request.capture_maximum_stream_scalar_bytes),
        "capture-maximum-stream-scalar-bytes must be in 1..=1099511627776"
    );
    anyhow::ensure!(
        !request.certify_roots || cfg!(feature = "arb"),
        "root certification requires a build with --features arb"
    );
    anyhow::ensure!(
        request.root_acquisition != RootAcquisition::Independent || cfg!(feature = "arb"),
        "independent root discovery requires a build with --features arb"
    );
    let last_zero_index = request
        .first_zero_index
        .checked_add(request.zero_count - 1)
        .context("requested zero window overflows usize")?;

    let params = CcmParams::from_lambda_sq_integer(request.lambda_sq, request.n_modes);
    let prime_powers = ccm::prime_powers_up_to(params.lambda_sq_int());
    let mut cfg = high_prec_config(
        request.precision_digits,
        request.parity_policy,
        request.eigenstate_solver,
        request.zero_count,
    );
    cfg.ground_index_policy = match request.ground_index_policy {
        GroundIndexPolicy::Require => ccm::hp::CcmGroundIndexPolicy::Require,
        GroundIndexPolicy::RecordOutcome => ccm::hp::CcmGroundIndexPolicy::RecordOutcome,
    };
    capture::preflight(request, cfg.precision_bits)?;
    let dataset = xc_zeta::zeros::bundled_dataset_identity()?;
    if last_zero_index > dataset.record_count {
        anyhow::bail!(
            "requested zero window {}..={} exceeds bundled reference count {}",
            request.first_zero_index,
            last_zero_index,
            dataset.record_count
        );
    }
    let all_reference_strings = xc_zeta::zeros::bundled_first_n_strings(last_zero_index)?;
    let reference_strings = &all_reference_strings[(request.first_zero_index - 1)..last_zero_index];
    let zero_seeds = reference_strings
        .iter()
        .map(|value| {
            Float::parse(value)
                .map(|parsed| Float::with_val(cfg.precision_bits, parsed))
                .map_err(|error| anyhow::anyhow!("invalid bundled zero {value:?}: {error}"))
        })
        .collect::<Result<Vec<_>>>()?;

    let rayon_workers = rayon::current_num_threads();
    let available_cpus = std::thread::available_parallelism()
        .map(|value| value.get())
        .unwrap_or(1);

    println!(
        "CCM operator: lambda^2={}, N={}, matrix_size={}",
        request.lambda_sq,
        params.n_modes,
        params.matrix_size()
    );
    println!(
        "  prime powers k <= {}: {} entries",
        request.lambda_sq,
        prime_powers.len()
    );
    println!(
        "  requested precision: {} decimal digits; working precision: {} bits",
        request.precision_digits, cfg.precision_bits
    );
    println!(
        "  root acquisition: {}; requested ordinals {}..={} ({} roots)",
        request.root_acquisition.as_str(),
        request.first_zero_index,
        last_zero_index,
        request.zero_count
    );
    println!("  parity policy: {}", request.parity_policy.as_str());
    println!(
        "  eigenstate solver: {}",
        request.eigenstate_solver.as_str()
    );
    println!("  research capture: {}", request.research_capture.as_str());
    println!(
        "  reference dataset: {} (sha256={})",
        dataset.resource_id,
        &dataset.content_sha256[..12]
    );
    let comparison_semantics = match request.root_acquisition {
        RootAcquisition::Seeded => "reference-seeded-indexed-refinement",
        RootAcquisition::Independent => "independent-positive-ordinal-comparison",
    };
    if request.root_acquisition == RootAcquisition::Independent {
        println!(
            "  comparison: independently discovered positive roots are compared by ordinal \
             position; this is not a displacement classification"
        );
    }
    println!(
        "  runtime parallelism: Rayon workers={}, available CPUs={}",
        rayon_workers, available_cpus
    );

    let arithmetic_reference =
        preparation::arithmetic_reference_selection(request.n_modes, journal)?;
    let mut target_binding = preparation::target_binding()?;
    if let Some(selection) = &arithmetic_reference {
        target_binding["arithmetic_reference_dataset"] = selection.binding();
    }
    let managed = xc_cache::ManagedArtifactCacheSession::from_environment()?
        .context("managed cache is required to retain primary source identities")?;
    let cache = managed.context();
    let target = ccm::window::ZeroTarget::IndexRange {
        first: request.first_zero_index,
        last: last_zero_index,
    };
    let mut run = match request.root_acquisition {
        RootAcquisition::Seeded => ccm::hp::capture_run::RetainedCcmRun::seeded(
            &params,
            &cfg,
            request.first_zero_index,
            &zero_seeds,
            &dataset,
            &cache,
        )?,
        RootAcquisition::Independent => ccm::hp::capture_run::RetainedCcmRun::independent(
            &params,
            &cfg,
            &target,
            ccm::hp::IndependentRootDiscoveryOptions::advanced(false, true),
            &cache,
        )?,
    };
    journal.save(
        "primary.json",
        &ccm::hp::PortableHighPrecResult::from_runtime(run.primary())?,
    )?;
    journal.save("primary-sources.json", &run.primary_sources())?;
    if let Some(selection) = arithmetic_reference {
        selection.install(&mut run)?;
    }
    let hp_result = run.primary();
    let ground_index_admission = reported_ground_admission(
        request.ground_index_policy,
        hp_result.ground_index_admission.as_ref(),
    )?;
    let selected_state_scope = if ground_index_admission["established"] == true {
        "proven_ground_state_of_exact_stored_matrix_in_requested_subspace"
    } else {
        println!(
            "[UNASSESSED] selected-state ground index: {}",
            ground_index_admission["reason"]
        );
        "selected_stored_state_only_ground_index_not_established"
    };
    if hp_result.first_positive_root_index != request.first_zero_index {
        anyhow::bail!(
            "toolkit returned first root index {}, expected {}",
            hp_result.first_positive_root_index,
            request.first_zero_index
        );
    }

    println!(
        "  solved in {:.3}s, selected stored eigenvalue = {}",
        hp_result.elapsed_seconds,
        xc_numerics::fmt::display_hp(&hp_result.weil_min_eigenvalue, 8)
    );
    println!();
    println!(
        "{:>6}  {:>11}  {:>22}  {:>22}  {:>14}  {:>7}",
        "zero", "status", "computed root", "reference root", "match digits", "iters"
    );
    println!("{}", "-".repeat(96));

    let cmp_prec = hp_result.precision_bits.saturating_mul(2);
    let mut roots = Vec::with_capacity(request.zero_count);
    for (offset, reference_string) in reference_strings.iter().enumerate() {
        let reference_index = request.first_zero_index + offset;
        let outcome = hp_result.eigenvalues_pos.get(offset).ok_or_else(|| {
            anyhow::anyhow!(
                "toolkit returned only {} roots for a {}-root request",
                hp_result.eigenvalues_pos.len(),
                request.zero_count
            )
        })?;
        let measurement = root_measurement(
            reference_index,
            outcome,
            reference_string.as_str(),
            cmp_prec,
        )?;

        let computed_display = outcome
            .value()
            .map(|value| xc_numerics::fmt::display_hp(value, request.display_digits))
            .unwrap_or_else(|| "N/A".to_owned());
        let reference_value = Float::with_val(
            cmp_prec,
            Float::parse(reference_string.as_str())
                .map_err(|error| anyhow::anyhow!("invalid reference zero: {error}"))?,
        );
        let matching_display = measurement
            .matching_digits
            .as_ref()
            .map(|value| {
                Float::parse(value)
                    .map(|parsed| {
                        xc_numerics::fmt::display_hp(&Float::with_val(cmp_prec, parsed), 8)
                    })
                    .unwrap_or_else(|_| value.clone())
            })
            .unwrap_or_else(|| "N/A".to_owned());
        println!(
            "{:>6}  {:>11}  {:>22}  {:>22}  {:>14}  {:>7}",
            reference_index,
            measurement.status,
            computed_display,
            xc_numerics::fmt::display_hp(&reference_value, request.display_digits),
            matching_display,
            measurement.iterations
        );
        roots.push(measurement);
    }

    let mut report = MeasurementReport {
        schema_version: 1,
        application: "ccm-convergence-rate",
        application_version: env!("CARGO_PKG_VERSION"),
        toolkit_version: xc_cache::current_toolkit_version()?.to_string(),
        build_info: build_info(),
        journal: journal.directory.clone(),
        capture_complete: false,
        all_requested_capture_complete: false,
        applicable_capture_complete: false,
        precision_control_capture: request.precision_control_capture,
        capture_applicability: serde_json::json!({"status":"not_run"}),
        capture_applicability_artifact: None,
        capture_receipt: serde_json::json!({"status":"not_run"}),
        primary_sources: run.primary_sources(),
        root_acquisition: request.root_acquisition,
        parity_policy: request.parity_policy,
        eigenstate_solver: request.eigenstate_solver,
        ground_index_policy: request.ground_index_policy,
        ground_index_admission,
        stored_state_resolution: serde_json::to_value(&hp_result.stored_state_resolution)?,
        selected_state_scope,
        research_capture: request.research_capture,
        research_sector_eigenpairs: request.research_sector_eigenpairs,
        comparison_semantics,
        lambda_sq: request.lambda_sq,
        n_modes: request.n_modes,
        matrix_size: params.matrix_size(),
        precision_digits_requested: request.precision_digits,
        precision_bits_working: hp_result.precision_bits,
        first_zero_index: request.first_zero_index,
        zero_count_requested: request.zero_count,
        zero_count_returned: hp_result.eigenvalues_pos.len(),
        reference_dataset: ReferenceDatasetReport {
            resource_id: dataset.resource_id,
            content_sha256: dataset.content_sha256,
            record_count: dataset.record_count,
            decimal_digits: dataset.decimal_digits,
        },
        rayon_workers,
        available_cpus,
        elapsed_seconds: hp_result.elapsed_seconds,
        weil_min_eigenvalue: hp_result.weil_min_eigenvalue.to_string_radix(10, None),
        selected_eigenvalue: hp_result.weil_min_eigenvalue.to_string_radix(10, None),
        roots,
    };

    journal.save("primary-measurements.json", &report)?;
    // Operational paths/timings stay in the journal, never in mathematical
    // artifact identity or payload. Repeating a configuration must not create
    // different evidence merely because it ran in another directory.
    let measurement_payload = retained_measurement_payload(&report)?;
    let measurement_record = xc_cache::capture_and_persist(
        &serde_json::json!({"semantics":"paper3-indexed-root-measurements-v1",
            "implementation_digest":journal::implementation_digest(),
            "configuration":{
                "lambda_squared":request.lambda_sq,"n_modes":request.n_modes,
                "precision_digits":request.precision_digits,"first_zero_index":request.first_zero_index,
                "zero_count":request.zero_count,"root_acquisition":request.root_acquisition,
                "parity_policy":request.parity_policy,"eigenstate_solver":request.eigenstate_solver,
                "ground_index_policy":request.ground_index_policy
            },"sources":report.primary_sources}),
        vec!["paper3_measurements".into()],
        |_| {
            xc_cache::CapturedDiagnostic::new(&measurement_payload, report.primary_sources.clone())
                .map_err(xc_cache::CaptureFailure::failed)
        },
        &cache,
    )?;
    journal.save("measurement-receipt.json", &measurement_record.value)?;
    let measurement_manifest = measurement_record
        .produced_manifest
        .as_ref()
        .or(measurement_record.reused_manifest.as_ref())
        .context("retained measurement manifest unavailable")?;
    journal.save("measurement-manifest.json", measurement_manifest)?;
    anyhow::ensure!(
        measurement_record.value.receipt.is_complete(),
        "measurement retention incomplete"
    );
    let mut checks = Vec::new();
    let capture_result = capture::capture(
        &mut run,
        &params,
        &cfg,
        request,
        &cache,
        journal,
        &mut checks,
        &target_binding,
    );
    report.capture_complete = capture_result.as_ref().copied().unwrap_or(false);
    report.capture_receipt = if journal.directory.join("capture.json").exists() {
        serde_json::from_slice(&fs::read(journal.directory.join("capture.json"))?)?
    } else {
        serde_json::json!({"status": if report.capture_complete {"completed"} else {"incomplete"},
            "reason": capture_result.as_ref().err().map(|e| format!("{e:#}"))})
    };
    report.all_requested_capture_complete = report.capture_complete;
    report.capture_applicability = capture::assess_applicability(
        request,
        cfg.precision_bits,
        &report.ground_index_admission,
        &report.stored_state_resolution,
        &report.selected_eigenvalue,
        &report.primary_sources,
        &report.capture_receipt,
        report.capture_complete,
        journal,
    )?;
    report.applicable_capture_complete = report.capture_applicability
        ["applicable_capture_complete"]
        .as_bool()
        .unwrap_or(false);
    journal.save("capture-applicability.json", &report.capture_applicability)?;
    if request.precision_control_capture {
        let raw_manifest: xc_cache::ArtifactManifest =
            serde_json::from_slice(&fs::read(journal.directory.join("capture-manifest.json"))?)?;
        let mut dependencies = report.primary_sources.clone();
        dependencies.extend([raw_manifest.clone(), measurement_manifest.clone()]);
        let assessment_payload = serde_json::json!({
            "schema_version":1,"semantics":capture::APPLICABILITY_EVIDENCE,
            "assessment":report.capture_applicability,"raw_capture":report.capture_receipt,
            "measurement":measurement_payload,
            "raw_capture_manifest":raw_manifest,"measurement_manifest":measurement_manifest
        });
        let assessment_record = xc_cache::capture_and_persist(
            &serde_json::json!({"policy":capture::APPLICABILITY_POLICY,
                "configuration":report.capture_applicability["configuration"],
                "implementation_digest":journal::implementation_digest(),
                "raw_capture":raw_manifest.key,"raw_capture_content_digest":raw_manifest.content_digest,
                "measurement":measurement_manifest.key,
                "measurement_content_digest":measurement_manifest.content_digest}),
            vec!["paper3_capture_applicability".into()],
            |_| {
                xc_cache::CapturedDiagnostic::new(&assessment_payload, dependencies.clone())
                    .map_err(xc_cache::CaptureFailure::failed)
            },
            &cache,
        )?;
        anyhow::ensure!(
            assessment_record.value.receipt.is_complete(),
            "precision-control applicability evidence retention incomplete"
        );
        let manifest = assessment_record
            .produced_manifest
            .as_ref()
            .or(assessment_record.reused_manifest.as_ref())
            .context("precision-control applicability manifest unavailable")?;
        let payload = xc_core::finite_json::to_vec(&assessment_record.value)?;
        anyhow::ensure!(
            xc_cache::ContentDigest::sha256(&payload) == manifest.content_digest,
            "precision-control applicability payload does not match its retained manifest"
        );
        journal.save_bytes("capture-applicability-record.json", &payload)?;
        journal.save("capture-applicability-artifact.json", manifest)?;
        report.capture_applicability_artifact = Some(manifest.clone());
    }
    let roots_complete = report.zero_count_returned == report.zero_count_requested
        && report.roots.iter().all(|row| row.status == "converged");
    journal.save("summary.json", &serde_json::json!({
        "roots_complete":roots_complete,"capture_complete":report.capture_complete,
        "all_requested_capture_complete":report.all_requested_capture_complete,
        "applicable_capture_complete":report.applicable_capture_complete,
        "capture_applicability":report.capture_applicability,
        "ground_index_admission":report.ground_index_admission,"selected_state_scope":report.selected_state_scope,
        "checks":checks,"scope":"finite indexed measurements; mathematical qualifications remain in each artifact"}))?;
    journal.save("measurements.json", &report)?;
    if let Some(path) = &request.json_output {
        write_json_atomic(&path, &report)?;
        println!("\nStructured result: {}", path.display());
    }
    capture_result?;
    anyhow::ensure!(roots_complete, "one or more requested roots are not converged; retained measurements preserve solver outcomes");
    anyhow::ensure!(
        report.applicable_capture_complete,
        "requested research capture incomplete; inspect retained receipt"
    );
    Ok(())
}

#[cfg(feature = "hp")]
fn reported_ground_admission(
    policy: GroundIndexPolicy,
    outcome: Option<&ccm::hp::CcmGroundIndexAdmission>,
) -> Result<serde_json::Value> {
    match (policy, outcome) {
        (GroundIndexPolicy::Require, None) => Ok(serde_json::json!({"established":true})),
        (GroundIndexPolicy::RecordOutcome, Some(value))
            if (value.established && value.reason.is_none())
                || (!value.established
                    && value
                        .reason
                        .as_deref()
                        .is_some_and(|r| !r.trim().is_empty())) =>
        {
            Ok(serde_json::to_value(value)?)
        }
        _ => anyhow::bail!("ground-index outcome does not match the explicit admission policy"),
    }
}

#[cfg(feature = "hp")]
fn retained_measurement_payload(report: &MeasurementReport) -> Result<serde_json::Value> {
    let mut value = serde_json::to_value(report)?;
    let object = value
        .as_object_mut()
        .expect("measurement report serializes as an object");
    for field in [
        "journal",
        "elapsed_seconds",
        "rayon_workers",
        "available_cpus",
        "capture_complete",
        "all_requested_capture_complete",
        "applicable_capture_complete",
        "precision_control_capture",
        "capture_applicability",
        "capture_applicability_artifact",
        "capture_receipt",
        "research_capture",
        "research_sector_eigenpairs",
    ] {
        object.remove(field);
    }
    Ok(value)
}

#[cfg(feature = "hp")]
fn root_measurement(
    reference_index: usize,
    outcome: &ccm::hp::EigenvalueResult,
    reference_string: &str,
    precision_bits: u32,
) -> Result<RootMeasurement> {
    use rug::Float;

    let (status, refinement, failure_iterations, failure_reason) = match outcome {
        ccm::hp::EigenvalueResult::Converged(result) => ("converged", Some(result), 0, None),
        ccm::hp::EigenvalueResult::Stagnated(result) => ("stagnated", Some(result), 0, None),
        ccm::hp::EigenvalueResult::Approximate(result) => ("approximate", Some(result), 0, None),
        ccm::hp::EigenvalueResult::Failed { iterations, reason } => {
            ("failed", None, *iterations, Some(reason.clone()))
        }
    };

    let Some(refinement) = refinement else {
        return Ok(RootMeasurement {
            reference_index,
            status,
            computed_value: None,
            reference_value: reference_string.to_owned(),
            absolute_error: None,
            relative_error: None,
            matching_digits: None,
            matching_digits_f64: None,
            iterations: failure_iterations,
            achieved_decimal_digits: None,
            final_correction: None,
            residual: None,
            failure_reason,
        });
    };

    let computed = Float::with_val(precision_bits, &refinement.value);
    let reference = Float::with_val(
        precision_bits,
        Float::parse(reference_string)
            .map_err(|error| anyhow::anyhow!("invalid reference zero: {error}"))?,
    );
    let mut absolute_error = Float::with_val(precision_bits, &computed);
    absolute_error -= &reference;
    absolute_error.abs_mut();
    let mut relative_error = Float::with_val(precision_bits, &absolute_error);
    relative_error /= Float::with_val(precision_bits, &reference).abs();
    let matching_digits = xc_numerics::fmt::matching_digits(&computed, &reference);

    Ok(RootMeasurement {
        reference_index,
        status,
        computed_value: Some(computed.to_string_radix(10, None)),
        reference_value: reference_string.to_owned(),
        absolute_error: Some(absolute_error.to_string_radix(10, None)),
        relative_error: Some(relative_error.to_string_radix(10, None)),
        matching_digits: Some(matching_digits.to_string_radix(10, None)),
        matching_digits_f64: Some(matching_digits.to_f64()),
        iterations: refinement.diagnostics.iterations,
        achieved_decimal_digits: Some(
            refinement
                .diagnostics
                .achieved_decimal_digits
                .to_string_radix(10, None),
        ),
        final_correction: Some(
            refinement
                .diagnostics
                .final_correction
                .to_string_radix(10, None),
        ),
        residual: Some(refinement.diagnostics.residual.to_string_radix(10, None)),
        failure_reason: None,
    })
}

#[cfg(feature = "hp")]
fn run_measure_evenness(
    lambda_sq: u64,
    n_modes: usize,
    precision_digits: u32,
    display_digits: usize,
    eigenstate_solver: EigenstateSolver,
    ground_index_policy: GroundIndexPolicy,
    capture_output: PathBuf,
    json_output: Option<PathBuf>,
) -> Result<()> {
    let journal = journal::Journal::start(
        &capture_output,
        &serde_json::json!({
            "command":"measure-evenness", "lambda_sq":lambda_sq, "n_modes":n_modes,
            "precision_digits":precision_digits, "display_digits":display_digits,
            "eigenstate_solver":eigenstate_solver,"ground_index_policy":ground_index_policy,
            "capture_scope":"stored-source evenness only"
        }),
    )?;
    let result = run_measure_evenness_inner(
        lambda_sq,
        n_modes,
        precision_digits,
        display_digits,
        eigenstate_solver,
        ground_index_policy,
        json_output,
        &journal,
    );
    if let Err(error) = &result {
        journal.save(
            "failure.json",
            &serde_json::json!({"error":format!("{error:#}"),
            "measurements_saved":journal.directory.join("measurements.json").exists()}),
        )?;
    }
    result
}

#[cfg(feature = "hp")]
fn run_measure_evenness_inner(
    lambda_sq: u64,
    n_modes: usize,
    precision_digits: u32,
    display_digits: usize,
    eigenstate_solver: EigenstateSolver,
    ground_index_policy: GroundIndexPolicy,
    json_output: Option<PathBuf>,
    journal: &journal::Journal,
) -> Result<()> {
    use xc_numerics::fmt::{display_hp, sign_of};

    if lambda_sq < 2 {
        anyhow::bail!("lambda-sq must be at least 2 (got {lambda_sq})");
    }
    if n_modes == 0 || precision_digits == 0 || display_digits == 0 {
        anyhow::bail!("n-modes, precision-digits, and display-digits must be positive");
    }
    let params = CcmParams::from_lambda_sq_integer(lambda_sq, n_modes);
    let mut cfg = high_prec_config(
        precision_digits,
        ParityPolicy::EvenSector,
        eigenstate_solver,
        1,
    );
    cfg.ground_index_policy = match ground_index_policy {
        GroundIndexPolicy::Require => ccm::hp::CcmGroundIndexPolicy::Require,
        GroundIndexPolicy::RecordOutcome => ccm::hp::CcmGroundIndexPolicy::RecordOutcome,
    };
    println!(
        "Measuring evenness: lambda^2={}, N={}, requested precision={} digits ({} working bits)",
        lambda_sq, n_modes, precision_digits, cfg.precision_bits
    );
    println!("  eigenstate solver: {}", eigenstate_solver.as_str());
    let managed = xc_cache::ManagedArtifactCacheSession::from_environment()?
        .context("managed cache required for evenness source retention")?;
    let cache = managed.context();
    let (result, primary_sources, source_state_resolutions) =
        journal::source_observer::with_sources(&cache, ground_index_policy, |observed| {
            ccm::hp::measure_evenness_via_cache(&params, &cfg, observed)
        })?;
    journal.save("primary-sources.json", &primary_sources)?;
    journal.save("source-state-resolutions.json", &source_state_resolutions)?;
    let all_established = source_state_resolutions
        .iter()
        .all(|value| value["ground_index_admission"]["established"] == true);
    let ground_index_admission = if all_established {
        serde_json::json!({"established":true})
    } else {
        serde_json::json!({"established":false,"reason":"one or more selected stored states lack a proven ground index; inspect source_state_resolutions"})
    };
    let selected_state_scope = if all_established {
        "proven_ground_states_of_exact_stored_matrix_in_each_requested_subspace"
    } else {
        "selected_stored_states_only_ground_index_not_established"
    };
    if !all_established {
        println!("[UNASSESSED] evenness is measured for selected stored states; inspect source-state-resolutions.json");
    }
    let natural_sign = sign_of(&result.natural_eigenvalue).as_str().to_owned();
    let forced_even_sign = sign_of(&result.forced_eigenvalue).as_str().to_owned();
    println!(
        "  ||xi - gamma(xi)|| / ||xi|| = {}",
        display_hp(&result.evenness_deviation, display_digits)
    );
    println!(
        "  natural selected eigenvalue     = {}",
        display_hp(&result.natural_eigenvalue, display_digits)
    );
    println!(
        "  forced-even selected eigenvalue = {}",
        display_hp(&result.forced_eigenvalue, display_digits)
    );
    println!(
        "  natural sign = {}, forced-even sign = {}",
        natural_sign, forced_even_sign
    );

    let report = EvennessReport {
        schema_version: 1,
        application: "ccm-convergence-rate",
        application_version: env!("CARGO_PKG_VERSION"),
        toolkit_version: xc_cache::current_toolkit_version()?.to_string(),
        build_info: build_info(),
        capture_complete: None,
        capture_scope:
            "stored-source evenness only; Ultra capture belongs to the paired root measurement",
        journal: journal.directory.clone(),
        primary_sources,
        claim_scope: serde_json::to_value(result.claim_scope)?,
        assembly_error_bound: result
            .assembly_error_bound
            .as_ref()
            .map(|x| x.to_string_radix(10, None)),
        eigenstate_solver,
        ground_index_policy,
        ground_index_admission,
        source_state_resolutions,
        selected_state_scope,
        lambda_sq,
        n_modes,
        matrix_size: params.matrix_size(),
        precision_digits_requested: precision_digits,
        precision_bits_working: result.natural_eigenvalue.prec(),
        evenness_deviation: result.evenness_deviation.to_string_radix(10, None),
        natural_eigenvalue: result.natural_eigenvalue.to_string_radix(10, None),
        forced_even_eigenvalue: result.forced_eigenvalue.to_string_radix(10, None),
        natural_sign,
        forced_even_sign,
    };
    journal.save("measurements.json", &report)?;
    journal.save(
        "summary.json",
        &serde_json::json!({"execution_integrity":"PASS",
        "capture_complete":null,"scope":report.capture_scope,
        "ground_index_admission":report.ground_index_admission,"selected_state_scope":report.selected_state_scope}),
    )?;
    if let Some(path) = json_output {
        write_json_atomic(&path, &report)?;
        println!("Structured result: {}", path.display());
    }
    Ok(())
}

#[cfg(not(feature = "hp"))]
fn run_measure_evenness(
    _lambda_sq: u64,
    _n_modes: usize,
    _precision_digits: u32,
    _display_digits: usize,
    _eigenstate_solver: EigenstateSolver,
    _ground_index_policy: GroundIndexPolicy,
    _capture_output: PathBuf,
    _json_output: Option<PathBuf>,
) -> Result<()> {
    anyhow::bail!(
        "High-precision evenness measurement requires --features hp.\n\
         Build with: cargo build --release --features hp --locked"
    )
}

#[cfg(not(feature = "hp"))]
fn run_measure(_request: MeasureRequest) -> Result<()> {
    anyhow::bail!(
        "High-precision measurement requires --features hp.\n\
         Build with: cargo build --release --features hp --locked"
    )
}

fn finalize_publication() -> Result<()> {
    let config = xc_cache::ManagedArtifactCacheConfig::from_environment()?
        .context("publication requires explicit managed cache configuration")?;
    anyhow::ensure!(config.profile == xc_cache::ManagedRunProfile::Author
        && config.execute_remote_mutations
        && config.publication_target != xc_core::PublicationTarget::None
        && config.staging_root.is_some() && config.output_validation.is_none(),
        "publication requires an author staging root, execution, a destination, and no output validation");
    let root = config.staging_root.as_ref().expect("checked staging root");
    anyhow::ensure!(
        fs::symlink_metadata(root)?.file_type().is_dir(),
        "publication requires an ordinary staging directory"
    );
    let managed = xc_cache::ManagedArtifactCacheSession::new_with_resources(
        config,
        xc_cache::managed_resource_policy_from_environment()?,
    )?;
    let path = managed
        .retry_retained_publication()?
        .context("publication did not finalize a retained inventory")?;
    println!("Publication inventory finalized: {}", path.display());
    Ok(())
}

fn write_json_atomic(path: &Path, value: &impl Serialize) -> Result<()> {
    if let Some(parent) = path
        .parent()
        .filter(|parent| !parent.as_os_str().is_empty())
    {
        fs::create_dir_all(parent)
            .with_context(|| format!("failed to create {}", parent.display()))?;
    }
    let temporary = path.with_extension(format!("json.{}.tmp", std::process::id()));
    let bytes = serde_json::to_vec_pretty(value)?;
    fs::write(&temporary, bytes)
        .with_context(|| format!("failed to write {}", temporary.display()))?;
    #[cfg(windows)]
    if path.exists() {
        fs::remove_file(path).with_context(|| format!("failed to replace {}", path.display()))?;
    }
    fs::rename(&temporary, path)
        .with_context(|| format!("failed to replace {}", path.display()))?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use clap::Parser;

    #[test]
    fn measure_defaults_to_modern_policies() {
        let cli = Cli::try_parse_from(["ccm-convergence-rate", "measure"]).unwrap();
        match cli.command {
            Command::Measure {
                first_zero_index,
                zero_count,
                root_acquisition,
                parity_policy,
                eigenstate_solver,
                ground_index_policy,
                precision_control_capture,
                research_capture,
                capture_sector_gap_certificate,
                parallel_gl_roots,
                ..
            } => {
                assert_eq!(first_zero_index, 1);
                assert_eq!(zero_count, 5);
                assert_eq!(root_acquisition, RootAcquisition::Seeded);
                assert_eq!(parity_policy, ParityPolicy::EvenSector);
                assert_eq!(eigenstate_solver, EigenstateSolver::Auto);
                assert_eq!(ground_index_policy, GroundIndexPolicy::Require);
                assert!(!precision_control_capture);
                assert_eq!(research_capture, ResearchCapture::Claim);
                assert!(!capture_sector_gap_certificate);
                assert!(!parallel_gl_roots);
            }
            _ => panic!("expected measure command"),
        }
    }

    #[test]
    fn arbitrary_reference_window_is_parseable() {
        let cli = Cli::try_parse_from([
            "ccm-convergence-rate",
            "measure",
            "--first-zero-index",
            "21",
            "--zero-count",
            "12",
            "--root-acquisition",
            "independent",
            "--parity-policy",
            "natural",
            "--eigenstate-solver",
            "shift-invert-krylov",
            "--research-capture",
            "maximum",
        ])
        .unwrap();
        match cli.command {
            Command::Measure {
                first_zero_index,
                zero_count,
                root_acquisition,
                parity_policy,
                eigenstate_solver,
                research_capture,
                ..
            } => {
                assert_eq!(first_zero_index, 21);
                assert_eq!(zero_count, 12);
                assert_eq!(root_acquisition, RootAcquisition::Independent);
                assert_eq!(parity_policy, ParityPolicy::Natural);
                assert_eq!(eigenstate_solver, EigenstateSolver::ShiftInvertKrylov);
                assert_eq!(research_capture, ResearchCapture::Maximum);
            }
            _ => panic!("expected measure command"),
        }
    }

    #[test]
    fn build_identity_is_bound_to_locked_toolkit_and_features() {
        let info = build_info();
        assert_eq!(info["toolkit_revision"], TOOLKIT_REVISION);
        assert_eq!(info["hp_enabled"], cfg!(feature = "hp"));
        assert_eq!(info["complete_positive_roots"], cfg!(feature = "arb"));
        let digest = info["implementation_digest"].as_str().unwrap();
        assert_eq!(digest.len(), 64);
        assert!(digest.bytes().all(|b| b.is_ascii_hexdigit()));
        assert!(include_str!("../Cargo.lock").contains(TOOLKIT_REVISION));
        assert!(!include_str!("../Cargo.lock").contains("tag=v0.13.5"));
    }

    #[cfg(feature = "hp")]
    #[test]
    fn recorded_ground_outcome_cannot_be_promoted_to_a_proof() {
        let outcome = ccm::hp::CcmGroundIndexAdmission {
            established: false,
            reason: Some("a lower stored eigenvalue was proven".into()),
        };
        let recorded =
            reported_ground_admission(GroundIndexPolicy::RecordOutcome, Some(&outcome)).unwrap();
        assert_eq!(recorded["established"], false);
        assert_eq!(recorded["reason"], "a lower stored eigenvalue was proven");
        assert!(reported_ground_admission(GroundIndexPolicy::Require, Some(&outcome)).is_err());
        assert!(reported_ground_admission(GroundIndexPolicy::RecordOutcome, None).is_err());
        assert_eq!(
            reported_ground_admission(GroundIndexPolicy::Require, None).unwrap()["established"],
            true
        );
    }

    #[test]
    fn selected_state_policy_requires_an_explicit_cli_choice() {
        for command in ["measure", "measure-evenness"] {
            let cli = Cli::try_parse_from([
                "ccm-convergence-rate",
                command,
                "--lambda-sq",
                "13",
                "--n-modes",
                "80",
                "--precision-digits",
                "30",
                "--ground-index-policy",
                "record-outcome",
            ])
            .unwrap();
            let policy = match cli.command {
                Command::Measure {
                    ground_index_policy,
                    ..
                }
                | Command::MeasureEvenness {
                    ground_index_policy,
                    ..
                } => ground_index_policy,
                _ => unreachable!(),
            };
            assert_eq!(policy, GroundIndexPolicy::RecordOutcome);
        }
    }

    #[cfg(feature = "hp")]
    #[test]
    fn failed_root_is_preserved_without_an_accuracy_value() {
        let row = root_measurement(
            7,
            &ccm::hp::EigenvalueResult::Failed {
                iterations: 12,
                reason: "explicit finite solver refusal".into(),
            },
            "40.918719012147495187398126914633254395726165962777",
            256,
        )
        .unwrap();
        assert_eq!(row.reference_index, 7);
        assert_eq!(row.status, "failed");
        assert_eq!(row.iterations, 12);
        assert!(row.computed_value.is_none());
        assert!(row.matching_digits.is_none());
        assert_eq!(
            row.failure_reason.as_deref(),
            Some("explicit finite solver refusal")
        );
    }

    #[test]
    fn ultra_is_explicit_and_keeps_sector_gap_separate() {
        let cli = Cli::try_parse_from([
            "ccm-convergence-rate",
            "measure",
            "--research-capture",
            "ultra",
            "--capture-output",
            "journals",
            "--capture-maximum-stream-scalar-bytes",
            "1024",
        ])
        .unwrap();
        match cli.command {
            Command::Measure {
                research_capture,
                capture_sector_gap_certificate,
                capture_maximum_stream_scalar_bytes,
                ..
            } => {
                assert_eq!(research_capture, ResearchCapture::Ultra);
                assert!(!capture_sector_gap_certificate);
                assert_eq!(capture_maximum_stream_scalar_bytes, 1024);
            }
            _ => panic!("expected measure command"),
        }
    }
}
