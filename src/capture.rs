//! Supplemental capture from the retained primary sources; numerical outcomes
//! remain qualified by the Toolkit. Cross-configuration diagnostics are deferred.
use crate::{
    journal::{Check, Journal, Status},
    ResearchCapture,
};
use anyhow::Result;
use serde_json::json;
use std::{collections::BTreeMap, time::Instant};
use xc_cache::{ArtifactCacheContext, CaptureFailure, CapturedDiagnostic};
use xc_spectral::ccm::{
    self,
    capture::{CcmCaptureLevel, CcmCapturePlan, RetainedReductionRequest},
    hp::{capture_run::RetainedCcmRun, HighPrecConfig},
    CcmParams,
};

pub fn preflight(args: &crate::MeasureRequest, precision_bits: u32) -> Result<()> {
    if args.precision_control_capture {
        anyhow::ensure!(
            precision_control_configuration(args),
            "--precision-control-capture is restricted to the fixed C1/C2/C3 Ultra precision controls with recorded ground-index outcomes"
        );
    }
    let level = match args.research_capture {
        ResearchCapture::Claim => CcmCaptureLevel::Claim,
        ResearchCapture::Research => CcmCaptureLevel::Research,
        ResearchCapture::Gap => CcmCaptureLevel::Gap,
        ResearchCapture::Maximum => CcmCaptureLevel::Maximum,
        ResearchCapture::Ultra => CcmCaptureLevel::Ultra,
    };
    let dimension = args
        .n_modes
        .checked_add(1)
        .ok_or_else(|| anyhow::anyhow!("even-sector dimension overflow"))?;
    let plan = CcmCapturePlan::resolve(
        level,
        args.research_sector_eigenpairs.min(args.n_modes),
        dimension,
    )?;
    plan.validate_for_source_precision(precision_bits)?;
    anyhow::ensure!(
        !plan.requires_even_sector || args.parity_policy == crate::ParityPolicy::EvenSector,
        "the selected capture level requires --parity-policy even-sector"
    );
    Ok(())
}
#[allow(clippy::too_many_arguments)]
pub fn capture(
    run: &mut RetainedCcmRun,
    params: &CcmParams,
    cfg: &HighPrecConfig,
    args: &crate::MeasureRequest,
    cache: &ArtifactCacheContext<'_>,
    journal: &Journal,
    checks: &mut Vec<Check>,
    target_binding: &serde_json::Value,
) -> Result<bool> {
    let level = match args.research_capture {
        ResearchCapture::Claim => CcmCaptureLevel::Claim,
        ResearchCapture::Research => CcmCaptureLevel::Research,
        ResearchCapture::Gap => CcmCaptureLevel::Gap,
        ResearchCapture::Maximum => CcmCaptureLevel::Maximum,
        ResearchCapture::Ultra => CcmCaptureLevel::Ultra,
    };
    let plan = CcmCapturePlan::resolve(
        level,
        args.research_sector_eigenpairs.min(params.n_modes),
        params.n_modes + 1,
    )?;
    plan.validate_for_source_precision(cfg.precision_bits)?;
    let mut options = plan.primary_options()?;
    options.sector_gap_certification = args.capture_sector_gap_certificate.then(Default::default);
    if args.certify_roots {
        options.root_certification =
            Some(ccm::hp::CcmRootCertificationOptions::for_decimal_digits(
                ccm::certified_roots::IndependentCcmRootTarget::IndexRange {
                    first: args.first_zero_index,
                    last: args.first_zero_index + args.zero_count - 1,
                },
                args.precision_digits,
            )?);
    }
    if let Some(distance) = &mut options.distance_capture {
        let replacement = ccm::hp::CcmDistanceCaptureOptions::default_convention(4000, 1000);
        distance.rules = replacement.rules;
        distance.profile_steps = replacement.profile_steps;
    }
    let reduction = (level == CcmCaptureLevel::Ultra).then(|| RetainedReductionRequest {
        working_precision_bits: cfg.precision_bits,
        maximum_dimension: 8193,
        relative_tolerance: format!(
            "1e-{}",
            (cfg.precision_bits.saturating_sub(48) as usize * 3 / 10).max(1)
        ),
    });
    let mut requested = plan
        .receipt()?
        .outcomes()
        .keys()
        .filter(|id| !id.starts_with("prefix_"))
        .cloned()
        .collect::<Vec<_>>();
    if plan.capture_prefix_analysis {
        requested.push("prefix_ladder".into());
        requested.extend(
            plan.prefix_checkpoint_dimensions
                .iter()
                .map(|d| format!("prefix_checkpoint_{d}")),
        );
    }
    if reduction.is_some() {
        requested.push("retained_reduction".into());
    }
    if args.capture_sector_gap_certificate {
        requested.push("sector_gap_certificate".into());
    }
    if args.certify_roots {
        requested.push("root_certificate".into());
    }
    let mut skipped = BTreeMap::<String, String>::new();
    for id in ["configuration_comparison", "dimension_precision_budget"] {
        skipped.insert(
            id.into(),
            "deferred until compatible independently computed configurations are available".into(),
        );
    }
    skipped.retain(|id, _| requested.contains(id));
    requested.retain(|id| !skipped.contains_key(id));
    let resolved = json!({"schema_version":1,"capture":plan,"retained_reduction":reduction,"excluded_diagnostics":skipped,"requested_diagnostics":requested,"primary_source_ids":run.primary_sources(),"distance_grid":4000,"profile_steps":1000});
    journal.save("capture-plan.json", &resolved)?;
    let mut preparation_complete = true;
    if level == CcmCaptureLevel::Ultra {
        let preparation =
            crate::preparation::prepare(run, params, cfg, args, cache, journal, target_binding);
        let (status, detail) = match preparation {
            Ok(detail) => (Status::Pass, detail),
            Err(error) => (
                Status::Incomplete,
                json!({"status":"failed","error":format!("{error:#}")}),
            ),
        };
        journal.save("input-preparation-status.json", &detail)?;
        preparation_complete = status == Status::Pass;
        checks.push(Check::new(
            "external input preparation",
            "capture",
            status,
            detail.to_string(),
        ));
    }
    for (id, reason) in &skipped {
        checks.push(Check::new(id, "capture", Status::Unsupported, reason));
    }
    if requested.is_empty() {
        return Ok(preparation_complete);
    }
    let retained = if plan.capture_prefix_analysis
        && requested
            .iter()
            .any(|id| id.starts_with("prefix_") || id == "retained_reduction")
    {
        match run.retained_even_sources(cache) {
            Ok(v) => Some(v),
            Err(error) => {
                journal.save(
                    "retained-source-failure.json",
                    &json!({"error":format!("{error:#}")}),
                )?;
                None
            }
        }
    } else {
        None
    };
    let mut prefix: Option<xc_cache::ArtifactExecutionCacheResult<ccm::prefix::CcmPrefixAnalysis>> =
        None;
    let target_missing = xc_spectral::target::TargetProfileSpec::from_environment()
        .err()
        .map(|e| e.to_string());
    let record = xc_cache::capture_and_persist(
        &resolved,
        requested,
        |id| {
            println!("Capture {id}: started");
            if id == "retained_reduction" {
                let (matrix, _) = retained.as_ref().ok_or_else(|| CaptureFailure::Missing {
                    reason: "retained even matrix unavailable".into(),
                })?;
                let budget = reduction.as_ref().expect("requested reduction");
                if matrix.dimension() > budget.maximum_dimension {
                    return Err(CaptureFailure::Blocked {
                        reason: "retained reduction exceeds explicit dimension budget".into(),
                    });
                }
                let r = ccm::prefix::check_retained_reduction_via_cache(
                    matrix,
                    budget.working_precision_bits,
                    budget.maximum_dimension,
                    &budget.relative_tolerance,
                    cache,
                )
                .map_err(CaptureFailure::failed)?;
                let sources = r
                    .produced_manifest
                    .as_ref()
                    .or(r.reused_manifest.as_ref())
                    .map(|m| vec![m.clone()])
                    .unwrap_or_else(|| vec![matrix.manifest().clone()]);
                return CapturedDiagnostic::new(&r.value, sources).map_err(CaptureFailure::failed);
            }
            if id == "prefix_ladder" {
                let (matrix, pairs) = retained.as_ref().ok_or_else(|| CaptureFailure::Missing {
                    reason: "retained even matrix unavailable".into(),
                })?;
                let r = plan
                    .capture_retained_diagnostics(matrix, pairs, cache)
                    .map_err(CaptureFailure::failed)?
                    .ok_or_else(|| CaptureFailure::failed("prefix disabled"))?;
                let sources = r
                    .produced_manifest
                    .as_ref()
                    .or(r.reused_manifest.as_ref())
                    .map(|m| vec![m.clone()])
                    .unwrap_or_else(|| vec![matrix.manifest().clone()]);
                let diagnostic =
                    CapturedDiagnostic::new(&r.value, sources).map_err(CaptureFailure::failed)?;
                prefix = Some(r);
                return Ok(diagnostic);
            }
            if let Some(dimension) = id.strip_prefix("prefix_checkpoint_") {
                let r = prefix.as_ref().ok_or_else(|| CaptureFailure::Blocked {
                    reason: "prefix ladder unavailable".into(),
                })?;
                let checkpoint = r
                    .value
                    .checkpoints
                    .iter()
                    .find(|c| c.dimension.to_string() == dimension)
                    .ok_or_else(|| CaptureFailure::Missing {
                        reason: "requested checkpoint not reached".into(),
                    })?;
                if checkpoint.eigenpair_source.is_none() {
                    return Err(CaptureFailure::Missing {
                        reason:
                            "checkpoint eigenstate unavailable; partial export retained in ladder"
                                .into(),
                    });
                }
                let sources = r
                    .produced_manifest
                    .as_ref()
                    .or(r.reused_manifest.as_ref())
                    .map(|m| vec![m.clone()])
                    .unwrap_or_default();
                return CapturedDiagnostic::new(checkpoint, sources)
                    .map_err(CaptureFailure::failed);
            }
            if matches!(
                id,
                "target_distance"
                    | "distance_resolution"
                    | "target_residual_analysis"
                    | "deviation_decomposition"
            ) {
                if let Some(reason) = &target_missing {
                    return Err(CaptureFailure::Missing {
                        reason: format!("runtime target unavailable: {reason}"),
                    });
                }
            }
            let started = Instant::now();
            let result = run.capture_diagnostic_outcome(id, &options, cache);
            println!(
                "Capture {id}: {} ({:.3}s)",
                if result.is_ok() {
                    "completed"
                } else {
                    "incomplete"
                },
                started.elapsed().as_secs_f64()
            );
            result
        },
        cache,
    )?;
    journal.save("capture.json", &record.value)?;
    let manifest = record
        .produced_manifest
        .as_ref()
        .or(record.reused_manifest.as_ref())
        .ok_or_else(|| anyhow::anyhow!("retained capture manifest unavailable"))?;
    journal.save("capture-manifest.json", manifest)?;
    for (id, outcome) in record.value.receipt.outcomes() {
        let status = match outcome {
            xc_core::DiagnosticOutcome::Completed { .. } => Status::Pass,
            _ => Status::Incomplete,
        };
        checks.push(Check::new(
            id,
            "capture",
            status,
            if status == Status::Pass {
                "completed".into()
            } else {
                serde_json::to_string(outcome)?
            },
        ));
    }
    Ok(preparation_complete && record.value.receipt.is_complete())
}

