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
}

impl ResearchCapture {
    fn as_str(self) -> &'static str {
        match self {
            Self::Claim => "claim",
            Self::Research => "research",
            Self::Gap => "gap",
            Self::Maximum => "maximum",
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

        /// Supplemental artifact capture level.
        #[arg(long, value_enum, default_value_t = ResearchCapture::Claim)]
        research_capture: ResearchCapture,

        /// Low eigenpairs retained per parity sector in maximum capture.
        #[arg(long, default_value_t = 8)]
        research_sector_eigenpairs: usize,

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
            research_capture,
            research_sector_eigenpairs,
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
            research_capture,
            research_sector_eigenpairs,
            json_output,
        }),
        Command::MeasureEvenness {
            lambda_sq,
            n_modes,
            precision_digits,
            display_digits,
            eigenstate_solver,
            json_output,
        } => run_measure_evenness(
            lambda_sq,
            n_modes,
            precision_digits,
            display_digits,
            eigenstate_solver,
            json_output,
        ),
        Command::FinalizePublication => finalize_publication(),
    }
}

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
    research_capture: ResearchCapture,
    research_sector_eigenpairs: usize,
    json_output: Option<PathBuf>,
}

#[derive(Serialize)]
struct MeasurementReport {
    schema_version: u32,
    application: &'static str,
    application_version: &'static str,
    toolkit_version: String,
    root_acquisition: RootAcquisition,
    parity_policy: ParityPolicy,
    eigenstate_solver: EigenstateSolver,
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
    eigenstate_solver: EigenstateSolver,
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
    let last_zero_index = request
        .first_zero_index
        .checked_add(request.zero_count - 1)
        .context("requested zero window overflows usize")?;

    let params = CcmParams::from_lambda_sq_integer(request.lambda_sq, request.n_modes);
    let prime_powers = ccm::prime_powers_up_to(params.lambda_sq_int());
    let cfg = high_prec_config(
        request.precision_digits,
        request.parity_policy,
        request.eigenstate_solver,
        request.zero_count,
    );
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

    let sector_count = match request.research_capture {
        ResearchCapture::Claim | ResearchCapture::Research => None,
        ResearchCapture::Gap => Some(2.min(request.n_modes)),
        ResearchCapture::Maximum => Some(request.research_sector_eigenpairs.min(request.n_modes)),
    };
    if sector_count == Some(0) {
        anyhow::bail!("sector research capture requires N >= 1");
    }
    let sector_analysis = sector_count.map(|count| match request.research_capture {
        ResearchCapture::Maximum => ccm::hp::CcmSectorAnalysisOptions::maximum(count),
        _ => ccm::hp::CcmSectorAnalysisOptions::selected(count),
    });
    let capture_options = ccm::hp::CcmResearchCaptureOptions {
        capture_evenness: sector_analysis.is_some(),
        sector_analysis,
        root_certification: None,
    };
    let capture_requested = !matches!(
        request.research_capture,
        ResearchCapture::Claim | ResearchCapture::Research
    );
    let target = ccm::window::ZeroTarget::IndexRange {
        first: request.first_zero_index,
        last: last_zero_index,
    };
    let hp_result = match (request.root_acquisition, capture_requested) {
        (RootAcquisition::Seeded, false) => ccm::hp::run_indexed_seeded(
            &params,
            &cfg,
            request.first_zero_index,
            &zero_seeds,
            &dataset,
        )?,
        (RootAcquisition::Seeded, true) => {
            ccm::hp::run_indexed_seeded_with_research_capture(
                &params,
                &cfg,
                request.first_zero_index,
                &zero_seeds,
                &dataset,
                capture_options,
            )?
            .primary
        }
        (RootAcquisition::Independent, false) => ccm::hp::run_independent(&params, &cfg, &target)?,
        (RootAcquisition::Independent, true) => {
            ccm::hp::run_independent_with_research_capture(&params, &cfg, &target, capture_options)?
                .primary
        }
    };
    if hp_result.first_positive_root_index != request.first_zero_index {
        anyhow::bail!(
            "toolkit returned first root index {}, expected {}",
            hp_result.first_positive_root_index,
            request.first_zero_index
        );
    }

