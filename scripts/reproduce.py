#!/usr/bin/env python3
# Copyright (c) 2026 Ronnie Andrews, Jr. (Team Xcelerator Inc.(R))
# See LICENSE for terms. Provided for verification and study.
"""
reproduce.py -- one-command reproduction driver for the claims of

    "A Quantitative Convergence Law for the Connes-Consani-Moscovici
     Zeta Spectral Triple"  (Andrews, 2026; doi:10.5281/zenodo.20938200)

Each subcommand runs the `measure` binary across the parameter sweep a
single claim needs. Every requested zero is retained in a structured JSON
result; one selected ordinal supplies D to the paper's scalar fits. The
published fits concern zero 1, while other ordinals are intentionally
reported as exploratory extensions of the convergence law.

This module is the structured analysis backend. Most users should run the
readable `scripts/claim*.sh` launchers; direct invocation remains supported:

    python3 scripts/reproduce.py <claim> [options]

Claims (paper order):
    precision-slope     C2   D_Wprec slope = 1
    budget-switch       C1   the min() switches budgets (low-scale demo)
    floor-artifact      C3   sub-floor results are precision-limited
    nmode-ramp          C4   normalized mode budget follows a tanh ramp
    archimedean-slope   C7   leading digit slope pi^2/(ln10 ln L2) at L2=7
    mode-exponent       C8   q(lambda^2) exponent law
    onset-constant      C9   onset c clusters near 4/pi
    shannon             C10  saturation at N/(L2 ln L2) ~ 2.0-2.3   [server]
    prime-anchor        C11  D_Primes(100) = 526.08
    matching-floor      C12  D_Primes(200) ~ 1070.4 = two-floor anchor [server]
    prime-smooth        C13  ceiling is smooth, ~5.3 digits / unit L2
    bottleneck          C14  sup over N,P at fixed L2 = the prime ceiling
    all                 run every claim (use --quick to skip server-grade)

Requires: a release build with the `hp` feature, and Python 3.8+ (stdlib only).
    cargo build --release --features hp        (run inside WSL2 on Windows)
"""
import argparse
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

_APPLICABILITY_POLICY = "paper3-precision-control-v3"
_APPLICABILITY_EVIDENCE = "paper3-precision-control-applicability-evidence-v3"
_CLUSTERED_GROUND_PREFIX = "CCM ground state is unresolved or clustered at the requested precision: upper_count="
_AMBIGUOUS_SECTOR_PREFIX = ("sector diagnostic unavailable: invalid cache manifest: CCM sector resolution limit: "
    "unresolved eigenvector eigenspace: requested value does not identify exactly one eigenvalue (")