pub const APPLICABILITY_POLICY: &str = "paper3-precision-control-v3";
pub const APPLICABILITY_EVIDENCE: &str = "paper3-precision-control-applicability-evidence-v3";
const NONGROUND: &str =
    "claimed CCM eigenpair is not the algebraic ground state in the requested subspace";
const AMBIGUOUS_SECTOR_PREFIX: &str = "sector diagnostic unavailable: invalid cache manifest: CCM sector resolution limit: unresolved eigenvector eigenspace: requested value does not identify exactly one eigenvalue (";
const CLUSTERED_GROUND_PREFIX: &str =
    "CCM ground state is unresolved or clustered at the requested precision: upper_count=";

fn canonical_count(value: &str, dimension: usize) -> Option<usize> {
    let count = value.parse::<usize>().ok()?;
    (count >= 2 && count <= dimension && count.to_string() == value).then_some(count)
}

fn ambiguous_sector(value: &serde_json::Value, dimension: usize) -> bool {
    value["status"] == "failed"
        && value["reason"].as_str().is_some_and(|reason| {
            reason
                .strip_prefix(AMBIGUOUS_SECTOR_PREFIX)
                .and_then(|s| s.strip_suffix(" candidate members)"))
                .and_then(|s| canonical_count(s, dimension))
                .is_some()
        })
}