    println!(
        "  solved in {:.3}s, epsilon_N = {}",
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
    for offset in 0..request.zero_count {
        let reference_index = request.first_zero_index + offset;
        let reference_string = reference_strings[offset].clone();
        let outcome = hp_result.eigenvalues_pos.get(offset).ok_or_else(|| {
            anyhow::anyhow!(
                "toolkit returned only {} roots for a {}-root request",
                hp_result.eigenvalues_pos.len(),
                request.zero_count
            )
        })?;
        let measurement = root_measurement(reference_index, outcome, &reference_string, cmp_prec)?;

        let computed_display = outcome
            .value()
            .map(|value| xc_numerics::fmt::display_hp(value, request.display_digits))
            .unwrap_or_else(|| "N/A".to_owned());
        let reference_value = Float::with_val(
            cmp_prec,
            Float::parse(&reference_string)
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

    let report = MeasurementReport {
        schema_version: 1,
        application: "ccm-convergence-rate",
        application_version: env!("CARGO_PKG_VERSION"),
        toolkit_version: xc_cache::current_toolkit_version()?.to_string(),
        root_acquisition: request.root_acquisition,
        parity_policy: request.parity_policy,
        eigenstate_solver: request.eigenstate_solver,
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
        roots,
    };

    if let Some(path) = request.json_output {
        write_json_atomic(&path, &report)?;
        println!("\nStructured result: {}", path.display());
    }
    Ok(())
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
    json_output: Option<PathBuf>,
) -> Result<()> {
    use xc_numerics::fmt::{display_hp, sign_of};

    if lambda_sq < 2 {
        anyhow::bail!("lambda-sq must be at least 2 (got {lambda_sq})");
    }
    if n_modes == 0 || precision_digits == 0 || display_digits == 0 {
        anyhow::bail!("n-modes, precision-digits, and display-digits must be positive");
    }
    let params = CcmParams::from_lambda_sq_integer(lambda_sq, n_modes);
    let cfg = high_prec_config(
        precision_digits,
        ParityPolicy::EvenSector,
        eigenstate_solver,
        1,
    );
    println!(
        "Measuring evenness: lambda^2={}, N={}, requested precision={} digits ({} working bits)",
        lambda_sq, n_modes, precision_digits, cfg.precision_bits
    );
    println!("  eigenstate solver: {}", eigenstate_solver.as_str());
    let result = ccm::hp::measure_evenness(&params, &cfg)?;
    let natural_sign = sign_of(&result.natural_eigenvalue).as_str().to_owned();
    let forced_even_sign = sign_of(&result.forced_eigenvalue).as_str().to_owned();
    println!(
        "  ||xi - gamma(xi)|| / ||xi|| = {}",
        display_hp(&result.evenness_deviation, display_digits)
    );
    println!(
        "  natural smallest eigenvalue     = {}",
        display_hp(&result.natural_eigenvalue, display_digits)
    );
    println!(
        "  forced-even smallest eigenvalue = {}",
        display_hp(&result.forced_eigenvalue, display_digits)
    );
    println!(
        "  natural sign = {}, forced-even sign = {}",
        natural_sign, forced_even_sign
    );

    if let Some(path) = json_output {
        let report = EvennessReport {
            schema_version: 1,
            application: "ccm-convergence-rate",
            application_version: env!("CARGO_PKG_VERSION"),
            toolkit_version: xc_cache::current_toolkit_version()?.to_string(),
            eigenstate_solver,
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
    let Some(managed) =
        xc_cache::ManagedArtifactCacheSession::from_environment().map_err(anyhow::Error::from)?
    else {
        println!("Publication finalization: managed cache session is disabled");
        return Ok(());
    };
    match managed
        .finalize_publication_inventory()
        .map_err(anyhow::Error::from)?
    {
        Some(path) => println!("Publication inventory finalized: {}", path.display()),
        None => println!("Publication finalization: no staging root is configured"),
    }
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
    fn measure_defaults_to_modern_paper_one_policies() {
        let cli = Cli::try_parse_from(["ccm-convergence-rate", "measure"]).unwrap();
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
                assert_eq!(first_zero_index, 1);
                assert_eq!(zero_count, 5);
                assert_eq!(root_acquisition, RootAcquisition::Seeded);
                assert_eq!(parity_policy, ParityPolicy::EvenSector);
                assert_eq!(eigenstate_solver, EigenstateSolver::Auto);
                assert_eq!(research_capture, ResearchCapture::Claim);
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
}