def _finite_decimal_fraction(text):
    # Exact metadata comparisons, independent of the producer's MPFR arithmetic.
    if (not isinstance(text, str) or not text or len(text) > 4096 or
            not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", text)):
        raise ValueError("invalid finite source decimal")
    exponent = re.split("[eE]", text)
    if len(exponent) == 2 and not -100_000 <= int(exponent[1]) <= 100_000:
        raise ValueError("source decimal exponent outside bounded verification")
    try:
        return Fraction(Decimal(text))
    except (InvalidOperation, OverflowError) as error:
        raise ValueError("invalid finite source decimal") from error


def _canonical_count(text, dimension):
    return (isinstance(text, str) and re.fullmatch(r"[1-9][0-9]*", text) is not None
            and len(text) <= 20 and 2 <= int(text) <= dimension)


def _ambiguous_sector_reason(reason, dimension):
    if not isinstance(reason, str) or not reason.startswith(_AMBIGUOUS_SECTOR_PREFIX):
        return False
    count = reason[len(_AMBIGUOUS_SECTOR_PREFIX):]
    return count.endswith(" candidate members)") and _canonical_count(count[:-19], dimension)


def _source_below_storage_scale(report, resolution):
    """Conservative source-metadata qualification, not a new ground-index proof."""
    try:
        if (not isinstance(report["precision_bits_working"], int) or
                not 64 <= report["precision_bits_working"] <= 1_000_000 or
                resolution.get("arithmetic") != "stored_state_residual_and_admitted_gap_v2"):
            return False
        value = _finite_decimal_fraction(report.get("selected_eigenvalue"))
        radius = _finite_decimal_fraction(resolution.get("residual_upper"))
        lower = _finite_decimal_fraction(resolution.get("eigenvalue_lower"))
        upper = _finite_decimal_fraction(resolution.get("eigenvalue_upper"))
        scale = _finite_decimal_fraction(resolution.get("matrix_rounding_scale_upper"))
        sign_matches = ((resolution.get("eigenvalue_resolution") == "stored_sign_unresolved"
                         and lower <= 0 <= upper) or
                        (resolution.get("eigenvalue_resolution") == "below_storage_floor"
                         and (upper < 0 or lower > 0)))
        # For lambda=0, the producer's local probe depends on unretained matrix
        # entries; it cannot be admitted from this report alone.
        local_radius = abs(value) / (1 << (report["precision_bits_working"] + 8))
        return (value != 0 and radius > 0 and scale > 0 and sign_matches and lower < upper and
                lower <= value <= upper and abs(lower) < scale and abs(upper) < scale and
                2 * max(abs(lower), abs(upper), abs(value) + max(8 * radius, local_radius)) < scale)
    except (ValueError, KeyError, TypeError):
        return False


def _clustered_ground_source(report, resolution, reason):
    if not isinstance(reason, str) or not reason.startswith(_CLUSTERED_GROUND_PREFIX):
        return False
    try:
        count, rest = reason[len(_CLUSTERED_GROUND_PREFIX):].split(", eigenvalue=", 1)
        eigenvalue, residual = rest.split(", residual=", 1)
        return (_canonical_count(count, report["n_modes"] + 1) and
                resolution.get("eigenvalue_resolution") == "stored_sign_unresolved" and
                eigenvalue == report.get("selected_eigenvalue") and
                residual == resolution.get("residual_upper") and
                _source_below_storage_scale(report, resolution))
    except (ValueError, KeyError, TypeError):
        return False

# --------------------------------------------------------------------------
# Constants from the paper
# --------------------------------------------------------------------------
GAMMA = 0.5772156649015329       # Euler-Mascheroni
LN10 = math.log(10.0)
K = 4.0 * math.pi / LN10         # prime-ceiling leading coefficient, 5.45750...
C0 = math.log10(2.0**14 * math.sqrt(2.0) * math.pi**5 / 3.0)  # 6.3736..., eigenvalue-floor prefactor
P_M = 5.0                        # matching-floor sub-log coefficient (empirical)
C_M = 9.5                        # matching-floor offset (empirical)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_BIN = os.path.join(REPO_ROOT, "target", "release", "ccm-convergence-rate")

# --------------------------------------------------------------------------
# Derived quantities (closed forms from the paper)
# --------------------------------------------------------------------------
def matching_floor(lsq):
    """Matching floor D_match = K L2 - P_m log10 L2 - c_m  (paper eq:primes, the floor min() consumes)."""
    return K * lsq - P_M * math.log10(lsq) - C_M

def eigenvalue_floor(lsq):
    """Eigenvalue floor = K L2 - (9/2) log10 L2 - C0  (paper eq:eigfloor, the prolate asymptotic)."""
    return K * lsq - 4.5 * math.log10(lsq) - C0

def shannon_number(lsq):
    """Time-frequency Shannon number of the box, S = L2 ln L2."""
    return lsq * math.log(lsq)

def q_formula(lsq):
    """Closed-form mode exponent q(L2) = 2 / (2 gamma + ln ln L2)  (paper eq:q)."""
    return 2.0 / (2.0 * GAMMA + math.log(math.log(lsq)))

def archimedean_slope(lsq):
    """Predicted leading digit slope, pi^2 / (ln10 ln L2)  (paper eq:slope)."""
    return math.pi**2 / (LN10 * math.log(lsq))

# --------------------------------------------------------------------------
# Binary invocation + output parsing
# --------------------------------------------------------------------------
_BIN = DEFAULT_BIN
_FIRST_ZERO_INDEX = 1
_ZERO_COUNT = 5
_ANALYSIS_ZERO_INDEX = 1
_ROOT_ACQUISITION = "seeded"
_PARITY_POLICY = "even-sector"
_EIGENSTATE_SOLVER = "auto"
_RESEARCH_CAPTURE = "ultra"
_RESEARCH_SECTOR_EIGENPAIRS = 8
_RESULTS_DIR = os.path.join(REPO_ROOT, "outputs")
_RESUME = False
_MEASUREMENTS = []
_BUILD_INFO = None
_BINARY_SHA256 = None
_PARALLEL_GL_ROOTS = False
_SECTOR_GAP = False
_STREAM_SCALAR_BYTES = 274877906944
_RESUME_DIR = None
_CHECKS = []
_ANALYSIS = {}
_INTEGRITY_ISSUES = []
_INVOCATION_ID = None
_INPUT_BINDINGS = {}
_GROUND_INDEX_POLICY = "require"
_GROUND_POLICY_OVERRIDE = None
_GROUND_QUALIFICATIONS = []
_PRECISION_CONTROL_REQUESTED = False
_PRECISION_CONTROL_CAPTURE = False
_CAPTURE_COVERAGE = []


def _claim_ground_policy(claim):
    return _GROUND_POLICY_OVERRIDE or ("record-outcome" if claim in {
        "budget-switch", "precision-slope", "floor-artifact"} else "require")


def _claim_precision_control(claim):
    return _PRECISION_CONTROL_REQUESTED and claim in {
        "budget-switch", "precision-slope", "floor-artifact"}

# This order is shared with the Rust executable's --build-info implementation.
BUILD_SOURCES = ("src/main.rs", "src/journal.rs", "src/capture.rs",
                 "src/preparation.rs", "Cargo.toml", "Cargo.lock")


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = path + ".tmp-" + uuid.uuid4().hex
    with open(temporary, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
    os.replace(temporary, path)


def _verify_binary():
    """Bind a prebuilt executable to these exact sources and lockfile."""
    global _BUILD_INFO, _BINARY_SHA256
    result = subprocess.run([_BIN, "--build-info"], check=True,
                            capture_output=True, text=True)
    info = json.loads(result.stdout)
    source_texts = [(Path(REPO_ROOT) / name).read_text(encoding="utf-8")
                    .replace("\r\n", "\n") for name in BUILD_SOURCES]
    expected = hashlib.sha256(json.dumps(source_texts, ensure_ascii=False,
                             separators=(",", ":")).encode()).hexdigest()
    revisions = set(re.findall(r'rev\s*=\s*"([0-9a-f]{40})"',
                               source_texts[-2]))
    if info.get("schema_version") != 1 or not info.get("hp_enabled"):
        raise ValueError("the executable lacks the required HP build identity")
    if len(revisions) != 1 or info.get("toolkit_revision") not in revisions:
        raise ValueError("the executable uses a different Toolkit revision")
    if info.get("implementation_digest") != expected:
        raise ValueError("the executable differs from these sources or Cargo.lock")
    if _ROOT_ACQUISITION == "independent" and not info.get("complete_positive_roots"):
        raise ValueError("independent roots require complete positive-root capability")
    if _PARALLEL_GL_ROOTS and not info.get("parallel_gl_roots", False):
        raise ValueError("the executable does not support native-Linux parallel GL roots")
    _BUILD_INFO, _BINARY_SHA256 = info, _sha256(_BIN)
    print("[PASS] executable matches the locked source and requested root capability",
          flush=True)
    return info


def _execution_policy():
    return {"parallel_gl_roots": _PARALLEL_GL_ROOTS,
            "capture_sector_gap_certificate": _SECTOR_GAP,
            "capture_maximum_stream_scalar_bytes": _STREAM_SCALAR_BYTES}


def _target_file(lsq, precision):
    directory, explicit = os.environ.get("XC_TARGET_SPEC_DIR"), os.environ.get("XC_TARGET_SPEC_FILE")
    if directory and explicit:
        raise ValueError("set only one of XC_TARGET_SPEC_DIR and XC_TARGET_SPEC_FILE")
    if not directory and not explicit:
        return None
    path = Path(directory) / f"c{lsq}-d{precision}.json" if directory else Path(explicit)
    if not path.is_file():
        raise ValueError(f"required exact target specification is missing: {path}")
    return str(path.resolve(strict=True))


def _external_input_binding(target_file, n_modes=None):
    """Hash source-dependent inputs without retaining secret-bearing recipes."""
    binding = {"target_sha256": _sha256(target_file) if target_file else None}
    if n_modes is not None and n_modes - min(n_modes, 64) > 1000:
        reference = os.environ.get("XC_ARITHMETIC_REFERENCE_JSON")
        identity_file = os.environ.get("XC_ARITHMETIC_REFERENCE_IDENTITY")
        if bool(reference) != bool(identity_file):
            raise ValueError("arithmetic reference requires both JSON and identity files")
        if reference:
            if not 0 < Path(reference).stat().st_size <= 64 * 1024 * 1024 or not 0 < Path(identity_file).stat().st_size <= 16 * 1024:
                raise ValueError("arithmetic reference exceeds input limits")
            identity = json.loads(Path(identity_file).read_text(encoding="utf-8"))
            digest = _sha256(reference)
            if (not isinstance(identity, dict) or identity.get("schema_version") != 1 or
                    identity.get("content_sha256") != digest or
                    not isinstance(identity.get("record_count"), int) or
                    isinstance(identity.get("record_count"), bool) or
                    identity["record_count"] < n_modes - min(n_modes, 64)):
                raise ValueError("arithmetic reference identity or prefix coverage mismatch")
            binding["arithmetic_reference_dataset"] = {"identity": identity,
                "json_sha256": digest, "identity_file_sha256": _sha256(identity_file)}
    for name in ("XC_RESEARCH_INPUTS_FILE", "XC_SMOOTH_NATIVE_HELPER", "XC_TARGET_PROVIDER_EXECUTABLE"):
        path = os.environ.get(name)
        if path:
            binding[name + "_sha256"] = _sha256(path)
    if os.environ.get("XC_RESEARCH_INPUTS"):
        binding["XC_RESEARCH_INPUTS_sha256"] = hashlib.sha256(os.environ["XC_RESEARCH_INPUTS"].encode()).hexdigest()
    recipe = os.environ.get("XC_RESEARCH_PREPARER")
    if recipe:
        configuration = json.loads(recipe)
        argv = configuration.get("argv", [])
        if not isinstance(argv, list) or not argv or not all(isinstance(arg, str) for arg in argv):
            raise ValueError("private preparer configuration has no valid argv")
        files = {}
        canonical_argv = list(argv)
        for index, arg in enumerate(argv):
            path = Path(shutil.which(arg) or arg) if index == 0 else Path(arg)
            if not path.is_file():
                continue
            files[f"argument_{index}"] = _sha256(path)
            # Frozen preparers may move between retry directories. Their
            # contents and flags determine identity; operational paths do not.
            canonical_argv[index] = {"file_sha256": files[f"argument_{index}"]}
            manifest = path.parent / "preparer-snapshot.json"
            if manifest.is_file():
                files[f"snapshot_{index}"] = _sha256(manifest)
                inventory = json.loads(manifest.read_text(encoding="utf-8")).get("files", {})
                for name, expected in sorted(inventory.items()):
                    member = (manifest.parent / name).resolve(strict=True)
                    try:
                        member.relative_to(manifest.parent.resolve())
                    except ValueError as error:
                        raise ValueError("preparer snapshot member escapes its source directory") from error
                    actual = _sha256(member)
                    if actual != expected:
                        raise ValueError(f"private preparer snapshot member changed: {name}")
                    files[f"snapshot_{index}/{name}"] = actual
        if "argument_0" not in files:
            raise ValueError("private preparer executable cannot be authenticated")
        canonical_configuration = dict(configuration, argv=canonical_argv)
        binding["preparer_configuration_sha256"] = hashlib.sha256(json.dumps(
            canonical_configuration, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False).encode()).hexdigest()
        binding["preparer_file_sha256"] = files
    return binding


def _journal_hashes(path):
    with open(path, encoding="utf-8") as stream:
        report = json.load(stream)
    directory = report.get("journal")
    if not directory:
        return {}
    root = Path(directory)
    required = ("request.json", "build.json", "measurements.json")
    for name in required:
        if not (root / name).is_file():
            raise ValueError(f"retained journal is missing {name}")
    # Bind every immutable top-level JSON receipt, including source joins and
    # qualification files; operational progress streams remain in their logs.
    return {p.name: _sha256(p) for p in sorted(root.glob("*.json"))}


def _publication_staging_binding():
    """Bind reuse to the campaign's retained publication closure, not just rows."""
    if os.environ.get("XC_PUBLISH_EXECUTE", "").lower() != "true":
        return None
    root = os.environ.get("XC_PUBLISH_STAGING_ROOT")
    if not root:
        raise ValueError("published row requires an explicit retained staging root")
    root = Path(root).resolve(strict=True)
    identities = set()
    for path in sorted((root / "drafts").rglob("draft.json")):
        path.resolve(strict=True).relative_to(root)
        draft = json.loads(path.read_text(encoding="utf-8"))
        manifest = draft["manifest"]
        identity = (manifest["artifact_family"], manifest["semantic_digest"], manifest["payload_digest"])
        if (not isinstance(identity[0], str) or not identity[0] or
                any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
                    for value in identity[1:])):
            raise ValueError("retained staging descriptor has an invalid canonical identity")
        identities.add(identity)
    if not identities:
        raise ValueError("published row has no retained authenticated staging candidates")
    return {"staging_root": str(root), "target": os.environ.get("XC_PUBLISH_TARGET"),
            "repository_owner": os.environ.get("XC_CACHE_REPOSITORY_OWNER"),
            "required_drafts": [list(identity) for identity in sorted(identities)]}


def _validate_publication_staging(retained, current):
    if retained is None or current is None:
        if retained != current:
            raise ValueError("retained row publication policy differs")
        return
    if any(retained.get(key) != current.get(key)
           for key in ("staging_root", "target", "repository_owner")):
        raise ValueError("retained row belongs to a different publication staging root or destination")
    required = retained.get("required_drafts")
    if not isinstance(required, list) or not required:
        raise ValueError("retained row lacks its publication artifact closure")
    available = {tuple(identity) for identity in current["required_drafts"]}
    if any(not isinstance(identity, list) or len(identity) != 3 or
           not all(isinstance(value, str) for value in identity) or
           tuple(identity) not in available for identity in required):
        raise ValueError("retained row publication artifact closure is missing from shared staging")


def _check_arithmetic_reference_binding(path, configuration):
    selected = configuration.get("external_inputs", {}).get("arithmetic_reference_dataset")
    with open(path, encoding="utf-8") as stream:
        report = json.load(stream)
    if not report.get("journal"):
        if selected is not None:
            raise ValueError("explicit arithmetic reference lacks a retained journal")
        return
    root = Path(report["journal"])
    identity = root / "arithmetic-reference-identity.json"
    ordinates = root / "arithmetic-reference-ordinates.json"
    if selected is None:
        if identity.exists() or ordinates.exists():
            raise ValueError("unexpected explicit arithmetic reference in retained journal")
        return
    retained = json.loads(identity.read_text(encoding="utf-8"))
    if retained.get("identity") != selected["identity"] or _sha256(ordinates) != selected["json_sha256"]:
        raise ValueError("retained arithmetic reference differs from the admitted source binding")


def _seal_execution(path, log_path, configuration):
    _check_arithmetic_reference_binding(path, configuration)
    receipt = {"schema_version": 1, "exit_code": 0,
               "build_info": _BUILD_INFO, "binary_sha256": _BINARY_SHA256,
               "configuration": configuration, "execution_policy": _execution_policy(),
               "report_sha256": _sha256(path), "log_sha256": _sha256(log_path),
               "journal_sha256": _journal_hashes(path),
               "publication_staging": _publication_staging_binding()}
    _write_json(path + ".execution.json", receipt)


def _validate_execution(path, configuration):
    _check_arithmetic_reference_binding(path, configuration)
    with open(path + ".execution.json", encoding="utf-8") as stream:
        receipt = json.load(stream)
    log_path = os.path.splitext(path)[0] + ".log"
    retained_staging = receipt.get("publication_staging")
    _validate_publication_staging(retained_staging, _publication_staging_binding())
    expected = {"schema_version": 1, "exit_code": 0,
                "build_info": _BUILD_INFO, "binary_sha256": _BINARY_SHA256,
                "configuration": configuration, "execution_policy": _execution_policy(),
                "report_sha256": _sha256(path), "log_sha256": _sha256(log_path),
                "journal_sha256": _journal_hashes(path),
                "publication_staging": retained_staging}
    if receipt != expected:
        raise ValueError("retained execution receipt, sources, policies, or file hashes differ")


def _check_report_build(report):
    if _BUILD_INFO is None or report.get("build_info") != _BUILD_INFO:
        raise ValueError("measurement does not bind to the verified executable")


def _check_ground_admission(report, path):
    if report.get("ground_index_policy") != _GROUND_INDEX_POLICY:
        raise ValueError("measurement ground-index policy does not match its request")
    admission = report.get("ground_index_admission", {})
    if not isinstance(admission.get("established"), bool):
        raise ValueError("measurement does not retain a ground-index admission outcome")
    if not admission["established"]:
        qualification = {"measurement": path, "reason": admission.get("reason"),
            "scope": "selected finite state; algebraic ground index not established"}
        if qualification not in _GROUND_QUALIFICATIONS:
            _GROUND_QUALIFICATIONS.append(qualification)
        if _GROUND_INDEX_POLICY == "require":
            _INTEGRITY_ISSUES.append(f"{path}: required algebraic ground index was not established")


def _applicability_artifact_binding(report):
    """Require the managed assessment itself in the retained publication closure."""
    manifest = report.get("capture_applicability_artifact")
    if not isinstance(manifest, dict) or not isinstance(manifest.get("key"), dict):
        raise ValueError("precision-control applicability lacks its managed artifact manifest")
    journal = Path(report["journal"])
    retained_manifest = json.loads((journal / "capture-applicability-artifact.json").read_text(encoding="utf-8"))
    payload_path = journal / "capture-applicability-record.json"
    if retained_manifest != manifest or _sha256(payload_path) != manifest.get("content_digest"):
        raise ValueError("retained precision-control applicability artifact changed")
    record = json.loads(payload_path.read_text(encoding="utf-8"))
    value = record.get("measurements", {}).get("paper3_capture_applicability", {}).get("value", {})
    if (value.get("schema_version") != 1 or
            value.get("semantics") != _APPLICABILITY_EVIDENCE or
            value.get("assessment") != report.get("capture_applicability") or
            value.get("raw_capture") != report.get("capture_receipt")):
        raise ValueError("managed applicability artifact does not bind the unchanged assessment and raw capture")
    binding = {"source_content_digest": manifest["content_digest"], "source_artifact_key": manifest["key"]}
    if os.environ.get("XC_PUBLISH_EXECUTE", "").lower() == "true":
        staging = _publication_staging_binding()
        root = Path(staging["staging_root"])
        identities = set()
        for path in (root / "drafts").rglob("draft.json"):
            path.resolve(strict=True).relative_to(root)
            draft = json.loads(path.read_text(encoding="utf-8"))
            if (draft.get("source_artifact_key") == manifest["key"] and
                    draft.get("source_content_digest") == manifest["content_digest"]):
                canonical = draft["manifest"]
                identities.add((canonical["artifact_family"], canonical["semantic_digest"], canonical["payload_digest"]))
        if len(identities) != 1 or list(next(iter(identities))) not in staging["required_drafts"]:
            raise ValueError("managed precision-control applicability artifact is missing or ambiguous in staging")
        binding["canonical_identity"] = list(next(iter(identities)))
    return binding


def _capture_coverage(report, path):
    raw = report.get("capture_complete")
    applicable = report.get("applicable_capture_complete")
    if (not isinstance(raw, bool) or report.get("all_requested_capture_complete") is not raw or
            not isinstance(applicable, bool) or
            report.get("precision_control_capture") is not _PRECISION_CONTROL_CAPTURE):
        raise ValueError("measurement does not preserve the requested and applicable capture scopes")
    outcomes = report.get("capture_receipt", {}).get("receipt", {}).get("outcomes", {})
    if not isinstance(outcomes, dict) or (report.get("research_capture") == "ultra" and not outcomes):
        raise ValueError("measurement has no complete raw capture outcome inventory")
    incomplete = {name: value for name, value in outcomes.items() if value.get("status") != "completed"}
    if raw and incomplete:
        raise ValueError("raw capture-complete flag disagrees with its unchanged receipt")
    qualified = {}
    if not _PRECISION_CONTROL_CAPTURE:
        if applicable != raw:
            raise ValueError("strict capture cannot qualify an incomplete raw receipt")
    else:
        configuration = {
            "lambda_squared": report["lambda_sq"], "n_modes": report["n_modes"],
            "precision_digits": report["precision_digits_requested"],
            "precision_bits": report["precision_bits_working"],
            "root_acquisition": _ROOT_ACQUISITION, "first_zero_index": _FIRST_ZERO_INDEX,
            "zero_count": report["zero_count_requested"], "parity_policy": _PARITY_POLICY,
            "eigenstate_solver": _EIGENSTATE_SOLVER, "ground_index_policy": _GROUND_INDEX_POLICY,
            "research_capture": _RESEARCH_CAPTURE, "capture_sector_gap_certificate": _SECTOR_GAP}
        allowed = {(13, 80, p) for p in (30, 45, 90, 180)} | {
            (50, 400, p) for p in (50, 100, 150, 200, 300)}
        if ((report["lambda_sq"], report["n_modes"], report["precision_digits_requested"]) not in allowed or
                (_ROOT_ACQUISITION, _FIRST_ZERO_INDEX, report["zero_count_requested"], _PARITY_POLICY,
                 _EIGENSTATE_SOLVER, _GROUND_INDEX_POLICY, _RESEARCH_CAPTURE, _SECTOR_GAP) !=
                ("seeded", 1, 5, "even-sector", "auto", "record-outcome", "ultra", False) or
                _RESEARCH_SECTOR_EIGENPAIRS != 8):
            raise ValueError("precision-control applicability is outside its exact declared configuration")
        assessment = report.get("capture_applicability", {})
        for key, expected in {"schema_version": 1, "policy": _APPLICABILITY_POLICY,
                "enabled": True, "configuration": configuration, "build_info": report["build_info"],
                "primary_sources": report["primary_sources"],
                "ground_index_admission": report["ground_index_admission"],
                "all_requested_capture_complete": raw, "applicable_capture_complete": applicable}.items():
            if assessment.get(key) != expected:
                raise ValueError(f"precision-control applicability has an incorrect {key} binding")
        qualified = assessment.get("qualified_diagnostics")
        if not isinstance(qualified, dict) or not report["primary_sources"]:
            raise ValueError("precision-control applicability lacks bound sources or qualifications")
        response_reason = ("invalid cache manifest: CCM response unresolved_near_crossing: source-matrix "
            f"eigenvalue intervals are not finitely separated at {report['precision_bits_working']} bits")
        for name, value in qualified.items():
            if (name not in {"evenness", "sector_analysis", "prime_power_response", "u_flow_response"} or
                    name not in incomplete or value.get("raw_outcome") != incomplete[name] or
                    value.get("classification") != "unavailable_at_stored_precision" or
                    not isinstance(value.get("basis"), str) or not value["basis"].strip()):
                raise ValueError("precision-control qualification does not match an allowed raw outcome")
            reason = incomplete[name].get("reason")
            expected_reason = (_ambiguous_sector_reason(reason, report["n_modes"] + 1)
                if name in {"evenness", "sector_analysis"} else reason == response_reason)
            if incomplete[name].get("status") != "failed" or not expected_reason:
                raise ValueError("precision-control qualification cannot exclude an unknown failure reason")
        unhandled = {name: value for name, value in incomplete.items() if name not in qualified}
        if assessment.get("unhandled_diagnostics") != unhandled:
            raise ValueError("precision-control applicability omits unhandled failures")
        if assessment.get("applied") is not bool(qualified):
            raise ValueError("precision-control applicability misstates whether exclusions were applied")
        if qualified and (report["ground_index_admission"].get("established") is not False or
                assessment.get("applied") is not True or not assessment.get("prerequisite_evidence")):
            raise ValueError("precision-control exclusions lack their source prerequisite assessment")
        if qualified:
            prerequisites = assessment["prerequisite_evidence"]
            if prerequisites.get("source_join_validated") is not True:
                raise ValueError("precision-control preparation source join was not validated")
            resolution = prerequisites.get("stored_state_resolution", {})
            reason = report["ground_index_admission"].get("reason")
            nonground = "claimed CCM eigenpair is not the algebraic ground state in the requested subspace"
            gap_floor = ("CCM stored precision resolution limit: selected-subspace gap is not separated "
                f"from the matrix rounding scale at {report['precision_bits_working']} bits")
            eligible_resolution = (
                reason == nonground and _source_below_storage_scale(report, resolution)
            ) or (
                reason == gap_floor and resolution.get("eigenvalue_resolution") in {
                    "resolved", "below_storage_floor", "stored_sign_unresolved"}
            ) or _clustered_ground_source(report, resolution, reason)
            if (not eligible_resolution or resolution.get("separation_unresolved_reason") != reason or
                    "selected_gap_lower" not in resolution or resolution["selected_gap_lower"] is not None or
                    "residual_angle_upper" not in resolution or resolution["residual_angle_upper"] is not None or
                    resolution != report.get("stored_state_resolution")):
                raise ValueError("precision-control ground refusal does not match a supported stored-precision limitation")
            if prerequisites.get("selected_eigenvalue") != report.get("selected_eigenvalue"):
                raise ValueError("precision-control selected eigenvalue source binding changed")
            for key, filename in (("input_preparation_status_sha256", "input-preparation-status.json"),
                    ("input_preparation_request_sha256", "input-preparation-request.json"),
                    ("prepared_research_inputs_sha256", "prepared-research-inputs.json")):
                if prerequisites.get(key) != _sha256(Path(report["journal"]) / filename):
                    raise ValueError("precision-control prerequisite evidence changed")
        if applicable and (unhandled or (not raw and not qualified)):
            raise ValueError("unhandled capture failures cannot become applicable capture success")
    artifact_binding = _applicability_artifact_binding(report) if _PRECISION_CONTROL_CAPTURE else None
    return {"measurement": path, "all_requested_capture_complete": raw,
            "applicable_capture_complete": applicable,
            "policy": _APPLICABILITY_POLICY if _PRECISION_CONTROL_CAPTURE else "strict-requested-capture",
            "qualified_diagnostics": qualified, "applicability_artifact": artifact_binding}


def _check_measurement_integrity(report, path):
    _check_ground_admission(report, path)
    expected_indices = list(range(report["first_zero_index"],
                                  report["first_zero_index"] + report["zero_count_requested"]))
    roots = report.get("roots", [])
    if [row.get("reference_index") for row in roots] != expected_indices:
        _INTEGRITY_ISSUES.append(f"{path}: requested root window is incomplete or reordered")
    for row in roots:
        digits = row.get("matching_digits_f64")
        if row.get("status") != "converged" or not isinstance(digits, (int, float)) or not math.isfinite(digits):
            _INTEGRITY_ISSUES.append(f"{path}: root {row.get('reference_index')} is unresolved")
    coverage = _capture_coverage(report, path)
    if coverage not in _CAPTURE_COVERAGE:
        _CAPTURE_COVERAGE.append(coverage)
    if not coverage["applicable_capture_complete"]:
        _INTEGRITY_ISSUES.append(f"{path}: applicable capture is incomplete; inspect retained receipt")


def _resume_candidates(result_path):
    # Identical requests inside `all` can reuse this invocation's sealed row too.
    current = [result_path] if os.path.exists(result_path) else []
    if not _RESUME or not _RESUME_DIR:
        return current
    basename = os.path.basename(result_path)
    root = Path(_RESUME_DIR).resolve(strict=True)
    paths = []
    for path in root.rglob(basename):
        try:
            path.resolve(strict=True).relative_to(root)
        except (OSError, ValueError):
            continue
        paths.append(str(path))
    return list(dict.fromkeys(current + sorted(paths)))

def _measurement_path(lsq, n, p, zero_count):
    name = (
        f"l2-{lsq}-n-{n}-p-{p}-"
        f"z-{_FIRST_ZERO_INDEX}-{zero_count}-"
        f"{_ROOT_ACQUISITION}-{_PARITY_POLICY}-{_EIGENSTATE_SOLVER}-"
        f"{_RESEARCH_CAPTURE}-e{_RESEARCH_SECTOR_EIGENPAIRS}.json"
    )
    return os.path.join(_RESULTS_DIR, "measurements", name)

def _load_measurement(path, lsq, n, p, zero_count):
    with open(path, "r", encoding="utf-8") as stream:
        report = json.load(stream)
    expected = {
        "lambda_sq": lsq,
        "n_modes": n,
        "precision_digits_requested": p,
        "first_zero_index": _FIRST_ZERO_INDEX,
        "zero_count_requested": zero_count,
        "root_acquisition": _ROOT_ACQUISITION,
        "parity_policy": _PARITY_POLICY,
        "eigenstate_solver": _EIGENSTATE_SOLVER,
        "ground_index_policy": _GROUND_INDEX_POLICY,
        "precision_control_capture": _PRECISION_CONTROL_CAPTURE,
        "research_capture": _RESEARCH_CAPTURE,
        "research_sector_eigenpairs": _RESEARCH_SECTOR_EIGENPAIRS,
        "comparison_semantics": (
            "reference-seeded-indexed-refinement"
            if _ROOT_ACQUISITION == "seeded"
            else "independent-positive-ordinal-comparison"
        ),
    }
    for field, value in expected.items():
        if report.get(field) != value:
            raise ValueError(
                f"{path}: {field} is {report.get(field)!r}, expected {value!r}"
            )
    _check_report_build(report)
    return report


def _measure_configuration(lsq, n, p, zero_count):
    return {"command": "measure", "lambda_sq": lsq, "n_modes": n,
            "precision_digits": p, "first_zero_index": _FIRST_ZERO_INDEX,
            "zero_count": zero_count, "root_acquisition": _ROOT_ACQUISITION,
            "parity_policy": _PARITY_POLICY, "eigenstate_solver": _EIGENSTATE_SOLVER,
            "ground_index_policy": _GROUND_INDEX_POLICY,
            "precision_control_capture": _PRECISION_CONTROL_CAPTURE,
            "research_capture": _RESEARCH_CAPTURE,
            "research_sector_eigenpairs": _RESEARCH_SECTOR_EIGENPAIRS}

def _selected_digits(report):
    for root in report["roots"]:
        if root["reference_index"] == _ANALYSIS_ZERO_INDEX:
            return root["matching_digits_f64"]
    return None

def measure(lsq, n, p, zero_count=None):
    """Measure a zero window and return D for the selected analysis ordinal."""
    # A finite N problem exposes at most N positive roots. Preserve as much of
    # the requested window as that configuration can represent; this keeps the
    # paper's N=2 and N=3 slope points valid while larger N points retain the
    # full multi-zero window.
    requested_zero_count = _ZERO_COUNT if zero_count is None else zero_count
    effective_zero_count = min(requested_zero_count, n - _FIRST_ZERO_INDEX + 1)
    if effective_zero_count < 1:
        raise ValueError("the requested reference window lies outside the finite root range")
    result_path = _measurement_path(lsq, n, p, effective_zero_count)
    configuration = _measure_configuration(lsq, n, p, effective_zero_count)
    target_file = _target_file(lsq, p)
    configuration["external_inputs"] = _external_input_binding(target_file, n)
    _INPUT_BINDINGS[f"c{lsq}-n{n}-d{p}"] = configuration["external_inputs"]
    log_path = os.path.splitext(result_path)[0] + ".log"
    os.makedirs(os.path.dirname(result_path), exist_ok=True)

    for retained_path in _resume_candidates(result_path):
        try:
            _validate_execution(retained_path, configuration)
            report = _load_measurement(
                retained_path, lsq, n, p, effective_zero_count
            )
            if not _capture_coverage(report, retained_path)["applicable_capture_complete"]:
                raise ValueError("retained applicable capture is incomplete")
            print(
                f"  [resume] L2={lsq}, N={n}, P={p}: "
                f"{retained_path}",
                flush=True,
            )
            _MEASUREMENTS.append(retained_path)
            _check_measurement_integrity(report, retained_path)
            return _selected_digits(report)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
            print(f"  [resume rejected] {error}; recomputing", flush=True)

    if os.path.exists(result_path):
        # A duplicate configuration in one invocation must never overwrite evidence.
        result_path = os.path.splitext(result_path)[0] + "-" + uuid.uuid4().hex + ".json"
        log_path = os.path.splitext(result_path)[0] + ".log"

    cmd = [_BIN, "measure",
           "--lambda-sq", str(lsq),
           "--n-modes", str(n),
           "--precision-digits", str(p),
           "--first-zero-index", str(_FIRST_ZERO_INDEX),
           "--zero-count", str(effective_zero_count),
           "--display-digits", "16",
           "--root-acquisition", _ROOT_ACQUISITION,
           "--parity-policy", _PARITY_POLICY,
           "--eigenstate-solver", _EIGENSTATE_SOLVER,
           "--ground-index-policy", _GROUND_INDEX_POLICY,
           "--research-capture", _RESEARCH_CAPTURE,
           "--research-sector-eigenpairs", str(_RESEARCH_SECTOR_EIGENPAIRS),
           "--capture-maximum-stream-scalar-bytes", str(_STREAM_SCALAR_BYTES),
           "--capture-output", os.path.splitext(result_path)[0] + "-capture",
           "--json-output", result_path]
    if _PARALLEL_GL_ROOTS:
        cmd.append("--parallel-gl-roots")
    if _SECTOR_GAP:
        cmd.append("--capture-sector-gap-certificate")
    if _PRECISION_CONTROL_CAPTURE:
        cmd.append("--precision-control-capture")
    _write_json(result_path + ".request.json", {"configuration": configuration,
                "execution_policy": _execution_policy(), "build_info": _BUILD_INFO,
                "binary_sha256": _BINARY_SHA256, "command": cmd})
    child_env = os.environ.copy()
    if n - min(n, 64) <= 1000:
        child_env.pop("XC_ARITHMETIC_REFERENCE_JSON", None)
        child_env.pop("XC_ARITHMETIC_REFERENCE_IDENTITY", None)
    child_env.pop("XC_TARGET_SPEC_DIR", None)
    if target_file:
        child_env["XC_TARGET_SPEC_FILE"] = target_file
    # Stage every artifact during a sweep, but execute remote publication only
    # once after the complete claim succeeds.
    if child_env.get("XC_PUBLISH_EXECUTE", "").lower() == "true":
        child_env["XC_PUBLISH_EXECUTE"] = "false"

    try:
        with open(log_path, "w", encoding="utf-8", buffering=1) as log:
            process = subprocess.Popen(
                cmd,
                cwd=REPO_ROOT,
                env=child_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert process.stdout is not None
            for line in process.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                log.write(line)
            return_code = process.wait()
    except FileNotFoundError:
        sys.exit(f"ERROR: binary not found at {_BIN}\n"
                 f"Build it first (inside WSL2 on Windows):\n"
                 f"    cargo build --release --features hp --locked")
    except KeyboardInterrupt:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        raise
    if return_code != 0:
        if os.path.isfile(result_path):
            try:
                report = _load_measurement(result_path, lsq, n, p, effective_zero_count)
                _MEASUREMENTS.append(result_path)
                _check_measurement_integrity(report, result_path)
            except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
                _INTEGRITY_ISSUES.append(f"failed-row report validation: {error}")
        _INTEGRITY_ISSUES.append(f"measurement exited {return_code}; inspect {log_path}")
        sys.exit(f"ERROR: measure failed for L2={lsq} N={n} P={p}")
    try:
        report = _load_measurement(result_path, lsq, n, p, effective_zero_count)
        digits = _selected_digits(report)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        sys.exit(f"ERROR: invalid structured result for L2={lsq} N={n} P={p}: {error}")
    _MEASUREMENTS.append(result_path)
    _check_measurement_integrity(report, result_path)
    if configuration["external_inputs"] != _external_input_binding(target_file, n):
        raise RuntimeError("external input or preparer binding changed during the measurement")
    _seal_execution(result_path, log_path, configuration)
    if digits is None:
        print(
            f"  [analysis unavailable] zero {_ANALYSIS_ZERO_INDEX} is outside "
            f"the finite root window retained at N={n}",
            flush=True,
        )
    return digits

def measure_evenness(lsq, n, p):
    """Measure natural-vs-forced evenness and return its structured record."""
    name = f"evenness-l2-{lsq}-n-{n}-p-{p}-{_EIGENSTATE_SOLVER}.json"
    result_path = os.path.join(_RESULTS_DIR, "measurements", name)
    log_path = os.path.splitext(result_path)[0] + ".log"
    os.makedirs(os.path.dirname(result_path), exist_ok=True)
    configuration = {"command": "measure-evenness", "lambda_sq": lsq,
                     "n_modes": n, "precision_digits": p,
                     "eigenstate_solver": _EIGENSTATE_SOLVER,
                     "ground_index_policy": _GROUND_INDEX_POLICY}

    for retained_path in _resume_candidates(result_path):
        try:
            _validate_execution(retained_path, configuration)
            with open(retained_path, "r", encoding="utf-8") as stream:
                report = json.load(stream)
            _check_report_build(report)
            if (
                report.get("lambda_sq") == lsq
                and report.get("n_modes") == n
                and report.get("precision_digits_requested") == p
                and report.get("eigenstate_solver") == _EIGENSTATE_SOLVER
                and report.get("ground_index_policy") == _GROUND_INDEX_POLICY
            ):
                print(f"  [resume] evenness L2={lsq}, N={n}, P={p}", flush=True)
                _MEASUREMENTS.append(retained_path)
                _check_ground_admission(report, retained_path)
                return report
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
            print(f"  [resume rejected] {error}; recomputing", flush=True)
    if os.path.exists(result_path):
        result_path = os.path.splitext(result_path)[0] + "-" + uuid.uuid4().hex + ".json"
        log_path = os.path.splitext(result_path)[0] + ".log"

    cmd = [
        _BIN,
        "measure-evenness",
        "--lambda-sq", str(lsq),
        "--n-modes", str(n),
        "--precision-digits", str(p),
        "--display-digits", "16",
        "--eigenstate-solver", _EIGENSTATE_SOLVER,
        "--ground-index-policy", _GROUND_INDEX_POLICY,
        "--capture-output", os.path.splitext(result_path)[0] + "-capture",
        "--json-output", result_path,
    ]
    _write_json(result_path + ".request.json", {"configuration": configuration,
                "execution_policy": _execution_policy(), "build_info": _BUILD_INFO,
                "binary_sha256": _BINARY_SHA256, "command": cmd})
    child_env = os.environ.copy()
    if child_env.get("XC_PUBLISH_EXECUTE", "").lower() == "true":
        child_env["XC_PUBLISH_EXECUTE"] = "false"
    with open(log_path, "w", encoding="utf-8", buffering=1) as log:
        process = subprocess.Popen(
            cmd,
            cwd=REPO_ROOT,
            env=child_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        try:
            for line in process.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                log.write(line)
            return_code = process.wait()
        except KeyboardInterrupt:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
            raise
    if return_code != 0:
        sys.exit(f"ERROR: evenness measurement failed for L2={lsq} N={n} P={p}")
    with open(result_path, "r", encoding="utf-8") as stream:
        report = json.load(stream)
    _check_report_build(report)
    for field, expected in (("lambda_sq", lsq), ("n_modes", n),
                            ("precision_digits_requested", p),
                            ("eigenstate_solver", _EIGENSTATE_SOLVER)):
        if report.get(field) != expected:
            raise ValueError(f"evenness measurement has incorrect {field}")
    _MEASUREMENTS.append(result_path)
    _check_ground_admission(report, result_path)
    _seal_execution(result_path, log_path, configuration)
    return report

# --------------------------------------------------------------------------
# Small stdlib fitting helpers
# --------------------------------------------------------------------------
def linfit(xs, ys):
    """Ordinary least squares y = a + b x. Returns (intercept a, slope b, R^2)."""
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b = sxy / sxx
    a = my - b * mx
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return a, b, r2

def fit_tanh_ramp(lsq, ns, ds):
    """
    Fit g = tanh((c N / S)^q) to the measured ramp ratios g = D / ceiling,
    by coarse-then-fine grid search. Returns (c, q, normalized RMSE).
    """
    S = shannon_number(lsq)
    ceil = matching_floor(lsq)
    pts = [(n, d / ceil) for n, d in zip(ns, ds)
           if d is not None and 0.02 < d / ceil < 0.999]
    if len(pts) < 3:
        return None, None, None

    def rms(c, q):
        e = 0.0
        for n, g in pts:
            model = math.tanh((c * n / S) ** q)
            e += (model - g) ** 2
        return e

    best = (None, None, float("inf"))
    # coarse pass
    c = 1.00
    while c <= 1.50001:
        q = 0.50
        while q <= 1.40001:
            e = rms(c, q)
            if e < best[2]:
                best = (c, q, e)
            q += 0.01
        c += 0.01
    # fine pass around the coarse optimum
    c0, q0 = best[0], best[1]
    best = (c0, q0, float("inf"))
    c = c0 - 0.02
    while c <= c0 + 0.02001:
        q = q0 - 0.02
        while q <= q0 + 0.02001:
            e = rms(c, q)
            if e < best[2]:
                best = (c, q, e)
            q += 0.002
        c += 0.002
    return best[0], best[1], math.sqrt(best[2] / len(pts))

# --------------------------------------------------------------------------
# Pretty printing
# --------------------------------------------------------------------------
def dstr(d, prec=3):
    """Format a possibly-None D value for a table cell."""
    return "N/A" if d is None else f"{d:.{prec}f}"

def verdict(condition):
    """Paper fits are validated for zero 1; higher ordinals are exploratory."""
    if _ANALYSIS_ZERO_INDEX != 1:
        result = "UNASSESSED"
    else:
        result = "PASS" if condition else "FAIL"
    _CHECKS.append({"scope": "finite empirical acceptance check",
                    "status": result,
                    "reason": "higher ordinal is exploratory" if _ANALYSIS_ZERO_INDEX != 1 else None})
    return result

def banner(title, claim, section, retained_zero_count=None):
    zero_count = _ZERO_COUNT if retained_zero_count is None else retained_zero_count
    print("=" * 74)
    print(f"  {claim}  |  {title}")
    print(f"  paper: {section}")
    print(
        f"  retained zero window: {_FIRST_ZERO_INDEX}.."
        f"{_FIRST_ZERO_INDEX + zero_count - 1}; "
        f"fit ordinal: {_ANALYSIS_ZERO_INDEX}"
    )
    if _ANALYSIS_ZERO_INDEX != 1:
        print("  NOTE: the paper's expected values are zero-1 baselines; this fit is exploratory.")
    print("=" * 74)

def server_note(desc):
    print(f"  [server-grade] {desc}")
    print(f"  Skipped under --quick. Re-run without --quick on a capable host.\n")

# --------------------------------------------------------------------------
# Claims
# --------------------------------------------------------------------------
def c2_precision_slope(quick):
    banner("Precision budget: D_Wprec = P + O(1), slope exactly 1",
           "C2", '"The precision budget"')
    lsq, n = 50, 400
    ps = [50, 100, 150, 200]
    slope_tolerance = 0.005
    minimum_r2 = 0.999
    print(f"  Isolating the precision budget at L2={lsq}, N={n} "
          f"(modes + prime ceiling held above P).\n")
    print(f"  {'P':>6}  {'D measured':>12}")
    xs, ys = [], []
    for p in ps:
        d = measure(lsq, n, p)
        print(f"  {p:>6}  {dstr(d):>12}")
        if d is not None:
            xs.append(p); ys.append(d)
    if len(xs) != len(ps):
        _INTEGRITY_ISSUES.append("C2 requires every planned precision row")
        return
    _, slope, r2 = linfit(xs, ys)
    _ANALYSIS.update({"precision_digits": xs, "matching_digits": ys,
                      "slope": slope, "r_squared": r2,
                      "slope_tolerance": slope_tolerance, "minimum_r_squared": minimum_r2})
    print(f"\n  measured slope dD/dP = {slope:.4f}   (R^2 = {r2:.5f})")
    print(f"  empirical acceptance = |slope - 1| <= {slope_tolerance:.3f} "
          f"and R^2 >= {minimum_r2:.3f}")
    print(f"  VERDICT: {verdict(abs(slope - 1.0) <= slope_tolerance and r2 >= minimum_r2)}\n")

def c1_budget_switch(quick):
    banner("Finite precision sweep: inspect a possible budget switch",
           "C1", '"The three-budget skeleton" (Prop. "The minimum is forced")')
    lsq, n = 13, 80
    ceil = matching_floor(lsq)
    ps = [30, 45, 90, 180]
    print(f"  Fixed L2={lsq}, N={n}. Prime ceiling D_Primes ~ {ceil:.1f}.")
    print(f"  Small P: precision binds (D ~ P). Large P: prime ceiling binds.\n")
    print(f"  {'P':>6}  {'D measured':>12}  binding budget")
    observations = []
    for p in ps:
        d = measure(lsq, n, p)
        observations.append({"precision_digits": p, "matching_digits": d})
        if d is None:
            print(f"  {p:>6}  {'N/A':>12}  (unresolved)")
            continue
        which = "precision" if d < ceil - 3 else "prime ceiling"
        print(f"  {p:>6}  {d:>12.3f}  {which}")
    _ANALYSIS.update({"observations": observations, "model_matching_floor": ceil})
    print("\n  This descriptive sweep records the response to precision.")
    print("  It does not establish a forced minimum or an asymptotic ceiling.")
    print("  VERDICT: UNASSESSED (no fixed quantitative acceptance criterion).\n")

def c3_floor_artifact(quick):
    banner("Precision-floor diagnostic: matching digits and evenness",
           "C3", '"Symmetry, positivity, and the precision floor"')
    lsq, n = 50, 400
    ceil = matching_floor(lsq)
    ps = [50, 150, 300]
    print(f"  L2={lsq}, N={n}. Model matching floor D_Primes ~ {ceil:.1f}.")
    print(f"  Below floor (P < ~{ceil:.0f}) the eigenvalue is unresolved and")
    print("  may be precision-limited; the recorded rows test that behavior.\n")
    print(f"  {'P':>6}  {'D measured':>12}  {'evenness dev.':>14}  {'signs':>13}  state")
    for p in ps:
        d = measure(lsq, n, p)
        evenness = measure_evenness(lsq, n, p)
        deviation = float(evenness["evenness_deviation"])
        signs = f"{evenness['natural_sign']}/{evenness['forced_even_sign']}"
        if d is None:
            print(
                f"  {p:>6}  {'N/A':>12}  {deviation:>14.3e}  "
                f"{signs:>13}  unresolved"
            )
            continue
        state = "precision-starved (D~P)" if d < ceil - 3 else "floor recovered"
        print(
            f"  {p:>6}  {d:>12.3f}  {deviation:>14.3e}  "
            f"{signs:>13}  {state}"
        )
    print("\n  This run records natural-vs-forced eigenvalues, signs, and reflection")
    print("  deviation at every precision. The broader 38-configuration analysis")
    print("  is documented in the independent reproduction. No fixed quantitative")
    print("  acceptance criterion is applied to this descriptive diagnostic:")
    print(f"    github.com/TeamXcelerator/ccm-reproduction-and-convergence\n")

def c7_archimedean_slope(quick):
    banner("Archimedean leading rate: slope = pi^2 / (ln10 ln L2) at L2=7",
           "C7", '"The archimedean leading rate"', retained_zero_count=1)
    lsq = 7
    # Initial-slope window matching the paper: N in [2, 0.25*Shannon], min 8.
    S = shannon_number(lsq)
    nmax = min(max(8, int(0.25 * S)), 30)
    ns = list(range(2, nmax + 1))
    p = 200
    print(f"  Small-N initial-slope window N in [2,{nmax}] at L2={lsq} "
          f"(few primes, q ~ 1), P={p}.\n")
    print(f"  {'N':>6}  {'D measured':>12}")
    xs, ys = [], []
    for n in ns:
        d = measure(lsq, n, p, zero_count=1)
        print(f"  {n:>6}  {dstr(d):>12}")
        if d is not None:
            xs.append(n); ys.append(d)
    if len(xs) < 3:
        _INTEGRITY_ISSUES.append("C7 has too few resolved points to fit its planned slope")
        print("\n  Too few converged points to fit a slope.\n")
        return
    _, slope, r2 = linfit(xs, ys)
    pred = archimedean_slope(lsq)
    print(f"\n  fit window actually used: N = {xs[0]}..{xs[-1]}")
    print(f"  measured initial slope dD/dN = {slope:.3f}   (R^2 = {r2:.4f})")
    print(f"  predicted pi^2/(ln10 ln7)    = {pred:.3f}   (parameter-free)")
    print(f"  paper reports                ~ 2.264  (3% match, using N=2,3 too)")
    _ANALYSIS.update({"n_modes": xs, "matching_digits": ys, "slope": slope,
                      "r_squared": r2, "predicted_slope": pred,
                      "relative_tolerance": 0.15,
                      "historical_reported_relative_difference": 0.03})
    if xs != ns:
        _INTEGRITY_ISSUES.append("C7 requires every planned N row, including N=2 and N=3")
        print("  INCOMPLETE: missing planned rows; no full-grid verdict is issued.")
        return
    print(f"  VERDICT: {verdict(abs(slope - pred) / pred < 0.15)}\n")

# per-L2 ramp grids: (lsq, [N values], P, server?)
# N is capped near ~1.3*Shannon. The tanh ceiling is known analytically from
# D_Primes, so points past the knee (g >~ 0.9) cost the most (the HP eigensolve
# is ~O(N^3)) yet add almost nothing to the q/c fit. Covering g ~ 0.1-0.9 pins
# both q and c. The executable reproduction grid stops at lambda^2=100 because
# the paper does not preserve the exact configurations behind its lambda^2=150
# and lambda^2=200 fit rows. Those rows remain reference values only until their
# provenance is established.
_RAMP_GRID = [
    (7,   [3, 5, 7, 9, 11, 13, 15, 18],            200, False),
    (13,  [7, 11, 16, 21, 27, 33, 39, 44],         200, False),
    (20,  [12, 20, 28, 38, 48, 58, 68, 78],        300, False),
    (25,  [16, 28, 40, 55, 70, 85, 98, 108],       300, False),
    (50,  [40, 70, 105, 140, 175, 210, 240, 260],  500, True),
    (100, [90, 170, 250, 330, 410, 490, 560, 620], 700, True),
]
# Paper fit-table (tab:q) reference values
_TABLE1_Q = {7: 1.185, 13: 0.985, 20: 0.900, 25: 0.880, 50: 0.835, 100: 0.785, 150: 0.760, 200: 0.805}
_TABLE1_C = {7: 1.20, 13: 1.25, 20: 1.28, 25: 1.29, 50: 1.31, 100: 1.28, 150: 1.26, 200: 1.31}
_MODE_RAMP_CACHE = {}

def collect_mode_ramp_fits(quick):
    """Run the shared C4/C8/C9 grid once and return per-cutoff fit records."""
    key = (
        quick,
        _BIN,
        _FIRST_ZERO_INDEX,
        _ROOT_ACQUISITION,
        _PARITY_POLICY,
        _EIGENSTATE_SOLVER,
        _GROUND_INDEX_POLICY,
        _RESEARCH_CAPTURE,
        _RESEARCH_SECTOR_EIGENPAIRS,
        _RESULTS_DIR,
        json.dumps({f"c{c}-d{p}": _external_input_binding(_target_file(c, p))
                    for c, _, p, server in _RAMP_GRID if not (quick and server)}, sort_keys=True),
    )
    cached = _MODE_RAMP_CACHE.get(key)
    if cached is not None:
        rows, measurement_paths, issues = cached
        _MEASUREMENTS.extend(measurement_paths)
        _INTEGRITY_ISSUES.extend(issues)
        for path in measurement_paths:
            with open(path, encoding="utf-8") as stream:
                _check_measurement_integrity(json.load(stream), path)
        print("  Reusing the shared C4/C8/C9 measurements collected in this process.\n")
        return rows

    first_measurement = len(_MEASUREMENTS)
    first_issue = len(_INTEGRITY_ISSUES)
    rows = []
    for lsq, ns, p, server in _RAMP_GRID:
        if quick and server:
            continue
        print(f"  -- L2={lsq}: ramping N up to {ns[-1]} at P={p} "
              f"(Shannon S = {shannon_number(lsq):.1f}) ...", flush=True)
        ds = [measure(lsq, n, p, zero_count=1) for n in ns]
        c, q, rmse = fit_tanh_ramp(lsq, ns, ds)
        if c is None:
            _INTEGRITY_ISSUES.append(f"L2={lsq}: insufficient resolved transition points for the planned fit")
            print("     not enough in-ramp points; skipping fit.", flush=True)
            continue
        rows.append((lsq, q, c, rmse))
        print(f"     -> q={q:.3f} (paper {_TABLE1_Q.get(lsq, float('nan')):.3f}, "
              f"formula {q_formula(lsq):.3f}), c={c:.3f}, normalized RMSE={rmse:.4f}",
              flush=True)

    measurement_paths = tuple(_MEASUREMENTS[first_measurement:])
    _MODE_RAMP_CACHE[key] = (tuple(rows), measurement_paths,
                           tuple(_INTEGRITY_ISSUES[first_issue:]))
    return rows

def c4_nmode_ramp(quick):
    banner("Mode budget follows a normalized tanh ramp",
           "C4", '"The mode budget"', retained_zero_count=1)
    rows = collect_mode_ramp_fits(quick)
    if not rows:
        return
    print(f"\n  {'L2':>5}  {'q fit':>8}  {'c fit':>8}  {'norm RMSE':>10}")
    for lsq, q, c, rmse in rows:
        print(f"  {lsq:>5}  {q:>8.3f}  {c:>8.3f}  {rmse:>10.4f}")
    maximum_rmse = max(rmse for _, _, _, rmse in rows)
    _ANALYSIS.update({"fits": rows, "maximum_normalized_rmse": maximum_rmse,
                      "maximum_allowed_rmse": 0.05})
    print("\n  Expected: each normalized transition is described by")
    print("    g(N) = tanh((c N / (lambda^2 log(lambda^2)))^q)")
    print(f"  maximum normalized RMSE = {maximum_rmse:.4f}")
    print(f"  VERDICT: {verdict(maximum_rmse <= 0.05)}\n")

def c8_mode_exponent(quick):
    banner("Mode exponent follows q(lambda^2)",
           "C8", '"The mode exponent"', retained_zero_count=1)
    rows = collect_mode_ramp_fits(quick)
    if not rows:
        return
    print(f"\n  {'L2':>5}  {'q meas':>8}  {'q paper':>8}  {'q form':>8}")
    for lsq, q, _, _ in rows:
        print(f"  {lsq:>5}  {q:>8.3f}  {_TABLE1_Q.get(lsq, float('nan')):>8.3f}  "
              f"{q_formula(lsq):>8.3f}")
    if len(rows) >= 3:
        regression_rows = [row for row in rows if row[0] != 200]
        xs = [math.log(math.log(lsq)) for lsq, _, _, _ in regression_rows]
        ys = [1.0 / q for _, q, _, _ in regression_rows]
        c0, c1, r2 = linfit(xs, ys)
        _ANALYSIS.update({"fits": rows, "intercept": c0, "slope": c1,
                          "r_squared": r2, "coefficient_tolerance": 0.12})
        print(f"\n  regression 1/q = c0 + c1 lnln(L2):")
        print(f"    c0 = {c0:.3f}  (gamma   = {GAMMA:.3f})")
        print(f"    c1 = {c1:.3f}  (1/2     = 0.500)")
        print(f"    R^2 = {r2:.3f}  (paper reports 0.98)")
        ok = abs(c0 - GAMMA) < 0.12 and abs(c1 - 0.5) < 0.12
        print(f"  VERDICT (q-law): {verdict(ok)}\n")

def c9_onset_constant(quick):
    banner("Mode-ramp onset constant clusters near 4/pi",
           "C9", '"The onset constant"', retained_zero_count=1)
    rows = collect_mode_ramp_fits(quick)
    if not rows:
        return
    print(f"\n  {'L2':>5}  {'c meas':>8}  {'c paper':>8}  {'4/pi':>8}")
    for lsq, _, c, _ in rows:
        print(f"  {lsq:>5}  {c:>8.3f}  {_TABLE1_C.get(lsq, float('nan')):>8.3f}  "
              f"{4/math.pi:>8.3f}")
    cs = [c for _, _, c, _ in rows]
    cmean = sum(cs) / len(cs)
    _ANALYSIS.update({"fits": rows, "mean_onset": cmean,
                      "expected_onset": 4 / math.pi, "absolute_tolerance": 0.1})
    print(f"\n  mean onset c = {cmean:.3f}; expected 4/pi = {4/math.pi:.3f}")
    print(f"  VERDICT: {verdict(abs(cmean - 4/math.pi) < 0.1)}\n")

def c10_shannon(quick):
    banner("Shannon coordinate: saturation at N/(L2 ln L2) ~ 2.0-2.3",
           "C10", '"The Shannon coordinate" (Lem. "Coordinate from ceiling over slope")')
    if quick:
        server_note("L2=100 ramp to saturation (N up to ~1200, HP-700).")
        return
    lsq, p = 100, 700
    S = shannon_number(lsq)
    ceil = matching_floor(lsq)
    ns = list(range(100, 1300, 100))
    print(f"  L2={lsq}, P={p}. Shannon S = {S:.1f}, ceiling ~ {ceil:.1f}.\n")
    print(f"  {'N':>6}  {'D':>10}  {'g=D/ceil':>10}  {'N/S':>8}")
    n_near = None
    n_full = None
    for n in ns:
        d = measure(lsq, n, p)
        if d is None:
            print(f"  {n:>6}  {'N/A':>10}  {'-':>10}  {n / S:>8.3f}")
            continue
        g = d / ceil
        print(f"  {n:>6}  {d:>10.2f}  {g:>10.3f}  {n / S:>8.3f}")
        if n_near is None and g >= 0.98:
            n_near = n
        if n_full is None and g >= 0.999:
            n_full = n
    if n_near:
        _ANALYSIS.update({"near_saturation_n": n_near, "full_saturation_n": n_full,
                          "shannon_number": S, "acceptance_interval": [1.8, 2.6]})
        print(f"\n  practical saturation (g>=0.98): N/S = {n_near / S:.2f}")
        if n_full:
            print(f"  full numerical plateau (g>=0.999): N/S = {n_full / S:.2f}")
        print("  paper's practical-saturation band: 2.0-2.3")
        print(f"  VERDICT: {verdict(1.8 <= n_near / S <= 2.6)}\n")
    else:
        _ANALYSIS.update({"near_saturation_n": None, "full_saturation_n": n_full})
        print(f"  VERDICT: {verdict(False)} (no saturation on the planned grid)\n")

def c11_prime_anchor(quick):
    banner("Prime ceiling anchor: D_Primes(100) = 526.08",
           "C11", '"The prime ceiling"')
    if quick:
        server_note("single saturated floor run at L2=100, N=1000, HP-700 (~20-40 min).")
        return
    lsq, n, p = 100, 1000, 700
    d = measure(lsq, n, p)
    _ANALYSIS.update({"matching_digits": d, "historical_value": 526.08,
                      "absolute_tolerance": 3})
    print(f"  L2={lsq}, N={n}, P={p} (both N and P above floor).\n")
    print(f"  D measured            = {dstr(d, 2)}")
    print(f"  paper reports         = 526.08")
    print(f"  matching-floor formula = {matching_floor(lsq):.2f}  (K L2 - 5 log10 L2 - 9.5)")
    print(f"  K = 4 pi / ln10        = {K:.5f}  (exact, parameter-free)")
    print(f"  VERDICT: {verdict(d is not None and abs(d - 526.08) < 3)}\n")

def c12_matching_floor(quick):
    banner("Matching floor / two-floor structure: D_Primes(200) ~ 1070.4",
           "C12", '"The prime ceiling"')
    if quick:
        server_note("L2=200, N>=2400, HP-1250 -- multi-hour, large memory.")
        return
    lsq, p = 200, 1250
    print(f"  L2={lsq}, P={p}, N>=2400 (saturated).\n")
    print(f"  {'N':>6}  {'D':>10}")
    d = None
    for n in [2400, 2800]:
        d = measure(lsq, n, p)
        print(f"  {n:>6}  {dstr(d, 2):>10}")
    mf = matching_floor(lsq)
    ef = eigenvalue_floor(lsq)
    _ANALYSIS.update({"last_matching_digits": d, "model_matching_floor": mf,
                      "model_eigenvalue_floor": ef, "absolute_tolerance": 3})
    print(f"\n  matching floor  K L2 - 5 log10 L2 - 9.5      = {mf:.2f}")
    print(f"  eigenvalue floor K L2 - 4.5 log10 L2 - C0    = {ef:.2f}")
    print(f"  two-floor gap (conv)                         = {ef - mf:.2f}")
    print(f"  paper reports D_Primes(200) ~ 1070.4, matching floor 1070.5")
    print(f"  VERDICT: {verdict(d is not None and abs(d - mf) < 3)}\n")

def c13_prime_smooth(quick):
    banner("Prime ceiling is smooth, not a staircase (~5.3 digits / unit L2)",
           "C13", '"The prime ceiling"')
    n, p = 300, 200
    hi = 16 if quick else 31
    lsqs = list(range(4, hi))
    print(f"  N={n}, P={p} (above floor). Unit steps in L2 from 4 to {hi - 1}.\n")
    print(f"  {'L2':>5}  {'D':>10}  {'dD':>8}  prime-power entry?")
    prev = None
    deltas = []
    grouped_deltas = {"prime-power entry": [], "ordinary entry": []}
    primeish = {4, 8, 9, 16, 25, 27}  # sample prime-power thresholds in range
    for lsq in lsqs:
        d = measure(lsq, n, p)
        if d is None:
            print(f"  {lsq:>5}  {'N/A':>10}  {'-':>8}  unresolved")
            continue
        dd = "" if prev is None else f"{d - prev:.2f}"
        if prev is not None:
            deltas.append(d - prev)
        is_pp = "yes" if (lsq in primeish or _is_prime(lsq)) else "no"
        if prev is not None:
            group = "prime-power entry" if is_pp == "yes" else "ordinary entry"
            grouped_deltas[group].append(d - prev)
        print(f"  {lsq:>5}  {d:>10.2f}  {dd:>8}  {is_pp}")
        prev = d
    if deltas:
        mean = sum(deltas) / len(deltas)
        _ANALYSIS.update({"increments": deltas, "mean_increment": mean,
                          "groups": grouped_deltas, "acceptance_interval": [4.5, 6.0]})
        print(f"\n  mean rise per unit L2 = {mean:.2f} digits   (paper ~5.3)")
        for label, values in grouped_deltas.items():
            if values:
                group_mean = sum(values) / len(values)
                variance = sum((value - group_mean) ** 2 for value in values) / len(values)
                print(
                    f"  {label:>18}: n={len(values):>2}, "
                    f"mean={group_mean:.3f}, sd={math.sqrt(variance):.3f}"
                )
        print("  The grouped statistics expose rather than assume any staircase effect.")
        print(f"  VERDICT: {verdict(4.5 <= mean <= 6.0)}\n")

def c14_bottleneck(quick):
    banner("Finite plateau comparison at fixed cutoff",
           "C14", '"The complete formula" (Prop. "Convergence criterion and the prime bottleneck")')
    lsq = 13
    ceil = matching_floor(lsq)
    grid = [(40, 100), (80, 200), (120, 400), (200, 800)]
    print(f"  Fixed L2={lsq}. Increase N and P; compare with the model floor ~ {ceil:.1f}.\n")
    print(f"  {'N':>6}  {'P':>6}  {'D':>10}")
    last = None
    for n, p in grid:
        d = measure(lsq, n, p)
        print(f"  {n:>6}  {p:>6}  {dstr(d, 2):>10}")
        if d is not None:
            last = d
    _ANALYSIS.update({"last_matching_digits": last, "model_matching_floor": ceil,
                      "absolute_tolerance": 4})
    print("\n  The check compares the last finite row with the model floor.")
    print("  A supremum over all N and P or a necessary convergence condition")
    print("  is not established by these four rows; those statements remain unassessed.")
    print(f"  VERDICT: {verdict(last is not None and abs(last - ceil) < 4)}\n")

def _is_prime(m):
    if m < 2:
        return False
    for i in range(2, int(m**0.5) + 1):
        if m % i == 0:
            return False
    return True

# --------------------------------------------------------------------------
# Dispatch
# --------------------------------------------------------------------------
CLAIMS = {
    "precision-slope": c2_precision_slope,
    "budget-switch": c1_budget_switch,
    "floor-artifact": c3_floor_artifact,
    "nmode-ramp": c4_nmode_ramp,
    "archimedean-slope": c7_archimedean_slope,
    "mode-exponent": c8_mode_exponent,
    "onset-constant": c9_onset_constant,
    "shannon": c10_shannon,
    "prime-anchor": c11_prime_anchor,
    "matching-floor": c12_matching_floor,
    "prime-smooth": c13_prime_smooth,
    "bottleneck": c14_bottleneck,
}
# Sensible run order for `all` (paper order)
ALL_ORDER = ["budget-switch", "precision-slope", "floor-artifact", "nmode-ramp",
             "archimedean-slope", "mode-exponent", "onset-constant", "shannon",
             "prime-anchor", "matching-floor", "prime-smooth", "bottleneck"]

def configuration_grid(claim, quick=False):
    """Published executable grid; analytical claims C5/C6 have no wrapper."""
    if claim in {"nmode-ramp", "mode-exponent", "onset-constant"}:
        return [{"lambda_sq": c, "n_modes": n, "precision_digits": p, "zero_count": 1}
                for c, ns, p, server in _RAMP_GRID if not (quick and server) for n in ns]
    grids = {
        "budget-switch": [(13, 80, p) for p in (30, 45, 90, 180)],
        "precision-slope": [(50, 400, p) for p in (50, 100, 150, 200)],
        "floor-artifact": [(50, 400, p) for p in (50, 150, 300)],
        "archimedean-slope": [(7, n, 200) for n in range(2, 9)],
        "shannon": [] if quick else [(100, n, 700) for n in range(100, 1300, 100)],
        "prime-anchor": [] if quick else [(100, 1000, 700)],
        "matching-floor": [] if quick else [(200, n, 1250) for n in (2400, 2800)],
        "prime-smooth": [(c, 300, 200) for c in range(4, 16 if quick else 31)],
        "bottleneck": [(13, n, p) for n, p in ((40, 100), (80, 200), (120, 400), (200, 800))],
    }
    result = []
    for c, n, p in grids[claim]:
        count = 1 if claim == "archimedean-slope" else min(_ZERO_COUNT, n - _FIRST_ZERO_INDEX + 1)
        result.append({"lambda_sq": c, "n_modes": n, "precision_digits": p, "zero_count": count})
    return result


def _validate_planned_measurements(claim, quick):
    expected = configuration_grid(claim, quick)
    observed, evenness = [], []
    for path in dict.fromkeys(_MEASUREMENTS):
        with open(path, encoding="utf-8") as stream:
            report = json.load(stream)
        row = {"lambda_sq": report["lambda_sq"], "n_modes": report["n_modes"],
               "precision_digits": report["precision_digits_requested"]}
        if "roots" in report:
            row["zero_count"] = report["zero_count_requested"]
            observed.append(row)
        else:
            evenness.append(row)
    if observed != expected:
        _INTEGRITY_ISSUES.append("retained measurements do not match the complete ordered planned grid")
    expected_evenness = [{k: v for k, v in row.items() if k != "zero_count"} for row in expected]
    if (claim == "floor-artifact" and evenness != expected_evenness) or (claim != "floor-artifact" and evenness):
        _INTEGRITY_ISSUES.append("retained evenness measurements do not match the planned grid")


def _write_claim_summary(claim, started_at, execution_integrity, publication, quick, error=None):
    os.makedirs(os.path.join(_RESULTS_DIR, "claims"), exist_ok=True)
    zero_count = (
        1
        if claim in {
            "nmode-ramp",
            "archimedean-slope",
            "mode-exponent",
            "onset-constant",
        }
        else _ZERO_COUNT
    )
    summary = {
        "schema_version": 2,
        "claim": claim,
        "execution_integrity": execution_integrity,
        "claim_complete": execution_integrity == "PASS" and not quick,
        "capture_complete": bool(_CAPTURE_COVERAGE) and all(row["all_requested_capture_complete"] for row in _CAPTURE_COVERAGE),
        "all_requested_capture_complete": bool(_CAPTURE_COVERAGE) and all(row["all_requested_capture_complete"] for row in _CAPTURE_COVERAGE),
        "applicable_capture_complete": bool(_CAPTURE_COVERAGE) and all(row["applicable_capture_complete"] for row in _CAPTURE_COVERAGE),
        "precision_control_capture": _PRECISION_CONTROL_CAPTURE,
        "capture_coverage": list(_CAPTURE_COVERAGE),
        "hypothesis_verdict": (
            "UNASSESSED" if execution_integrity != "PASS" or quick or not _CHECKS
            or _GROUND_QUALIFICATIONS
            else "FAIL" if any(check["status"] == "FAIL" for check in _CHECKS)
            else "UNASSESSED" if any(check["status"] == "UNASSESSED" for check in _CHECKS)
            else "PASS"),
        "hypothesis_scope": "finite empirical checks on the declared grid; no asymptotic proof or necessity claim",
        "ground_index_policy": _GROUND_INDEX_POLICY,
        "ground_index_qualifications": list(_GROUND_QUALIFICATIONS),
        "quick_subset": quick,
        "build_info": _BUILD_INFO,
        "binary_sha256": _BINARY_SHA256,
        "configuration_grid": configuration_grid(claim, quick),
        "execution_policy": _execution_policy(),
        "external_input_bindings": dict(_INPUT_BINDINGS),
        "checks": list(_CHECKS),
        "analysis": dict(_ANALYSIS),
        "integrity_issues": list(dict.fromkeys(_INTEGRITY_ISSUES)),
        "error": error,
        "publication": publication,
        "started_unix_seconds": started_at,
        "finished_unix_seconds": time.time(),
        "first_zero_index": _FIRST_ZERO_INDEX,
        "zero_count": zero_count,
        "analysis_zero_index": _ANALYSIS_ZERO_INDEX,
        "root_acquisition": _ROOT_ACQUISITION,
        "parity_policy": _PARITY_POLICY,
        "eigenstate_solver": _EIGENSTATE_SOLVER,
        "research_capture": _RESEARCH_CAPTURE,
        "research_sector_eigenpairs": _RESEARCH_SECTOR_EIGENPAIRS,
        "measurement_files": list(dict.fromkeys(_MEASUREMENTS)),
        "measurement_sha256": {path: _sha256(path) for path in dict.fromkeys(_MEASUREMENTS)},
        "measurement_execution_sha256": {path: _sha256(path + ".execution.json")
            for path in dict.fromkeys(_MEASUREMENTS) if os.path.isfile(path + ".execution.json")},
    }
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(started_at))
    path = os.path.join(_RESULTS_DIR, "claims", f"{claim}-{stamp}-{_INVOCATION_ID}.json")
    _write_json(path, summary)
    print(f"\n  Claim summary: {path}", flush=True)
    print(f"  Execution integrity: {execution_integrity}; finite hypothesis: {summary['hypothesis_verdict']}", flush=True)
    return summary

def _finalize_publication():
    if os.environ.get("XC_PUBLISH_EXECUTE", "").lower() != "true":
        return {"status": "not_requested"}
    retained_bindings = []
    staging_before = _publication_staging_binding()
    for path in dict.fromkeys(_MEASUREMENTS):
        with open(path + ".execution.json", encoding="utf-8") as stream:
            receipt = json.load(stream)
        if receipt.get("report_sha256") != _sha256(path):
            raise ValueError("measurement changed before publication")
        retained = receipt.get("publication_staging")
        _validate_publication_staging(retained, staging_before)
        retained_bindings.append(retained)
    print("\n  Finalizing staged publication once for the complete claim ...", flush=True)
    result = subprocess.run(
        [_BIN, "finalize-publication"],
        cwd=REPO_ROOT,
        env=os.environ.copy(),
    )
    if result.returncode != 0:
        raise RuntimeError(f"staged artifact publication exited {result.returncode}; retain staging and logs")
    root = os.environ.get("XC_PUBLISH_STAGING_ROOT")
    if not root:
        raise RuntimeError("publication lacks an explicit staging root for verification")
    report_path = os.path.join(root, "publication-execution-report.json")
    with open(report_path, encoding="utf-8") as stream:
        report = json.load(stream)
    phases = report.get("phases", [])
    if (report.get("all_completed") is not True or not phases
            or phases[-1].get("all_completed") is not True
            or any(row.get("completed") is not True for row in report.get("transactions", []))):
        raise RuntimeError("publication report does not verify every eligible destination")
    inventory_path = Path(root) / "publication-inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    entries = inventory.get("entries", [])
    if (inventory.get("target") != os.environ.get("XC_PUBLISH_TARGET") or not entries or
            inventory.get("ready_for_remote_execution") is not True or
            any(entry.get("assurance_eligible") is not True for entry in entries)):
        raise RuntimeError("publication inventory does not establish the requested eligible destination")
    covered = {(entry["family"], entry["semantic_digest"], entry["payload_digest"]) for entry in entries}
    for retained in [staging_before] + retained_bindings:
        if any(tuple(identity) not in covered for identity in retained["required_drafts"]):
            raise RuntimeError("publication inventory omits a retained measurement artifact")
    # Shared staging continues to grow between claims. Copy the complete proof
    # now, so earlier summaries never depend on mutable cumulative report paths.
    snapshot = Path(_RESULTS_DIR) / "publication" / uuid.uuid4().hex
    snapshot.mkdir(parents=True, exist_ok=False)
    files = {"publication-execution-report.json": Path(report_path),
             "publication-inventory.json": inventory_path}
    for phase in phases:
        relative = Path(phase["relative_report_path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("publication phase path escapes its retained root")
        source = (Path(root) / relative).resolve(strict=True)
        source.relative_to(Path(root).resolve(strict=True))
        files[str(relative)] = source
    hashes = {}
    for relative, source in sorted(files.items()):
        destination = snapshot / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        with source.open("rb") as reader, destination.open("xb") as writer:
            shutil.copyfileobj(reader, writer)
        hashes[relative] = _sha256(destination)
    return {"status": "finalized", "report": str(snapshot / "publication-execution-report.json"),
            "report_sha256": hashes["publication-execution-report.json"],
            "inventory": str(snapshot / "publication-inventory.json"),
            "inventory_sha256": hashes["publication-inventory.json"],
            "evidence_sha256": hashes, "staging_root": str(Path(root).resolve()),
            "target": os.environ.get("XC_PUBLISH_TARGET")}

def _failed_publication_evidence(exception):
    """Preserve a failed attempt without treating older cumulative reports as success."""
    root = os.environ.get("XC_PUBLISH_STAGING_ROOT")
    result = {"status": "failed", "error": f"{type(exception).__name__}: {exception}",
              "target": os.environ.get("XC_PUBLISH_TARGET"), "staging_root": root,
              "evidence": {}}
    if not root:
        return result
    snapshot = Path(_RESULTS_DIR) / "publication" / ("failed-" + uuid.uuid4().hex)
    try:
        for relative in ("journals/publication-operational-summary.json",
                         "publication-execution-report.json", "publication-inventory.json"):
            source = Path(root) / relative
            if not source.is_file():
                continue
            destination = snapshot / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            with source.open("rb") as reader, destination.open("xb") as writer:
                shutil.copyfileobj(reader, writer)
            result["evidence"][relative] = {"path": str(destination), "sha256": _sha256(destination)}
    except OSError as retention_error:
        # Evidence retention must not replace the original publication failure.
        result["evidence_retention_error"] = str(retention_error)
    return result


def _run_claim(name, quick):
    global _MEASUREMENTS, _CHECKS, _ANALYSIS, _INTEGRITY_ISSUES, _INVOCATION_ID, _INPUT_BINDINGS
    global _GROUND_INDEX_POLICY, _GROUND_QUALIFICATIONS, _PRECISION_CONTROL_CAPTURE, _CAPTURE_COVERAGE
    _GROUND_INDEX_POLICY = _claim_ground_policy(name)
    _PRECISION_CONTROL_CAPTURE = _claim_precision_control(name)
    _CAPTURE_COVERAGE = []
    _GROUND_QUALIFICATIONS = []
    _MEASUREMENTS = []
    _CHECKS, _ANALYSIS, _INTEGRITY_ISSUES = [], {}, []
    _INPUT_BINDINGS = {}
    _INVOCATION_ID = uuid.uuid4().hex[:12]
    started_at = time.time()
    integrity, publication, error = "INCOMPLETE", {"status": "not_started"}, None
    try:
        CLAIMS[name](quick)
        _validate_planned_measurements(name, quick)
        # Publication preserves useful artifacts even if a hypothesis is false or
        # a capture is incomplete; the independent integrity verdict stays strict.
        try:
            publication = _finalize_publication()
        except BaseException as publication_error:
            publication = _failed_publication_evidence(publication_error)
            raise
        if not _INTEGRITY_ISSUES:
            integrity = "PASS"
    except BaseException as exception:
        error = f"{type(exception).__name__}: {exception}"
        raise
    finally:
        summary = _write_claim_summary(name, started_at, integrity, publication, quick, error)
    if integrity != "PASS":
        raise RuntimeError("required measurement or capture evidence is incomplete; inspect the claim summary")
    return summary

def main():
    ap = argparse.ArgumentParser(
        description="Reproduce the claims of the CCM Convergence Law paper.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Claims: " + ", ".join(ALL_ORDER) + ", all")
    ap.add_argument("claim", help="claim to reproduce (or 'all')")
    ap.add_argument("--quick", action="store_true",
                    help="run only light (WSL2-minutes) configs; skip server-grade")
    ap.add_argument("--bin", default=DEFAULT_BIN,
                    help="path to the ccm-convergence-rate binary")
    ap.add_argument("--first-zero-index", type=int, default=1,
                    help="first one-based zero ordinal retained in every result (default: 1)")
    ap.add_argument("--zero-count", type=int, default=5,
                    help="number of consecutive zero ordinals retained (default: 5)")
    ap.add_argument("--analysis-zero-index", type=int, default=1,
                    help="ordinal used by the scalar convergence fits (default: 1)")
    ap.add_argument("--root-acquisition", choices=["seeded", "independent"],
                    default="seeded",
                    help="seeded reproduction or independent finite-source discovery")
    ap.add_argument("--parity-policy",
                    choices=["natural", "adaptive-even", "even-sector"],
                    default="even-sector",
                    help="eigenstate parity policy")
    ap.add_argument("--eigenstate-solver",
                    choices=["legacy-inverse-iteration", "shift-invert-krylov", "auto"],
                    default="auto",
                    help="eigenstate algorithm")
    ap.add_argument("--ground-index-policy", choices=["require", "record-outcome"],
                    help="default: record proof outcome for precision-floor controls C1-C3; require it otherwise")
    ap.add_argument("--precision-control-capture", action="store_true",
                    help="assess exact C1-C3 precision controls separately while preserving incomplete raw Ultra receipts")
    ap.add_argument("--research-capture",
                    choices=["claim", "research", "gap", "maximum", "ultra"],
                    default="ultra",
                    help="supplemental artifact capture level")
    ap.add_argument("--research-sector-eigenpairs", type=int, default=8,
                    help="low eigenpairs retained per sector in maximum mode")
    ap.add_argument("--results-dir", default=os.path.join(REPO_ROOT, "claim-runs"),
                    help="parent for a new unique measurement/log/summary directory")
    ap.add_argument("--resume", action="store_true",
                    help="search --resume-dir (or --results-dir) for fully source-bound retained results")
    ap.add_argument("--resume-dir", help="retained run root to search; existing files remain unchanged")
    ap.add_argument("--parallel-gl-roots", action="store_true",
                    help="use the explicitly built and qualified native-Linux parallel GL path")
    ap.add_argument("--capture-sector-gap-certificate", action="store_true",
                    help="request the optional sector gap certificate (off by default)")
    ap.add_argument("--capture-maximum-stream-scalar-bytes", type=int,
                    default=274877906944, help="cumulative streamed scalar-text budget")
    ap.add_argument("--plan", action="store_true", help="show exact grids and policies; no build or computation")
    ap.add_argument("--validate-only", action="store_true", help="verify the executable and configuration; no claim computation")
    args = ap.parse_args()

    global _BIN, _FIRST_ZERO_INDEX, _ZERO_COUNT, _ANALYSIS_ZERO_INDEX
    global _ROOT_ACQUISITION, _PARITY_POLICY, _EIGENSTATE_SOLVER
    global _RESEARCH_CAPTURE, _RESEARCH_SECTOR_EIGENPAIRS
    global _RESULTS_DIR, _RESUME
    global _RESUME_DIR, _PARALLEL_GL_ROOTS, _SECTOR_GAP, _STREAM_SCALAR_BYTES
    global _GROUND_POLICY_OVERRIDE, _GROUND_INDEX_POLICY, _PRECISION_CONTROL_REQUESTED, _PRECISION_CONTROL_CAPTURE
    _GROUND_POLICY_OVERRIDE = args.ground_index_policy
    _PRECISION_CONTROL_REQUESTED = args.precision_control_capture
    _BIN = args.bin
    _FIRST_ZERO_INDEX = args.first_zero_index
    _ZERO_COUNT = args.zero_count
    _ANALYSIS_ZERO_INDEX = args.analysis_zero_index
    _ROOT_ACQUISITION = args.root_acquisition
    _PARITY_POLICY = args.parity_policy
    _EIGENSTATE_SOLVER = args.eigenstate_solver
    _RESEARCH_CAPTURE = args.research_capture
    _RESEARCH_SECTOR_EIGENPAIRS = args.research_sector_eigenpairs
    _RESULTS_DIR = os.path.abspath(args.results_dir)
    _RESUME = args.resume
    _RESUME_DIR = os.path.abspath(args.resume_dir or args.results_dir) if args.resume or args.resume_dir else None
    _RESUME = _RESUME_DIR is not None
    _PARALLEL_GL_ROOTS = args.parallel_gl_roots
    _SECTOR_GAP = args.capture_sector_gap_certificate
    _STREAM_SCALAR_BYTES = args.capture_maximum_stream_scalar_bytes

    if _FIRST_ZERO_INDEX < 1:
        ap.error("--first-zero-index must be positive")
    if _ZERO_COUNT < 1:
        ap.error("--zero-count must be positive")
    if _RESEARCH_SECTOR_EIGENPAIRS < 1:
        ap.error("--research-sector-eigenpairs must be positive")
    if not 1 <= _STREAM_SCALAR_BYTES <= 1099511627776:
        ap.error("--capture-maximum-stream-scalar-bytes must be in 1..1099511627776")
    last_zero_index = _FIRST_ZERO_INDEX + _ZERO_COUNT - 1
    if not _FIRST_ZERO_INDEX <= _ANALYSIS_ZERO_INDEX <= last_zero_index:
        ap.error(
            "--analysis-zero-index must lie inside the retained window "
            f"{_FIRST_ZERO_INDEX}..{last_zero_index}"
        )

    if args.claim != "all" and args.claim not in CLAIMS:
        ap.error(f"unknown claim '{args.claim}'. Choose from: "
                 + ", ".join(ALL_ORDER) + ", all")
    names = ALL_ORDER if args.claim == "all" else [args.claim]
    if args.precision_control_capture and (args.claim != "all" and args.claim not in {
            "budget-switch", "precision-slope", "floor-artifact"}):
        ap.error("precision-control capture is restricted to the exact C1-C3 controls")
    if args.precision_control_capture and (args.ground_index_policy == "require" or
            (_ROOT_ACQUISITION, _FIRST_ZERO_INDEX, _ZERO_COUNT, _PARITY_POLICY, _EIGENSTATE_SOLVER,
             _RESEARCH_CAPTURE, _SECTOR_GAP) != ("seeded", 1, 5, "even-sector", "auto", "ultra", False)):
        ap.error("precision-control capture requires the declared seeded C1-C3 configuration and record-outcome policy")
    if args.ground_index_policy == "record-outcome" and any(name not in {
            "budget-switch", "precision-slope", "floor-artifact"} for name in names):
        ap.error("record-outcome is limited to the explicit precision-floor controls C1, C2, and C3")
    _GROUND_INDEX_POLICY = _claim_ground_policy(names[0])
    _PRECISION_CONTROL_CAPTURE = _claim_precision_control(names[0])
    plan = {"schema_version": 1, "claims": {name: configuration_grid(name, args.quick) for name in names},
            "ground_index_policies": {name: _claim_ground_policy(name) for name in names},
            "precision_control_capture_policies": {name: _claim_precision_control(name) for name in names},
            "root_acquisition": _ROOT_ACQUISITION, "parity_policy": _PARITY_POLICY,
            "eigenstate_solver": _EIGENSTATE_SOLVER, "research_capture": _RESEARCH_CAPTURE,
            "research_sector_eigenpairs": _RESEARCH_SECTOR_EIGENPAIRS,
            "first_zero_index": _FIRST_ZERO_INDEX, "analysis_zero_index": _ANALYSIS_ZERO_INDEX,
            "execution_policy": _execution_policy(), "quick_subset": args.quick,
            "publication_target": os.environ.get("XC_PUBLISH_TARGET", "none"),
            "publication_requested": os.environ.get("XC_PUBLISH_EXECUTE", "").lower() == "true"}
    if args.plan:
        print(json.dumps(plan, indent=2, allow_nan=False))
        return
    _verify_binary()
    # Resolve the entire requested target grid before any expensive point starts.
    for cutoff, precision, n_modes in sorted({(row["lambda_sq"], row["precision_digits"], row["n_modes"])
            for name in names for row in configuration_grid(name, args.quick)}):
        _external_input_binding(_target_file(cutoff, precision), n_modes)
    if args.validate_only:
        print(json.dumps(plan, indent=2, allow_nan=False))
        print("[PASS] configuration and executable admitted; no claim started")
        return
    parent = _RESULTS_DIR
    os.makedirs(parent, exist_ok=True)
    run_id = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + uuid.uuid4().hex[:12]
    _RESULTS_DIR = os.path.join(parent, f"claim-{args.claim}-{run_id}")
    os.makedirs(_RESULTS_DIR, exist_ok=False)
    _write_json(os.path.join(_RESULTS_DIR, "request.json"), plan)
    _write_json(os.path.join(_RESULTS_DIR, "build.json"), _BUILD_INFO)
    if os.environ.get("XC_PUBLISH_EXECUTE", "").lower() == "true":
        os.environ.setdefault("XC_PUBLISH_STAGING_ROOT", os.path.join(_RESULTS_DIR, "staging"))
    print(f"Run journals: {_RESULTS_DIR}", flush=True)
    for name in names:
        _run_claim(name, args.quick)

if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"[INCOMPLETE] {error}", file=sys.stderr)
        raise SystemExit(1)