fn decimal_bounds(text: &str, precision: u32) -> Option<(rug::Float, rug::Float)> {
    use rug::{float::Round, Float};
    if text.is_empty()
        || text.len() > 4096
        || !text
            .bytes()
            .all(|b| b.is_ascii_digit() || b"+-.eE".contains(&b))
    {
        return None;
    }
    if let Some((_, exponent)) = text.split_once(['e', 'E']) {
        let exponent = exponent.parse::<i32>().ok()?;
        if !(-100_000..=100_000).contains(&exponent) {
            return None;
        }
    }
    let lower = Float::with_val_round(precision, Float::parse(text).ok()?, Round::Down).0;
    let upper = Float::with_val_round(precision, Float::parse(text).ok()?, Round::Up).0;
    (lower.is_finite() && upper.is_finite()).then_some((lower, upper))
}

// A sign-resolved value below the storage floor and an interval spanning zero
// are both precision controls only when the same conservative source-scale
// checks pass. This metadata predicate does not establish a ground index.
fn source_below_storage_scale(
    resolution: &serde_json::Value,
    selected_eigenvalue: &str,
    precision_bits: u32,
) -> bool {
    use rug::{
        float::Round,
        ops::{AddAssignRound, MulAssignRound},
    };
    if !(64..=1_000_000).contains(&precision_bits)
        || resolution["arithmetic"] != "stored_state_residual_and_admitted_gap_v2"
    {
        return false;
    }
    let Some(work) = precision_bits.checked_add(256) else {
        return false;
    };
    let parse_field = |name: &str| {
        resolution[name]
            .as_str()
            .and_then(|s| decimal_bounds(s, work))
    };
    let Some((lambda_lower, lambda_upper)) = decimal_bounds(selected_eigenvalue, work) else {
        return false;
    };
    let Some((residual_lower, mut radius_upper)) = parse_field("residual_upper") else {
        return false;
    };
    let Some((lower_lower, lower_upper)) = parse_field("eigenvalue_lower") else {
        return false;
    };
    let Some((upper_lower, upper_upper)) = parse_field("eigenvalue_upper") else {
        return false;
    };
    let Some((scale_lower, _)) = parse_field("matrix_rounding_scale_upper") else {
        return false;
    };
    let sign_matches = match resolution["eigenvalue_resolution"].as_str() {
        Some("stored_sign_unresolved") => lower_upper <= 0 && upper_lower >= 0,
        Some("below_storage_floor") => upper_upper < 0 || lower_lower > 0,
        _ => false,
    };
    if residual_lower <= 0
        || scale_lower <= 0
        || !sign_matches
        || lower_upper >= upper_lower
        || lower_upper > lambda_lower
        || lambda_upper > upper_lower
        || (lambda_lower.is_zero() && lambda_upper.is_zero())
        || lower_lower.clone().abs() >= scale_lower
        || upper_upper.clone().abs() >= scale_lower
    {
        return false;
    }
    // Require lambda +/- max(8r, |lambda| * 2^-(p+8)) to stay strictly below
    // the storage policy scale, with outward rounding. Zero lambda is excluded
    // above because its producer local scale depends on matrix entries not in
    // this receipt. The policy scale is not an analytic assembly-error bound.
    radius_upper.mul_assign_round(8, Round::Up);
    let mut probe_upper = lambda_lower.abs();
    let other = lambda_upper.abs();
    if other > probe_upper {
        probe_upper = other;
    }
    let local_upper = probe_upper.clone() >> (precision_bits + 8);
    if local_upper > radius_upper {
        radius_upper = local_upper;
    }
    probe_upper.add_assign_round(radius_upper, Round::Up);
    // The strings were serialized at different source precisions. Require a
    // conservative factor-of-two margin rather than claiming an exact replay
    // of the producer's p+64 boundary arithmetic from printed decimals.
    for endpoint in [lower_lower.abs(), upper_upper.abs()] {
        if endpoint > probe_upper {
            probe_upper = endpoint;
        }
    }
    probe_upper.mul_assign_round(2, Round::Up);
    probe_upper < scale_lower
}

// This recognizes the exact conclusive producer branch: its lower inertia count
// was zero and its upper count was not one. It does not create an independent
// inertia certificate or establish which stored eigenvector is the ground state.
fn clustered_ground_source(
    reason: &str,
    resolution: &serde_json::Value,
    selected_eigenvalue: &str,
    precision_bits: u32,
    dimension: usize,
) -> bool {
    let Some((count, rest)) = reason
        .strip_prefix(CLUSTERED_GROUND_PREFIX)
        .and_then(|s| s.split_once(", eigenvalue="))
    else {
        return false;
    };
    let Some((lambda_text, residual_text)) = rest.split_once(", residual=") else {
        return false;
    };
    canonical_count(count, dimension).is_some()
        && resolution["eigenvalue_resolution"] == "stored_sign_unresolved"
        && lambda_text == selected_eigenvalue
        && resolution["residual_upper"].as_str() == Some(residual_text)
        && source_below_storage_scale(resolution, selected_eigenvalue, precision_bits)
}

fn precision_control_configuration(args: &crate::MeasureRequest) -> bool {
    let grid = match (args.lambda_sq, args.n_modes) {
        (13, 80) => [30, 45, 90, 180].contains(&args.precision_digits),
        (50, 400) => [50, 100, 150, 200, 300].contains(&args.precision_digits),
        _ => false,
    };
    grid && args.ground_index_policy == crate::GroundIndexPolicy::RecordOutcome
        && args.root_acquisition == crate::RootAcquisition::Seeded
        && args.first_zero_index == 1
        && args.zero_count == 5
        && args.parity_policy == crate::ParityPolicy::EvenSector
        && args.eigenstate_solver == crate::EigenstateSolver::Auto
        && args.research_capture == ResearchCapture::Ultra
        && !args.capture_sector_gap_certificate
        && !args.certify_roots
        && args.research_sector_eigenpairs == 8
}

fn has_outcome(value: &serde_json::Value, status: &str, reason: &str) -> bool {
    value["status"] == status && value["reason"] == reason
}

fn precision_limited_source(
    admission: &serde_json::Value,
    resolution: &serde_json::Value,
    precision_bits: u32,
    selected_eigenvalue: &str,
    dimension: usize,
) -> bool {
    let Some(reason) = admission["reason"].as_str() else {
        return false;
    };
    if admission["established"] != false
        || resolution["separation_unresolved_reason"] != reason
        || resolution.get("selected_gap_lower") != Some(&serde_json::Value::Null)
        || resolution.get("residual_angle_upper") != Some(&serde_json::Value::Null)
    {
        return false;
    }
    // The canonical nonground outcome is conclusive, not an unknown proof
    // failure. Both unresolved-sign and sign-resolved below-floor controls
    // require the same conservative source-scale evidence; neither is promoted.
    (reason == NONGROUND && source_below_storage_scale(resolution, selected_eigenvalue, precision_bits))
        || (reason == format!("CCM stored precision resolution limit: selected-subspace gap is not separated from the matrix rounding scale at {precision_bits} bits")
            && matches!(resolution["eigenvalue_resolution"].as_str(),
                Some("resolved" | "below_storage_floor" | "stored_sign_unresolved")))
        || clustered_ground_source(reason, resolution, selected_eigenvalue, precision_bits, dimension)
}

fn qualify_unavailable(
    unhandled: &mut serde_json::Map<String, serde_json::Value>,
    precision_bits: u32,
    dimension: usize,
) -> serde_json::Map<String, serde_json::Value> {
    let mut candidates = BTreeMap::new();
    for id in ["evenness", "sector_analysis"] {
        if unhandled
            .get(id)
            .is_some_and(|v| ambiguous_sector(v, dimension))
        {
            candidates.insert(id, "the requested sector eigenvector is not uniquely identifiable at the retained source precision");
        }
    }
    let response_reason = format!("invalid cache manifest: CCM response unresolved_near_crossing: source-matrix eigenvalue intervals are not finitely separated at {precision_bits} bits");
    for id in ["prime_power_response", "u_flow_response"] {
        if unhandled
            .get(id)
            .is_some_and(|v| has_outcome(v, "failed", &response_reason))
        {
            candidates.insert(id, "the response prerequisite requires a separated source eigenvalue; the retained source intervals do not establish that separation");
        }
    }
    candidates
        .into_iter()
        .map(|(id, basis)| {
            let raw_outcome = unhandled
                .remove(id)
                .expect("candidate comes from raw outcome");
            (
                id.into(),
                json!({"raw_outcome":raw_outcome,
            "classification":"unavailable_at_stored_precision","basis":basis}),
            )
        })
        .collect()
}

fn preparation_matches(
    args: &crate::MeasureRequest,
    precision_bits: u32,
    sources: &serde_json::Value,
    status: &serde_json::Value,
    request: &serde_json::Value,
    prepared: &serde_json::Value,
) -> bool {
    let eigenpair_digest = sources
        .as_array()
        .and_then(|items| {
            items
                .iter()
                .find(|m| m["key"]["kind"] == "ccm_weil_eigenpair")
        })
        .and_then(|m| m["content_digest"].as_str());
    status["status"] == "prepared"
        && status["source_join_validated"] == true
        && request["primary_sources"] == *sources
        && eigenpair_digest.is_some_and(|d| prepared["source_eigenpair"] == d)
        && request["configuration"]["lambda_squared"] == args.lambda_sq
        && request["configuration"]["n_modes"] == args.n_modes
        && request["configuration"]["precision_bits"] == precision_bits
}

fn read_prerequisite(journal: &Journal, name: &str) -> Result<(serde_json::Value, String)> {
    let path = journal.directory.join(name);
    anyhow::ensure!(
        std::fs::metadata(&path)?.len() <= 64 * 1024 * 1024,
        "precision-control prerequisite exceeds the bounded assessment reader: {name}"
    );
    let bytes = std::fs::read(path)?;
    let digest = xc_cache::ContentDigest::sha256(&bytes).to_string();
    Ok((serde_json::from_slice(&bytes)?, digest))
}

/// Assess applicability without changing the Toolkit's requested capture plan,
/// receipt, artifact identities, numerical gates, or failed/missing outcomes.
/// A precision-floor control can retain a selected state even when the source
/// precision does not identify a unique eigenspace. This is a separate execution
/// qualification, never evidence that a ground-state or response claim passed.
#[allow(clippy::too_many_arguments)]
pub fn assess_applicability(
    args: &crate::MeasureRequest,
    precision_bits: u32,
    admission: &serde_json::Value,
    resolution: &serde_json::Value,
    selected_eigenvalue: &str,
    sources: &[xc_cache::ArtifactManifest],
    receipt: &serde_json::Value,
    all_complete: bool,
    journal: &Journal,
) -> Result<serde_json::Value> {
    let outcomes = receipt["receipt"]["outcomes"].as_object();
    let mut unhandled = outcomes
        .into_iter()
        .flat_map(|m| m.iter())
        .filter(|(_, outcome)| outcome["status"] != "completed")
        .map(|(id, outcome)| (id.clone(), outcome.clone()))
        .collect::<serde_json::Map<_, _>>();
    let mut qualified = serde_json::Map::new();
    let mut evidence = json!({});
    let mut preparation_valid = false;
    let dimension = args.n_modes.checked_add(1).unwrap_or(0);
    let source_floor = precision_limited_source(
        admission,
        resolution,
        precision_bits,
        selected_eigenvalue,
        dimension,
    );
    let eligible =
        args.precision_control_capture && precision_control_configuration(args) && source_floor;
    if eligible && !all_complete {
        let (status, status_sha256) = read_prerequisite(journal, "input-preparation-status.json")?;
        let (request, request_sha256) =
            read_prerequisite(journal, "input-preparation-request.json")?;
        let (prepared, prepared_sha256) =
            read_prerequisite(journal, "prepared-research-inputs.json")?;
        let source_values = serde_json::to_value(sources)?;
        preparation_valid = preparation_matches(
            args,
            precision_bits,
            &source_values,
            &status,
            &request,
            &prepared,
        );
        evidence = json!({
            "input_preparation_status_sha256":status_sha256,
            "input_preparation_request_sha256":request_sha256,
            "prepared_research_inputs_sha256":prepared_sha256,
            "source_join_validated":preparation_valid,
            "stored_state_resolution":resolution,
            "selected_eigenvalue":selected_eigenvalue
        });
        if preparation_valid {
            qualified = qualify_unavailable(&mut unhandled, precision_bits, dimension);
        }
    }
    let applied = !qualified.is_empty();
    let applicable = all_complete
        || (eligible
            && preparation_valid
            && applied
            && unhandled.is_empty()
            && outcomes.is_some_and(|m| !m.is_empty()));
    Ok(json!({
        "schema_version":1,"policy":APPLICABILITY_POLICY,
        "enabled":args.precision_control_capture,"applied":applied,
        "configuration":{
            "lambda_squared":args.lambda_sq,"n_modes":args.n_modes,
            "precision_digits":args.precision_digits,"precision_bits":precision_bits,
            "root_acquisition":args.root_acquisition,"first_zero_index":args.first_zero_index,
            "zero_count":args.zero_count,"parity_policy":args.parity_policy,
            "eigenstate_solver":args.eigenstate_solver,"ground_index_policy":args.ground_index_policy,
            "research_capture":args.research_capture,
            "capture_sector_gap_certificate":args.capture_sector_gap_certificate
        },
        "build_info":crate::build_info(),"primary_sources":sources,
        "ground_index_admission":admission,
        "all_requested_capture_complete":all_complete,
        "applicable_capture_complete":applicable,
        "qualified_diagnostics":qualified,"unhandled_diagnostics":unhandled,
        "prerequisite_evidence":evidence,
        "scope":"Versioned precision-control applicability only. Raw requested capture outcomes remain unchanged; unavailable ground-state and response diagnostics are not numerical successes or mathematical proofs. Canonical ground-count semantics come from the source-bound producer outcome, not a new independent inertia certificate. The matrix rounding scale is a resolution policy, not an analytic assembly-error bound. Nonground and clustered-source metadata require a conservative factor-of-two margin below the serialized storage scale; this locates the selected state's bracket, not every lower eigenvalue, and is not an exact replay of the producer's boundary arithmetic. A conclusive nonground outcome remains nonground."
    }))
}

#[cfg(test)]
mod tests {
    use super::*;
    const AMBIGUOUS_SECTOR: &str = "sector diagnostic unavailable: invalid cache manifest: CCM sector resolution limit: unresolved eigenvector eigenspace: requested value does not identify exactly one eigenvalue (2 candidate members)";

    fn control() -> crate::MeasureRequest {
        crate::MeasureRequest {
            lambda_sq: 13,
            n_modes: 80,
            precision_digits: 30,
            first_zero_index: 1,
            zero_count: 5,
            display_digits: 16,
            root_acquisition: crate::RootAcquisition::Seeded,
            parity_policy: crate::ParityPolicy::EvenSector,
            eigenstate_solver: crate::EigenstateSolver::Auto,
            ground_index_policy: crate::GroundIndexPolicy::RecordOutcome,
            precision_control_capture: true,
            research_capture: ResearchCapture::Ultra,
            research_sector_eigenpairs: 8,
            parallel_gl_roots: false,
            capture_sector_gap_certificate: false,
            capture_maximum_stream_scalar_bytes: 274_877_906_944,
            capture_output: "unused".into(),
            certify_roots: false,
            json_output: None,
        }
    }

    #[test]
    fn applicability_is_limited_to_exact_precision_control_configurations() {
        let mut args = control();
        assert!(precision_control_configuration(&args));
        for (c, n, ps) in [
            (13, 80, vec![30, 45, 90, 180]),
            (50, 400, vec![50, 100, 150, 200, 300]),
        ] {
            for p in ps {
                args.lambda_sq = c;
                args.n_modes = n;
                args.precision_digits = p;
                assert!(precision_control_configuration(&args));
            }
        }
        args.precision_digits = 301;
        assert!(!precision_control_configuration(&args));
        args = control();
        args.ground_index_policy = crate::GroundIndexPolicy::Require;
        assert!(!precision_control_configuration(&args));
        args = control();
        args.first_zero_index = 2;
        assert!(!precision_control_configuration(&args));
        args = control();
        args.capture_sector_gap_certificate = true;
        assert!(!precision_control_configuration(&args));
    }

    #[test]
    fn applicability_retains_raw_outcomes_and_refuses_unknown_budget_or_missing_failures() {
        let raw = json!({
            "evenness":{"status":"failed","reason":AMBIGUOUS_SECTOR},
            "prime_power_response":{"status":"failed","reason":"invalid cache manifest: CCM response unresolved_near_crossing: source-matrix eigenvalue intervals are not finitely separated at 164 bits"},
            "u_flow_response":{"status":"failed","reason":"working memory budget exhausted"},
            "spectral_cluster_full":{"status":"missing","reason":"explicit retained cluster vectors and assembly policies required"}
        });
        let mut pending = raw.as_object().unwrap().clone();
        let qualified = qualify_unavailable(&mut pending, 164, 81);
        assert_eq!(qualified.len(), 2);
        assert_eq!(qualified["evenness"]["raw_outcome"], raw["evenness"]);
        assert_eq!(pending.len(), 2);
        assert_eq!(pending["u_flow_response"], raw["u_flow_response"]);
        assert!(pending.contains_key("spectral_cluster_full"));
        let mut wrong_precision = raw.as_object().unwrap().clone();
        qualify_unavailable(&mut wrong_precision, 165, 81);
        assert!(wrong_precision.contains_key("prime_power_response"));
    }

    #[test]
    fn applicability_requires_exact_preparer_source_join_and_configuration() {
        let args = control();
        let sources = json!([{"key":{"kind":"ccm_weil_eigenpair"},"content_digest":"source"}]);
        let status = json!({"status":"prepared","source_join_validated":true});
        let request = json!({"primary_sources":sources,"configuration":{"lambda_squared":13,"n_modes":80,"precision_bits":164}});
        let prepared = json!({"source_eigenpair":"source"});
        assert!(preparation_matches(
            &args, 164, &sources, &status, &request, &prepared
        ));
        assert!(!preparation_matches(
            &args, 165, &sources, &status, &request, &prepared
        ));
        assert!(!preparation_matches(
            &args,
            164,
            &sources,
            &status,
            &request,
            &json!({"source_eigenpair":"other"})
        ));
        assert!(!preparation_matches(
            &args,
            164,
            &sources,
            &json!({"status":"prepared","source_join_validated":false}),
            &request,
            &prepared
        ));
    }

    #[test]
    fn applicability_never_activates_without_explicit_source_floor_qualification() {
        let mut args = control();
        let admission = json!({"established":false,"reason":NONGROUND});
        let resolution = json!({"eigenvalue_resolution":"below_storage_floor","separation_unresolved_reason":NONGROUND,"selected_gap_lower":null,"residual_angle_upper":null});
        let raw = json!({"receipt":{"outcomes":{"evenness":{"status":"failed","reason":AMBIGUOUS_SECTOR}}}});
        let journal = Journal {
            directory: "must-not-be-read-for-ineligible-control".into(),
        };
        args.precision_control_capture = false;
        let result = assess_applicability(
            &args,
            164,
            &admission,
            &resolution,
            "0",
            &[],
            &raw,
            false,
            &journal,
        )
        .unwrap();
        assert_eq!(result["applicable_capture_complete"], false);
        assert_eq!(
            result["unhandled_diagnostics"]["evenness"],
            raw["receipt"]["outcomes"]["evenness"]
        );
        args.precision_control_capture = true;
        for wrong_admission in [
            json!({"established":true}),
            json!({"established":false,"reason":"memory budget exhausted"}),
        ] {
            let result = assess_applicability(
                &args,
                164,
                &wrong_admission,
                &resolution,
                "0",
                &[],
                &raw,
                false,
                &journal,
            )
            .unwrap();
            assert_eq!(result["applicable_capture_complete"], false);
            assert_eq!(result["applied"], false);
        }
    }

    #[test]
    fn known_gap_resolution_outcome_does_not_require_an_unresolved_eigenvalue() {
        let reason="CCM stored precision resolution limit: selected-subspace gap is not separated from the matrix rounding scale at 164 bits";
        let admission = json!({"established":false,"reason":reason});
        let mut resolution = json!({"eigenvalue_resolution":"resolved","separation_unresolved_reason":reason,"selected_gap_lower":null,"residual_angle_upper":null});
        assert!(precision_limited_source(
            &admission,
            &resolution,
            164,
            "0",
            81
        ));
        assert!(!precision_limited_source(
            &admission,
            &resolution,
            165,
            "0",
            81
        ));
        resolution["selected_gap_lower"] = json!("0.1");
        assert!(!precision_limited_source(
            &admission,
            &resolution,
            164,
            "0",
            81
        ));
        resolution["selected_gap_lower"] = serde_json::Value::Null;
        for unknown in ["CCM ground-index inertia is inconclusive within the guard precision budget", "ground-index stage exceeds workspace budget", "CCM ground state is unresolved or clustered at the requested precision: upper_count=2, eigenvalue=0, residual=1"] {
            resolution["separation_unresolved_reason"]=json!(unknown);
            assert!(!precision_limited_source(&json!({"established":false,"reason":unknown}),&resolution,164,"0",81));
        }
    }

    fn clustered_control() -> (serde_json::Value, serde_json::Value, &'static str) {
        let lambda = "1.5055664502159138363945483248616315216337809191509450519797090237602861e-70";
        let residual = "3.22877953976253008334943100414560455826445648623661223484693389043687363695482791066578672e-70";
        let reason =
            format!("{CLUSTERED_GROUND_PREFIX}5, eigenvalue={lambda}, residual={residual}");
        let admission = json!({"established":false,"reason":reason});
        let resolution = json!({"arithmetic":"stored_state_residual_and_admitted_gap_v2","eigenvalue_resolution":"stored_sign_unresolved",
            "separation_unresolved_reason":reason,"selected_gap_lower":null,"residual_angle_upper":null,
            "residual_upper":residual,
            "eigenvalue_lower":"-1.72321308954661624695488267928397303663067556708566718286722486667658757819410781546435139e-70",
            "eigenvalue_upper":"4.73434598997844391974397932900723607989823740538755728682664291419715969571554800586722205e-70",
            "matrix_rounding_scale_upper":"1.81301996003809347962777864054630263311560404455764947981685184868451223902905141953396053e-66"});
        (admission, resolution, lambda)
    }

    #[test]
    fn v2_clustered_ground_control_binds_actual_retained_values_and_bounds() {
        let (admission, resolution, lambda) = clustered_control();
        assert!(precision_limited_source(
            &admission,
            &resolution,
            231,
            lambda,
            401
        ));
        assert!(!precision_limited_source(
            &admission,
            &resolution,
            231,
            "2e-70",
            401
        ));
        assert!(!precision_limited_source(
            &admission,
            &resolution,
            231,
            lambda,
            4
        ));
        for (field, value) in [
            ("residual_upper", json!("1e-70")),
            ("eigenvalue_resolution", json!("resolved")),
            ("selected_gap_lower", json!("1")),
            ("residual_angle_upper", json!("1")),
            ("eigenvalue_lower", json!("1e-70")),
            ("eigenvalue_upper", json!("-1e-70")),
            ("eigenvalue_upper", json!("0")),
            ("matrix_rounding_scale_upper", json!("1e-70")),
            ("matrix_rounding_scale_upper", json!("0")),
            ("matrix_rounding_scale_upper", json!("NaN")),
            ("eigenvalue_lower", json!("-inf")),
            ("eigenvalue_upper", json!("1e100001")),
        ] {
            let mut invalid = resolution.clone();
            invalid[field] = value;
            assert!(
                !precision_limited_source(&admission, &invalid, 231, lambda, 401),
                "{field}"
            );
        }
        for count in ["0", "1", "402", "05", "+5", "-5", "5 trailing"] {
            let reason = admission["reason"]
                .as_str()
                .unwrap()
                .replace("upper_count=5,", &format!("upper_count={count},"));
            let mut invalid = resolution.clone();
            invalid["separation_unresolved_reason"] = json!(reason);
            assert!(!precision_limited_source(
                &json!({"established":false,"reason":reason}),
                &invalid,
                231,
                lambda,
                401
            ));
        }
    }

    #[test]
    fn v2_probe_scale_is_strict_and_zero_source_is_not_inferred() {
        let reason = format!("{CLUSTERED_GROUND_PREFIX}2, eigenvalue=1, residual=1");
        let admission = json!({"established":false,"reason":reason});
        let mut resolution = json!({"arithmetic":"stored_state_residual_and_admitted_gap_v2","eigenvalue_resolution":"stored_sign_unresolved",
            "separation_unresolved_reason":reason,"selected_gap_lower":null,"residual_angle_upper":null,
            "residual_upper":"1","eigenvalue_lower":"0","eigenvalue_upper":"2",
            "matrix_rounding_scale_upper":"18"});
        assert!(!precision_limited_source(
            &admission,
            &resolution,
            231,
            "1",
            401
        ));
        resolution["matrix_rounding_scale_upper"] = json!("19");
        assert!(precision_limited_source(
            &admission,
            &resolution,
            231,
            "1",
            401
        ));
        let zero_reason = reason.replace("eigenvalue=1,", "eigenvalue=0,");
        resolution["separation_unresolved_reason"] = json!(zero_reason);
        resolution["eigenvalue_lower"] = json!("-1");
        assert!(!precision_limited_source(
            &json!({"established":false,"reason":zero_reason}),
            &resolution,
            231,
            "0",
            401
        ));
    }

    #[test]
    fn v2_sector_candidate_count_is_canonical_bounded_and_distinct_from_ground_count() {
        for count in ["2", "31", "401"] {
            let reason = format!("{AMBIGUOUS_SECTOR_PREFIX}{count} candidate members)");
            assert!(ambiguous_sector(
                &json!({"status":"failed","reason":reason}),
                401
            ));
        }
        for count in ["0", "1", "402", "031", "+31", "-31", "31 extra"] {
            let reason = format!("{AMBIGUOUS_SECTOR_PREFIX}{count} candidate members)");
            assert!(!ambiguous_sector(
                &json!({"status":"failed","reason":reason}),
                401
            ));
        }
        assert!(!ambiguous_sector(
            &json!({"status":"missing","reason":AMBIGUOUS_SECTOR}),
            401
        ));
        assert!(!ambiguous_sector(
            &json!({"status":"failed","reason":format!("{AMBIGUOUS_SECTOR} guard budget exhausted")}),
            401
        ));
    }

    fn nonground_sign_control() -> (serde_json::Value, serde_json::Value, &'static str) {
        let lambda = "4.920354169916721831076896574044860205820552412273174410287764062922768559519593697399861696237317797551520181818491207152e-121";
        let admission = json!({"established":false,"reason":NONGROUND});
        let resolution = json!({"arithmetic":"stored_state_residual_and_admitted_gap_v2",
            "eigenvalue_resolution":"stored_sign_unresolved","separation_unresolved_reason":NONGROUND,
            "selected_gap_lower":null,"residual_angle_upper":null,
            "residual_upper":"1.5793218311939367582155197823332562652834763747934341669571841535302918355948642561950062348775487610682538699229511029649684188055344824140e-120",
            "eigenvalue_lower":"-1.0872864142022645751078301249287702447014211335661167259284077472380149796429048864550200652538169813131018517411019822497289460227103663634e-120",
            "eigenvalue_upper":"2.0713572481856089413232094397377422858655316160207516079859605598225686915468236259349924045012805408234058881048002236802078915883585984646e-120",
            "matrix_rounding_scale_upper":"1.9383103071530316218846529276661912812001120227295168164414254397631783489465064653111425148676089811641057013137887721930658620809954341890e-116"});
        (admission, resolution, lambda)
    }

    #[test]
    fn v3_actual_nonground_p100_sign_interval_is_a_control_not_a_ground_proof() {
        let (admission, resolution, lambda) = nonground_sign_control();
        assert!(precision_limited_source(
            &admission,
            &resolution,
            397,
            lambda,
            401
        ));
        assert_eq!(admission["established"], false);
        for (field, value) in [
            ("arithmetic", json!("unknown")),
            ("eigenvalue_resolution", json!("resolved")),
            ("eigenvalue_resolution", json!("below_storage_floor")),
            ("residual_upper", json!("0")),
            ("residual_upper", json!("-1")),
            ("residual_upper", json!("1e-110")),
            ("residual_upper", json!("NaN")),
            ("eigenvalue_lower", json!("1e-122")),
            ("eigenvalue_upper", json!("0")),
            ("matrix_rounding_scale_upper", json!("1e-120")),
            ("matrix_rounding_scale_upper", json!("0")),
            ("selected_gap_lower", json!("1")),
            ("residual_angle_upper", json!("1")),
        ] {
            let mut invalid = resolution.clone();
            invalid[field] = value;
            assert!(
                !precision_limited_source(&admission, &invalid, 397, lambda, 401),
                "{field}"
            );
        }
        for field in [
            "arithmetic",
            "residual_upper",
            "eigenvalue_lower",
            "eigenvalue_upper",
            "matrix_rounding_scale_upper",
            "selected_gap_lower",
            "residual_angle_upper",
        ] {
            let mut invalid = resolution.clone();
            invalid.as_object_mut().unwrap().remove(field);
            assert!(
                !precision_limited_source(&admission, &invalid, 397, lambda, 401),
                "missing {field}"
            );
        }
        for reason in [
            format!("{NONGROUND} trailing"),
            "CCM ground-index inertia is inconclusive within the guard precision budget".into(),
            "ground-index stage exceeds workspace budget".into(),
        ] {
            let mut invalid = resolution.clone();
            invalid["separation_unresolved_reason"] = json!(reason);
            assert!(!precision_limited_source(
                &json!({"established":false,"reason":reason}),
                &invalid,
                397,
                lambda,
                401
            ));
        }
        assert!(!precision_limited_source(
            &admission,
            &resolution,
            397,
            "0",
            401
        ));
        assert!(!precision_limited_source(
            &admission,
            &resolution,
            397,
            "1e-110",
            401
        ));
        assert!(!precision_limited_source(
            &json!({"established":true,"reason":NONGROUND}),
            &resolution,
            397,
            lambda,
            401
        ));
    }

    #[test]
    fn v3_sign_resolved_nonground_p30_control_keeps_the_same_conservative_gate() {
        let admission = json!({"established":false,"reason":NONGROUND});
        let lambda = "-3.08571487519675684658635048576602828758543460371413e-50";
        let mut resolution = json!({"arithmetic":"stored_state_residual_and_admitted_gap_v2",
            "eigenvalue_resolution":"below_storage_floor","separation_unresolved_reason":NONGROUND,
            "selected_gap_lower":null,"residual_angle_upper":null,
            "residual_upper":"1.533677974539112196050577512306561983573167716374381872089391400254457e-50",
            "eigenvalue_lower":"-4.619392849735869042636927998072590271158602320088512547511492726161503e-50",
            "eigenvalue_upper":"-1.552036900657644650535772973459466304012266887339748803332709925652574e-50",
            "matrix_rounding_scale_upper":"3.293039670328264857510010689915451189549896562116946054680914711247066e-47"});
        assert!(precision_limited_source(
            &admission,
            &resolution,
            164,
            lambda,
            81
        ));
        resolution["eigenvalue_resolution"] = json!("stored_sign_unresolved");
        assert!(!precision_limited_source(
            &admission,
            &resolution,
            164,
            lambda,
            81
        ));
    }

    #[test]
    fn v3_nonground_scale_requires_a_strict_factor_two_margin() {
        let admission = json!({"established":false,"reason":NONGROUND});
        let mut resolution = json!({"arithmetic":"stored_state_residual_and_admitted_gap_v2",
            "eigenvalue_resolution":"stored_sign_unresolved","separation_unresolved_reason":NONGROUND,
            "selected_gap_lower":null,"residual_angle_upper":null,
            "residual_upper":"1","eigenvalue_lower":"0","eigenvalue_upper":"2",
            "matrix_rounding_scale_upper":"18"});
        assert!(!precision_limited_source(
            &admission,
            &resolution,
            397,
            "1",
            401
        ));
        resolution["matrix_rounding_scale_upper"] = json!("19");
        assert!(precision_limited_source(
            &admission,
            &resolution,
            397,
            "1",
            401
        ));
    }
}
