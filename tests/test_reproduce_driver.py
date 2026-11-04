"""Unit tests for the non-numerical reproduction-driver behavior."""

import importlib.util
import copy
import io
import json
import pathlib
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "reproduce", REPO_ROOT / "scripts" / "reproduce.py"
)
reproduce = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(reproduce)


class MultiZeroDriverTests(unittest.TestCase):
    def setUp(self):
        self.original = (
            reproduce._FIRST_ZERO_INDEX,
            reproduce._ZERO_COUNT,
            reproduce._ANALYSIS_ZERO_INDEX,
            reproduce._ROOT_ACQUISITION,
            reproduce._PARITY_POLICY,
            reproduce._EIGENSTATE_SOLVER,
            reproduce._RESEARCH_CAPTURE,
        )

    def tearDown(self):
        (
            reproduce._FIRST_ZERO_INDEX,
            reproduce._ZERO_COUNT,
            reproduce._ANALYSIS_ZERO_INDEX,
            reproduce._ROOT_ACQUISITION,
            reproduce._PARITY_POLICY,
            reproduce._EIGENSTATE_SOLVER,
            reproduce._RESEARCH_CAPTURE,
        ) = self.original

    def test_selected_digits_uses_requested_ordinal(self):
        reproduce._ANALYSIS_ZERO_INDEX = 7
        report = {
            "roots": [
                {"reference_index": 6, "matching_digits_f64": 12.5},
                {"reference_index": 7, "matching_digits_f64": 9.25},
            ]
        }
        self.assertEqual(reproduce._selected_digits(report), 9.25)

    def test_missing_ordinal_is_an_unresolved_point(self):
        reproduce._ANALYSIS_ZERO_INDEX = 5
        report = {
            "roots": [
                {"reference_index": 1, "matching_digits_f64": 10.0},
                {"reference_index": 2, "matching_digits_f64": 8.0},
            ]
        }
        self.assertIsNone(reproduce._selected_digits(report))

    def test_measurement_identity_contains_all_numerical_policies(self):
        reproduce._FIRST_ZERO_INDEX = 21
        reproduce._ROOT_ACQUISITION = "independent"
        reproduce._PARITY_POLICY = "natural"
        reproduce._EIGENSTATE_SOLVER = "shift-invert-krylov"
        reproduce._RESEARCH_CAPTURE = "maximum"
        path = reproduce._measurement_path(50, 400, 700, 10)
        self.assertTrue(
            path.endswith(
                "l2-50-n-400-p-700-z-21-10-independent-natural-"
                "shift-invert-krylov-maximum-e8.json"
            )
        )

    def test_higher_ordinal_verdict_is_exploratory(self):
        reproduce._ANALYSIS_ZERO_INDEX = 2
        self.assertEqual(reproduce.verdict(True), "UNASSESSED")
        self.assertEqual(reproduce.verdict(False), "UNASSESSED")

    def test_small_n_mode_ramp_requests_only_the_first_root(self):
        grid = [(7, [3, 5], 200, False)]
        with (
            mock.patch.object(reproduce, "_RAMP_GRID", grid),
            mock.patch.object(reproduce, "measure", return_value=3.0) as measure,
            mock.patch.object(
                reproduce, "fit_tanh_ramp", return_value=(1.2, 1.0, 0.01)
            ),
            redirect_stdout(io.StringIO()),
        ):
            reproduce.c4_nmode_ramp(quick=False)

        self.assertEqual(measure.call_count, 2)
        for call in measure.call_args_list:
            self.assertEqual(call.kwargs, {"zero_count": 1})

    def test_mode_ramp_claims_have_distinct_reports(self):
        self.assertIs(reproduce.CLAIMS["nmode-ramp"], reproduce.c4_nmode_ramp)
        self.assertIs(reproduce.CLAIMS["mode-exponent"], reproduce.c8_mode_exponent)
        self.assertIs(
            reproduce.CLAIMS["onset-constant"], reproduce.c9_onset_constant
        )

    def test_mode_ramp_grid_excludes_unproven_extrapolations(self):
        self.assertEqual(
            [lambda_sq for lambda_sq, _, _, _ in reproduce._RAMP_GRID],
            [7, 13, 20, 25, 50, 100],
        )


class EvidenceIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.state = {name: getattr(reproduce, name) for name in (
            "_BUILD_INFO", "_BINARY_SHA256", "_CHECKS", "_ANALYSIS",
            "_INTEGRITY_ISSUES", "_MEASUREMENTS", "_RESULTS_DIR", "_INVOCATION_ID",
            "_ANALYSIS_ZERO_INDEX", "_FIRST_ZERO_INDEX", "_ZERO_COUNT", "_INPUT_BINDINGS",
            "_GROUND_INDEX_POLICY", "_GROUND_POLICY_OVERRIDE", "_GROUND_QUALIFICATIONS",
            "_PRECISION_CONTROL_REQUESTED", "_PRECISION_CONTROL_CAPTURE", "_CAPTURE_COVERAGE")}
        reproduce._BUILD_INFO = {"schema_version": 1, "implementation_digest": "source-a"}
        reproduce._BINARY_SHA256 = "binary-a"
        reproduce._CHECKS = []
        reproduce._ANALYSIS = {}
        reproduce._INTEGRITY_ISSUES = []
        reproduce._MEASUREMENTS = []
        reproduce._ANALYSIS_ZERO_INDEX = reproduce._FIRST_ZERO_INDEX = 1
        reproduce._ZERO_COUNT = 5
        reproduce._GROUND_INDEX_POLICY = "require"
        reproduce._GROUND_POLICY_OVERRIDE = None
        reproduce._GROUND_QUALIFICATIONS = []
        reproduce._PRECISION_CONTROL_REQUESTED = False
        reproduce._PRECISION_CONTROL_CAPTURE = False
        reproduce._CAPTURE_COVERAGE = []
        self.temporary = tempfile.TemporaryDirectory()
        reproduce._RESULTS_DIR = self.temporary.name

    def tearDown(self):
        for name, value in self.state.items():
            setattr(reproduce, name, value)
        self.temporary.cleanup()

    def publication_fixture(self):
        root = pathlib.Path(self.temporary.name) / "staging"
        draft = root / "drafts" / "first" / "draft.json"
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text(json.dumps({"manifest": {"artifact_family": "evidence",
            "semantic_digest": "a" * 64, "payload_digest": "b" * 64}}), encoding="utf-8")
        (root / "publication-inventory.json").write_text(json.dumps({"target": "private",
            "ready_for_remote_execution": True, "entries": [{"family": "evidence",
            "semantic_digest": "a" * 64, "payload_digest": "b" * 64,
            "assurance_eligible": True}]}), encoding="utf-8")
        phase = root / "publication-execution-reports" / "0001-first.json"
        phase.parent.mkdir()
        phase.write_text('{"all_completed":true,"transactions":[]}', encoding="utf-8")
        return root, {"XC_PUBLISH_EXECUTE": "true", "XC_PUBLISH_STAGING_ROOT": str(root),
            "XC_PUBLISH_TARGET": "private", "XC_CACHE_REPOSITORY_OWNER": "owner"}, draft

    def test_negative_hypothesis_is_recorded_as_fail(self):
        self.assertEqual(reproduce.verdict(False), "FAIL")
        self.assertEqual(reproduce._CHECKS[-1]["status"], "FAIL")

    def test_first_vast_grid_has_all_four_fixed_rows(self):
        self.assertEqual(reproduce.configuration_grid("precision-slope"), [
            {"lambda_sq": 50, "n_modes": 400, "precision_digits": p, "zero_count": 5}
            for p in (50, 100, 150, 200)])

    def test_resume_rejects_report_tampering_and_different_build(self):
        path = str(pathlib.Path(self.temporary.name) / "row.json")
        log = str(pathlib.Path(self.temporary.name) / "row.log")
        pathlib.Path(path).write_text('{"measurement": 1}', encoding="utf-8")
        pathlib.Path(log).write_text("complete\n", encoding="utf-8")
        configuration = {"lambda_sq": 50, "n_modes": 400, "precision_digits": 50}
        reproduce._seal_execution(path, log, configuration)
        reproduce._validate_execution(path, configuration)
        reproduce._BINARY_SHA256 = "other-binary"
        with self.assertRaises(ValueError):
            reproduce._validate_execution(path, configuration)
        reproduce._BINARY_SHA256 = "binary-a"
        pathlib.Path(path).write_text('{"measurement": 2}', encoding="utf-8")
        with self.assertRaises(ValueError):
            reproduce._validate_execution(path, configuration)

    def test_legacy_unbound_result_is_not_resumable(self):
        path = str(pathlib.Path(self.temporary.name) / "old.json")
        pathlib.Path(path).write_text("{}", encoding="utf-8")
        with self.assertRaises(FileNotFoundError):
            reproduce._validate_execution(path, {})

    def test_missing_or_unresolved_root_and_capture_are_incomplete(self):
        report = {"first_zero_index": 1, "zero_count_requested": 2,
                  "ground_index_policy": "require", "ground_index_admission": {"established": True},
                  "roots": [{"reference_index": 1, "status": "approximate",
                             "matching_digits_f64": 30.0}], "capture_complete": False,
                  "all_requested_capture_complete": False, "applicable_capture_complete": False,
                  "precision_control_capture": False}
        reproduce._check_measurement_integrity(report, "row.json")
        self.assertEqual(len(reproduce._INTEGRITY_ISSUES), 3)

    def test_failed_finite_check_does_not_become_execution_failure(self):
        def negative(quick):
            reproduce.verdict(False)
        with (
            mock.patch.dict(reproduce.CLAIMS, {"precision-slope": negative}),
            mock.patch.object(reproduce, "_validate_planned_measurements"),
            mock.patch.object(reproduce, "_finalize_publication", return_value={"status": "not_requested"}),
            redirect_stdout(io.StringIO()),
        ):
            summary = reproduce._run_claim("precision-slope", False)
        self.assertEqual(summary["execution_integrity"], "PASS")
        self.assertEqual(summary["hypothesis_verdict"], "FAIL")

    def test_missing_evidence_stays_incomplete_even_if_function_returns(self):
        with (
            mock.patch.dict(reproduce.CLAIMS, {"precision-slope": lambda quick: None}),
            mock.patch.object(reproduce, "_finalize_publication", return_value={"status": "not_requested"}),
            redirect_stdout(io.StringIO()),
        ):
            with self.assertRaises(RuntimeError):
                reproduce._run_claim("precision-slope", False)
        path = next((pathlib.Path(self.temporary.name) / "claims").glob("*.json"))
        summary = json.loads(path.read_text())
        self.assertEqual(summary["execution_integrity"], "INCOMPLETE")
        self.assertFalse(summary["claim_complete"])
        self.assertEqual(summary["hypothesis_verdict"], "UNASSESSED")
        self.assertEqual(summary["publication"]["status"], "not_requested")

    def test_failed_publication_retains_failure_evidence_and_measurements(self):
        root, environment, _ = self.publication_fixture()
        operational = root / "journals" / "publication-operational-summary.json"
        operational.parent.mkdir()
        operational.write_text('{"latest_invocation":{"outcome":"failure"}}', encoding="utf-8")
        row = pathlib.Path(self.temporary.name) / "retained-row.json"
        log = pathlib.Path(self.temporary.name) / "retained-row.log"
        row.write_text('{"retained":true}', encoding="utf-8")
        log.write_text("completed numerical row\n", encoding="utf-8")
        row_digest = reproduce._sha256(row)
        with (
            mock.patch.dict(reproduce.os.environ, environment, clear=True),
            mock.patch.dict(reproduce.CLAIMS, {"budget-switch": lambda quick: reproduce._MEASUREMENTS.append(str(row))}),
            mock.patch.object(reproduce, "_validate_planned_measurements"),
            mock.patch.object(reproduce.subprocess, "run", return_value=mock.Mock(returncode=1)),
            redirect_stdout(io.StringIO()),
        ):
            reproduce._seal_execution(str(row), str(log), {})
            with self.assertRaisesRegex(RuntimeError, "publication exited 1"):
                reproduce._run_claim("budget-switch", False)
        summary_path = next((pathlib.Path(self.temporary.name) / "claims").glob("*.json"))
        summary = json.loads(summary_path.read_text())
        self.assertEqual(summary["execution_integrity"], "INCOMPLETE")
        self.assertEqual(summary["publication"]["status"], "failed")
        self.assertIn("publication exited 1", summary["publication"]["error"])
        self.assertEqual(summary["measurement_files"], [str(row)])
        self.assertEqual(reproduce._sha256(row), row_digest)
        proof = summary["publication"]["evidence"]["journals/publication-operational-summary.json"]
        operational.write_text("changed by retry", encoding="utf-8")
        self.assertEqual(reproduce._sha256(proof["path"]), proof["sha256"])
        self.assertEqual(json.loads(pathlib.Path(proof["path"]).read_text())["latest_invocation"]["outcome"], "failure")

    def test_quick_skipped_claim_is_not_a_completed_claim(self):
        with (
            mock.patch.object(reproduce, "_finalize_publication", return_value={"status": "not_requested"}),
            redirect_stdout(io.StringIO()),
        ):
            summary = reproduce._run_claim("prime-anchor", True)
        self.assertFalse(summary["claim_complete"])
        self.assertEqual(summary["hypothesis_verdict"], "UNASSESSED")

    def test_no_matching_build_identity_is_rejected(self):
        with self.assertRaises(ValueError):
            reproduce._check_report_build({})

    def test_resume_binds_retained_journal_files(self):
        root = pathlib.Path(self.temporary.name)
        journal = root / "journal"
        journal.mkdir()
        for name in ("request.json", "build.json", "measurements.json", "capture.json"):
            (journal / name).write_text("{}", encoding="utf-8")
        report, log = root / "row.json", root / "row.log"
        report.write_text(json.dumps({"journal": str(journal)}), encoding="utf-8")
        log.write_text("done\n", encoding="utf-8")
        reproduce._seal_execution(str(report), str(log), {})
        reproduce._validate_execution(str(report), {})
        (journal / "capture.json").write_text('{"changed":true}', encoding="utf-8")
        with self.assertRaises(ValueError):
            reproduce._validate_execution(str(report), {})

    def test_capture_complete_boolean_cannot_override_incomplete_receipt(self):
        report = {"first_zero_index": 1, "zero_count_requested": 1,
                  "ground_index_policy": "require", "ground_index_admission": {"established": True},
                  "roots": [{"reference_index": 1, "status": "converged", "matching_digits_f64": 30.0}],
                  "capture_complete": True, "research_capture": "ultra",
                  "all_requested_capture_complete": True, "applicable_capture_complete": True,
                  "precision_control_capture": False,
                  "capture_receipt": {"receipt": {"outcomes": {"required": {"status": "missing"}}}}}
        with self.assertRaisesRegex(ValueError, "disagrees"):
            reproduce._check_measurement_integrity(report, "row.json")

    def test_successful_publisher_process_requires_nonvacuous_complete_report(self):
        root, environment, _ = self.publication_fixture()
        path = root / "publication-execution-report.json"
        path.write_text(json.dumps({"all_completed": True, "phases": [], "transactions": []}), encoding="utf-8")
        with (
            mock.patch.dict(reproduce.os.environ, environment, clear=True),
            mock.patch.object(reproduce.subprocess, "run", return_value=mock.Mock(returncode=0)),
            redirect_stdout(io.StringIO()),
        ):
            with self.assertRaises(RuntimeError):
                reproduce._finalize_publication()
            path.write_text(json.dumps({"all_completed": True,
                            "phases": [{"all_completed": True,
                                "relative_report_path": "publication-execution-reports/0001-first.json"}],
                            "transactions": []}), encoding="utf-8")
            self.assertEqual(reproduce._finalize_publication()["status"], "finalized")
            path.write_text(json.dumps({"all_completed": True,
                            "phases": [{"all_completed": False,
                                "relative_report_path": "publication-execution-reports/0001-first.json"},
                                {"all_completed": True,
                                "relative_report_path": "publication-execution-reports/0001-first.json"}],
                            "transactions": [{"completed": True}]}), encoding="utf-8")
            self.assertEqual(reproduce._finalize_publication()["status"], "finalized")

    def test_shared_staging_keeps_cross_claim_donors_bound(self):
        root, environment, draft = self.publication_fixture()
        report, log = pathlib.Path(self.temporary.name) / "row.json", pathlib.Path(self.temporary.name) / "row.log"
        report.write_text("{}", encoding="utf-8")
        log.write_text("done", encoding="utf-8")
        with mock.patch.dict(reproduce.os.environ, environment, clear=True):
            reproduce._seal_execution(str(report), str(log), {})
            another = root / "drafts" / "second" / "draft.json"
            another.parent.mkdir()
            another.write_text(json.dumps({"manifest": {"artifact_family": "evidence",
                "semantic_digest": "c" * 64, "payload_digest": "d" * 64}}), encoding="utf-8")
            reproduce._validate_execution(str(report), {})
            draft.unlink()
            with self.assertRaises(ValueError):
                reproduce._validate_execution(str(report), {})

    def test_publication_proof_is_immutable_across_later_claims(self):
        root, environment, _ = self.publication_fixture()
        path = root / "publication-execution-report.json"
        path.write_text(json.dumps({"all_completed": True, "phases": [{"all_completed": True,
            "relative_report_path": "publication-execution-reports/0001-first.json"}],
            "transactions": []}), encoding="utf-8")
        with (mock.patch.dict(reproduce.os.environ, environment, clear=True),
              mock.patch.object(reproduce.subprocess, "run", return_value=mock.Mock(returncode=0)),
              redirect_stdout(io.StringIO())):
            result = reproduce._finalize_publication()
        path.write_text("changed by next claim", encoding="utf-8")
        (root / "publication-inventory.json").write_text("changed by next claim", encoding="utf-8")
        self.assertEqual(reproduce._sha256(result["report"]), result["report_sha256"])
        self.assertEqual(reproduce._sha256(result["inventory"]), result["inventory_sha256"])

    def test_target_directory_selects_exact_cutoff_and_precision(self):
        root = pathlib.Path(self.temporary.name)
        target = root / "c13-d30.json"
        target.write_text("{}", encoding="utf-8")
        with mock.patch.dict(reproduce.os.environ, {"XC_TARGET_SPEC_DIR": str(root)}, clear=True):
            self.assertEqual(reproduce._target_file(13, 30), str(target.resolve()))
            with self.assertRaises(ValueError):
                reproduce._target_file(13, 45)
            with mock.patch.dict(reproduce.os.environ, {"XC_TARGET_SPEC_FILE": str(target)}):
                with self.assertRaises(ValueError):
                    reproduce._target_file(13, 30)

    def test_changed_target_prevents_resume(self):
        root = pathlib.Path(self.temporary.name)
        target = root / "c13-d30.json"
        target.write_text('{"target":1}', encoding="utf-8")
        report, log = root / "row.json", root / "row.log"
        report.write_text("{}", encoding="utf-8")
        log.write_text("done\n", encoding="utf-8")
        with mock.patch.dict(reproduce.os.environ, {}, clear=True):
            original = {"external_inputs": reproduce._external_input_binding(str(target))}
            reproduce._seal_execution(str(report), str(log), original)
            target.write_text('{"target":2}', encoding="utf-8")
            changed = {"external_inputs": reproduce._external_input_binding(str(target))}
            with self.assertRaises(ValueError):
                reproduce._validate_execution(str(report), changed)

    def test_preparer_snapshot_changes_are_rejected(self):
        root = pathlib.Path(self.temporary.name)
        script = root / "prepare.py"
        script.write_text("original", encoding="utf-8")
        (root / "preparer-snapshot.json").write_text(json.dumps({"files": {
            "prepare.py": reproduce._sha256(script)}}), encoding="utf-8")
        recipe = json.dumps({"argv": [str(script)], "timeout_seconds": 0})
        with mock.patch.dict(reproduce.os.environ, {"XC_RESEARCH_PREPARER": recipe}, clear=True):
            reproduce._external_input_binding(None)
            script.write_text("changed", encoding="utf-8")
            with self.assertRaises(ValueError):
                reproduce._external_input_binding(None)

    def test_identical_preparer_can_move_between_attempts(self):
        root = pathlib.Path(self.temporary.name)
        bindings = []
        for name in ("first", "retry"):
            directory = root / name
            directory.mkdir()
            script = directory / "prepare.py"
            script.write_text("same source", encoding="utf-8")
            (directory / "preparer-snapshot.json").write_text(json.dumps({"files": {
                "prepare.py": reproduce._sha256(script)}}), encoding="utf-8")
            recipe = json.dumps({"argv": [str(script), "--mode", "exact"], "timeout_seconds": 0})
            with mock.patch.dict(reproduce.os.environ, {"XC_RESEARCH_PREPARER": recipe}, clear=True):
                bindings.append(reproduce._external_input_binding(None))
        self.assertEqual(bindings[0], bindings[1])
        changed = json.dumps({"argv": [str(script), "--mode", "different"], "timeout_seconds": 0})
        with mock.patch.dict(reproduce.os.environ, {"XC_RESEARCH_PREPARER": changed}, clear=True):
            self.assertNotEqual(bindings[0], reproduce._external_input_binding(None))

    def test_precision_floor_policy_is_limited_to_three_controls(self):
        for name in reproduce.ALL_ORDER:
            expected = "record-outcome" if name in {
                "budget-switch", "precision-slope", "floor-artifact"} else "require"
            self.assertEqual(reproduce._claim_ground_policy(name), expected)

    def test_unproved_ground_index_qualifies_finite_fit_without_hiding_result(self):
        def finite_fit(quick):
            reproduce._check_ground_admission({"ground_index_policy": "record-outcome",
                "ground_index_admission": {"established": False, "reason": "resolution floor"}}, "row.json")
            reproduce.verdict(True)
        with (mock.patch.dict(reproduce.CLAIMS, {"precision-slope": finite_fit}),
              mock.patch.object(reproduce, "_validate_planned_measurements"),
              mock.patch.object(reproduce, "_finalize_publication", return_value={"status": "not_requested"}),
              redirect_stdout(io.StringIO())):
            summary = reproduce._run_claim("precision-slope", False)
        self.assertEqual(summary["execution_integrity"], "PASS")
        self.assertEqual(summary["checks"][0]["status"], "PASS")
        self.assertEqual(summary["hypothesis_verdict"], "UNASSESSED")
        self.assertEqual(len(summary["ground_index_qualifications"]), 1)

    def test_required_ground_index_cannot_pass_when_unproved(self):
        reproduce._check_ground_admission({"ground_index_policy": "require",
            "ground_index_admission": {"established": False, "reason": "unresolved"}}, "row.json")
        self.assertEqual(len(reproduce._INTEGRITY_ISSUES), 1)
        with self.assertRaises(ValueError):
            reproduce._check_ground_admission({"ground_index_policy": "record-outcome",
                "ground_index_admission": {"established": True}}, "row.json")

    def precision_control_report(self):
        reproduce._PRECISION_CONTROL_CAPTURE = True
        reproduce._GROUND_INDEX_POLICY = "record-outcome"
        raw = {"status": "failed", "reason": "invalid cache manifest: CCM response unresolved_near_crossing: source-matrix eigenvalue intervals are not finitely separated at 164 bits"}
        report = {"lambda_sq": 13, "n_modes": 80, "precision_digits_requested": 30,
            "precision_bits_working": 164, "first_zero_index": 1, "zero_count_requested": 5,
            "selected_eigenvalue": "-3",
            "ground_index_policy": "record-outcome", "ground_index_admission": {"established": False},
            "research_capture": "ultra", "capture_complete": False,
            "all_requested_capture_complete": False, "applicable_capture_complete": True,
            "precision_control_capture": True, "build_info": copy.deepcopy(reproduce._BUILD_INFO),
            "primary_sources": [{"content_digest": "a" * 64}],
            "roots": [{"reference_index": i, "status": "converged", "matching_digits_f64": 30.0}
                      for i in range(1, 6)],
            "capture_receipt": {"receipt": {"outcomes": {"u_flow_response": raw}}}}
        report["ground_index_admission"]["reason"] = "claimed CCM eigenpair is not the algebraic ground state in the requested subspace"
        report["stored_state_resolution"] = {"arithmetic": "stored_state_residual_and_admitted_gap_v2",
            "eigenvalue_resolution": "below_storage_floor", "residual_upper": "1",
            "eigenvalue_lower": "-4", "eigenvalue_upper": "-2", "matrix_rounding_scale_upper": "100",
            "selected_gap_lower": None, "residual_angle_upper": None,
            "separation_unresolved_reason": report["ground_index_admission"]["reason"]}
        report["capture_applicability"] = {"schema_version": 1, "policy": "paper3-precision-control-v3",
            "enabled": True, "applied": True,
            "configuration": {"lambda_squared": 13, "n_modes": 80, "precision_digits": 30,
                "precision_bits": 164, "root_acquisition": "seeded", "first_zero_index": 1,
                "zero_count": 5, "parity_policy": "even-sector", "eigenstate_solver": "auto",
                "ground_index_policy": "record-outcome", "research_capture": "ultra",
                "capture_sector_gap_certificate": False},
            "build_info": copy.deepcopy(report["build_info"]),
            "primary_sources": copy.deepcopy(report["primary_sources"]),
            "ground_index_admission": copy.deepcopy(report["ground_index_admission"]),
            "all_requested_capture_complete": False, "applicable_capture_complete": True,
            "qualified_diagnostics": {"u_flow_response": {"raw_outcome": copy.deepcopy(raw),
                "classification": "unavailable_at_stored_precision", "basis": "bound source separation unavailable"}},
            "unhandled_diagnostics": {}, "prerequisite_evidence": {"source_join_validated": True,
                "selected_eigenvalue": report["selected_eigenvalue"],
                "stored_state_resolution": copy.deepcopy(report["stored_state_resolution"])}}
        journal = pathlib.Path(self.temporary.name) / "control-journal"
        journal.mkdir(exist_ok=True)
        report["journal"] = str(journal)
        for key, filename in (("input_preparation_status_sha256", "input-preparation-status.json"),
                ("input_preparation_request_sha256", "input-preparation-request.json"),
                ("prepared_research_inputs_sha256", "prepared-research-inputs.json")):
            (journal / filename).write_text("{}", encoding="utf-8")
            report["capture_applicability"]["prerequisite_evidence"][key] = reproduce._sha256(journal / filename)
        self.write_applicability_artifact(report)
        return report

    def write_applicability_artifact(self, report):
        journal = pathlib.Path(report["journal"])
        record = {"measurements": {"paper3_capture_applicability": {"value": {
            "schema_version": 1, "semantics": "paper3-precision-control-applicability-evidence-v3",
            "assessment": report["capture_applicability"], "raw_capture": report["capture_receipt"]}}}}
        payload = journal / "capture-applicability-record.json"
        payload.write_text(json.dumps(record), encoding="utf-8")
        report["capture_applicability_artifact"] = {"key": {"kind": "research_capture_receipt", "logical_key": "control"},
            "content_digest": reproduce._sha256(payload)}
        (journal / "capture-applicability-artifact.json").write_text(json.dumps(report["capture_applicability_artifact"]), encoding="utf-8")

    def test_precision_control_keeps_raw_failures_and_qualifies_hypothesis(self):
        report = self.precision_control_report()
        before = copy.deepcopy(report)
        reproduce._check_measurement_integrity(report, "control.json")
        self.assertEqual(report, before)
        self.assertEqual(reproduce._INTEGRITY_ISSUES, [])
        self.assertFalse(reproduce._CAPTURE_COVERAGE[0]["all_requested_capture_complete"])
        self.assertTrue(reproduce._CAPTURE_COVERAGE[0]["applicable_capture_complete"])
        self.assertEqual(len(reproduce._GROUND_QUALIFICATIONS), 1)

    def test_precision_control_rejects_changed_source_build_config_and_raw_reason(self):
        original = self.precision_control_report()
        for field, value in (("primary_sources", []), ("build_info", {}),
                             ("configuration", {}), ("policy", "future-policy")):
            report = copy.deepcopy(original)
            report["capture_applicability"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                reproduce._capture_coverage(report, "control.json")
        report = copy.deepcopy(original)
        report["capture_receipt"]["receipt"]["outcomes"]["u_flow_response"]["reason"] = "memory budget exhausted"
        with self.assertRaises(ValueError):
            reproduce._capture_coverage(report, "control.json")
        report["capture_applicability"]["qualified_diagnostics"]["u_flow_response"]["raw_outcome"]["reason"] = "memory budget exhausted"
        with self.assertRaisesRegex(ValueError, "unknown failure reason"):
            reproduce._capture_coverage(report, "control.json")
        report = copy.deepcopy(original)
        (pathlib.Path(report["journal"]) / "prepared-research-inputs.json").write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "prerequisite evidence changed"):
            reproduce._capture_coverage(report, "control.json")

    def test_unhandled_input_or_budget_failure_cannot_pass_applicability(self):
        report = self.precision_control_report()
        raw = {"status": "missing", "reason": "explicit retained cluster vectors required"}
        report["capture_receipt"]["receipt"]["outcomes"]["spectral_cluster_full"] = raw
        assessment = report["capture_applicability"]
        assessment["unhandled_diagnostics"]["spectral_cluster_full"] = copy.deepcopy(raw)
        with self.assertRaisesRegex(ValueError, "unhandled capture failures"):
            reproduce._capture_coverage(report, "control.json")
        report["applicable_capture_complete"] = assessment["applicable_capture_complete"] = False
        self.write_applicability_artifact(report)
        reproduce._check_measurement_integrity(report, "control.json")
        self.assertEqual(len(reproduce._INTEGRITY_ISSUES), 1)
        assessment["qualified_diagnostics"]["spectral_cluster_full"] = {
            "raw_outcome": raw, "classification": "unavailable_at_stored_precision", "basis": "not allowed"}
        with self.assertRaisesRegex(ValueError, "allowed raw outcome"):
            reproduce._capture_coverage(report, "control.json")

    def test_strict_or_out_of_grid_capture_cannot_use_control_assessment(self):
        report = self.precision_control_report()
        reproduce._PRECISION_CONTROL_CAPTURE = False
        with self.assertRaises(ValueError):
            reproduce._capture_coverage(report, "control.json")
        reproduce._PRECISION_CONTROL_CAPTURE = True
        report["n_modes"] = 81
        with self.assertRaisesRegex(ValueError, "exact declared configuration"):
            reproduce._capture_coverage(report, "control.json")

    def test_exact_gap_floor_refusal_is_qualified_but_unknown_budget_is_not(self):
        report = self.precision_control_report()
        for field in ("selected_gap_lower", "residual_angle_upper"):
            for absent in (True, False):
                invalid = copy.deepcopy(report)
                for resolution in (invalid["stored_state_resolution"],
                        invalid["capture_applicability"]["prerequisite_evidence"]["stored_state_resolution"]):
                    if absent:
                        del resolution[field]
                    else:
                        resolution[field] = "1"
                with self.subTest(field=field, absent=absent), self.assertRaisesRegex(ValueError, "supported stored-precision"):
                    reproduce._capture_coverage(invalid, "control.json")
        reason = "CCM stored precision resolution limit: selected-subspace gap is not separated from the matrix rounding scale at 164 bits"
        report["ground_index_admission"]["reason"] = reason
        report["stored_state_resolution"] = {"eigenvalue_resolution": "resolved",
            "separation_unresolved_reason": reason, "selected_gap_lower": None, "residual_angle_upper": None}
        assessment = report["capture_applicability"]
        assessment["ground_index_admission"] = copy.deepcopy(report["ground_index_admission"])
        assessment["prerequisite_evidence"]["stored_state_resolution"] = copy.deepcopy(report["stored_state_resolution"])
        self.write_applicability_artifact(report)
        self.assertTrue(reproduce._capture_coverage(report, "control.json")["applicable_capture_complete"])
        invalid = copy.deepcopy(report)
        invalid["stored_state_resolution"]["eigenvalue_resolution"] = "unknown"
        invalid["capture_applicability"]["prerequisite_evidence"]["stored_state_resolution"]["eigenvalue_resolution"] = "unknown"
        with self.assertRaisesRegex(ValueError, "supported stored-precision"):
            reproduce._capture_coverage(invalid, "control.json")
        for bad_reason in (reason.replace("164", "165"), "guard budget exhausted"):
            invalid = copy.deepcopy(report)
            invalid["ground_index_admission"]["reason"] = bad_reason
            invalid["capture_applicability"]["ground_index_admission"]["reason"] = bad_reason
            invalid["stored_state_resolution"]["separation_unresolved_reason"] = bad_reason
            invalid["capture_applicability"]["prerequisite_evidence"]["stored_state_resolution"]["separation_unresolved_reason"] = bad_reason
            with self.subTest(reason=bad_reason), self.assertRaisesRegex(ValueError, "supported stored-precision"):
                reproduce._capture_coverage(invalid, "control.json")
        report["stored_state_resolution"]["selected_gap_lower"] = "1"
        assessment["prerequisite_evidence"]["stored_state_resolution"]["selected_gap_lower"] = "1"
        with self.assertRaisesRegex(ValueError, "supported stored-precision"):
            reproduce._capture_coverage(report, "control.json")

    def test_applicability_requires_exact_retained_and_published_artifact(self):
        report = self.precision_control_report()
        root, environment, draft = self.publication_fixture()
        with mock.patch.dict(reproduce.os.environ, environment, clear=True):
            with self.assertRaisesRegex(ValueError, "missing or ambiguous in staging"):
                reproduce._capture_coverage(report, "control.json")
            descriptor = json.loads(draft.read_text())
            descriptor["source_artifact_key"] = report["capture_applicability_artifact"]["key"]
            descriptor["source_content_digest"] = report["capture_applicability_artifact"]["content_digest"]
            draft.write_text(json.dumps(descriptor), encoding="utf-8")
            coverage = reproduce._capture_coverage(report, "control.json")
            self.assertEqual(coverage["applicability_artifact"]["canonical_identity"], ["evidence", "a"*64, "b"*64])
            payload = pathlib.Path(report["journal"]) / "capture-applicability-record.json"
            payload.write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "artifact changed"):
                reproduce._capture_coverage(report, "control.json")

    def clustered_precision_control_report(self):
        report = self.precision_control_report()
        report.update(lambda_sq=50, n_modes=400, precision_digits_requested=50, precision_bits_working=231)
        value = "1.5055664502159138363945483248616315216337809191509450519797090237602861e-70"
        residual = "3.22877953976253008334943100414560455826445648623661223484693389043687363695482791066578672e-70"
        reason = f"{reproduce._CLUSTERED_GROUND_PREFIX}5, eigenvalue={value}, residual={residual}"
        report["selected_eigenvalue"] = value
        report["ground_index_admission"] = {"established": False, "reason": reason}
        report["stored_state_resolution"] = {"arithmetic": "stored_state_residual_and_admitted_gap_v2",
            "eigenvalue_resolution": "stored_sign_unresolved",
            "separation_unresolved_reason": reason, "selected_gap_lower": None, "residual_angle_upper": None,
            "residual_upper": residual,
            "eigenvalue_lower": "-1.72321308954661624695488267928397303663067556708566718286722486667658757819410781546435139e-70",
            "eigenvalue_upper": "4.73434598997844391974397932900723607989823740538755728682664291419715969571554800586722205e-70",
            "matrix_rounding_scale_upper": "1.81301996003809347962777864054630263311560404455764947981685184868451223902905141953396053e-66"}
        outcomes = {}
        for name in ("evenness", "sector_analysis", "prime_power_response", "u_flow_response"):
            outcome_reason = (reproduce._AMBIGUOUS_SECTOR_PREFIX + "31 candidate members)"
                if name in {"evenness", "sector_analysis"} else
                "invalid cache manifest: CCM response unresolved_near_crossing: source-matrix eigenvalue intervals are not finitely separated at 231 bits")
            outcomes[name] = {"status": "failed", "reason": outcome_reason}
        report["capture_receipt"]["receipt"]["outcomes"] = outcomes
        assessment = report["capture_applicability"]
        assessment["configuration"].update(lambda_squared=50, n_modes=400, precision_digits=50, precision_bits=231)
        assessment["ground_index_admission"] = copy.deepcopy(report["ground_index_admission"])
        assessment["qualified_diagnostics"] = {name: {"raw_outcome": copy.deepcopy(value),
            "classification": "unavailable_at_stored_precision", "basis": "separation unavailable for bound stored source"}
            for name, value in outcomes.items()}
        assessment["prerequisite_evidence"].update(selected_eigenvalue=value,
            stored_state_resolution=copy.deepcopy(report["stored_state_resolution"]))
        self.write_applicability_artifact(report)
        return report

    def test_v2_actual_clustered_source_qualifies_only_four_known_outcomes(self):
        report = self.clustered_precision_control_report()
        before = copy.deepcopy(report)
        reproduce._check_measurement_integrity(report, "control.json")
        self.assertEqual(report, before)
        self.assertEqual(reproduce._INTEGRITY_ISSUES, [])
        self.assertEqual(len(reproduce._GROUND_QUALIFICATIONS), 1)
        coverage = reproduce._CAPTURE_COVERAGE[0]
        self.assertFalse(coverage["all_requested_capture_complete"])
        self.assertTrue(coverage["applicable_capture_complete"])
        self.assertEqual(set(coverage["qualified_diagnostics"]),
            {"evenness", "sector_analysis", "prime_power_response", "u_flow_response"})

    def test_v2_clustered_source_rejects_invalid_counts_bounds_and_source_bindings(self):
        original = self.clustered_precision_control_report()
        for field, value in (("residual_upper", "1e-70"), ("eigenvalue_resolution", "resolved"),
                ("selected_gap_lower", "1"), ("residual_angle_upper", "1"),
                ("eigenvalue_lower", "1e-70"), ("eigenvalue_upper", "-1e-70"),
                ("eigenvalue_upper", "0"), ("matrix_rounding_scale_upper", "1e-70"),
                ("matrix_rounding_scale_upper", "0"), ("matrix_rounding_scale_upper", "NaN"),
                ("eigenvalue_lower", "-Infinity"), ("eigenvalue_upper", "1e100001")):
            report = copy.deepcopy(original)
            report["stored_state_resolution"][field] = value
            report["capture_applicability"]["prerequisite_evidence"]["stored_state_resolution"][field] = value
            with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, "supported stored-precision"):
                reproduce._capture_coverage(report, "control.json")
        for count in ("0", "1", "402", "05", "+5", "-5", "5 trailing"):
            report = copy.deepcopy(original)
            reason = report["ground_index_admission"]["reason"].replace("upper_count=5,", f"upper_count={count},")
            report["ground_index_admission"]["reason"] = reason
            report["stored_state_resolution"]["separation_unresolved_reason"] = reason
            report["capture_applicability"]["ground_index_admission"] = copy.deepcopy(report["ground_index_admission"])
            report["capture_applicability"]["prerequisite_evidence"]["stored_state_resolution"] = copy.deepcopy(report["stored_state_resolution"])
            with self.subTest(count=count), self.assertRaisesRegex(ValueError, "supported stored-precision"):
                reproduce._capture_coverage(report, "control.json")
        original["selected_eigenvalue"] = "2e-70"
        with self.assertRaisesRegex(ValueError, "supported stored-precision"):
            reproduce._capture_coverage(original, "control.json")

    def test_v2_sector_parser_is_bounded_and_cannot_hide_unknown_failures(self):
        for count in ("2", "31", "401"):
            self.assertTrue(reproduce._ambiguous_sector_reason(
                reproduce._AMBIGUOUS_SECTOR_PREFIX + count + " candidate members)", 401))
        for count in ("0", "1", "402", "031", "+31", "-31", "31 extra"):
            self.assertFalse(reproduce._ambiguous_sector_reason(
                reproduce._AMBIGUOUS_SECTOR_PREFIX + count + " candidate members)", 401))
        for reason in ("guard budget exhausted", "missing cluster vectors",
                reproduce._AMBIGUOUS_SECTOR_PREFIX + "31 candidate members) trailing"):
            self.assertFalse(reproduce._ambiguous_sector_reason(reason, 401))

    def test_v2_counted_probe_must_be_strictly_below_resolution_scale(self):
        report = {"n_modes": 400, "precision_bits_working": 231, "selected_eigenvalue": "1"}
        reason = reproduce._CLUSTERED_GROUND_PREFIX + "2, eigenvalue=1, residual=1"
        resolution = {"arithmetic": "stored_state_residual_and_admitted_gap_v2",
            "eigenvalue_resolution": "stored_sign_unresolved", "residual_upper": "1",
            "eigenvalue_lower": "0", "eigenvalue_upper": "2", "matrix_rounding_scale_upper": "18"}
        self.assertFalse(reproduce._clustered_ground_source(report, resolution, reason))
        resolution["matrix_rounding_scale_upper"] = "19"
        self.assertTrue(reproduce._clustered_ground_source(report, resolution, reason))
        report["selected_eigenvalue"] = "0"
        reason = reason.replace("eigenvalue=1,", "eigenvalue=0,")
        resolution["eigenvalue_lower"] = "-1"
        self.assertFalse(reproduce._clustered_ground_source(report, resolution, reason))

    def nonground_sign_precision_control_report(self):
        report = self.clustered_precision_control_report()
        report.update(precision_digits_requested=100, precision_bits_working=397,
            selected_eigenvalue="4.920354169916721831076896574044860205820552412273174410287764062922768559519593697399861696237317797551520181818491207152e-121")
        reason = "claimed CCM eigenpair is not the algebraic ground state in the requested subspace"
        report["ground_index_admission"] = {"established": False, "reason": reason}
        report["stored_state_resolution"] = {"arithmetic": "stored_state_residual_and_admitted_gap_v2",
            "eigenvalue_resolution": "stored_sign_unresolved", "separation_unresolved_reason": reason,
            "selected_gap_lower": None, "residual_angle_upper": None,
            "residual_upper": "1.5793218311939367582155197823332562652834763747934341669571841535302918355948642561950062348775487610682538699229511029649684188055344824140e-120",
            "eigenvalue_lower": "-1.0872864142022645751078301249287702447014211335661167259284077472380149796429048864550200652538169813131018517411019822497289460227103663634e-120",
            "eigenvalue_upper": "2.0713572481856089413232094397377422858655316160207516079859605598225686915468236259349924045012805408234058881048002236802078915883585984646e-120",
            "matrix_rounding_scale_upper": "1.9383103071530316218846529276661912812001120227295168164414254397631783489465064653111425148676089811641057013137887721930658620809954341890e-116"}
        assessment = report["capture_applicability"]
        assessment["configuration"].update(precision_digits=100, precision_bits=397)
        assessment["ground_index_admission"] = copy.deepcopy(report["ground_index_admission"])
        assessment["prerequisite_evidence"].update(selected_eigenvalue=report["selected_eigenvalue"],
            stored_state_resolution=copy.deepcopy(report["stored_state_resolution"]))
        for name, raw in report["capture_receipt"]["receipt"]["outcomes"].items():
            raw["reason"] = raw["reason"].replace("31 candidate", "21 candidate").replace("231 bits", "397 bits")
            assessment["qualified_diagnostics"][name]["raw_outcome"] = copy.deepcopy(raw)
        self.write_applicability_artifact(report)
        return report

    def test_v3_actual_nonground_p100_qualifies_four_outcomes_without_mutating_raw_result(self):
        report = self.nonground_sign_precision_control_report()
        before = copy.deepcopy(report)
        reproduce._check_measurement_integrity(report, "control.json")
        self.assertEqual(report, before)
        self.assertEqual(reproduce._INTEGRITY_ISSUES, [])
        self.assertEqual(len(reproduce._GROUND_QUALIFICATIONS), 1)
        self.assertFalse(report["capture_complete"])
        self.assertFalse(report["ground_index_admission"]["established"])
        coverage = reproduce._CAPTURE_COVERAGE[0]
        self.assertFalse(coverage["all_requested_capture_complete"])
        self.assertTrue(coverage["applicable_capture_complete"])
        self.assertEqual(set(coverage["qualified_diagnostics"]),
            {"evenness", "sector_analysis", "prime_power_response", "u_flow_response"})
        self.assertTrue(all(raw["status"] == "failed"
            for raw in report["capture_receipt"]["receipt"]["outcomes"].values()))

    def test_v3_nonground_source_rejects_unsafe_or_mismatched_metadata(self):
        original = self.nonground_sign_precision_control_report()
        for field, value in (("arithmetic", "unknown"), ("eigenvalue_resolution", "resolved"),
                ("eigenvalue_resolution", "below_storage_floor"), ("residual_upper", "0"),
                ("residual_upper", "-1"), ("residual_upper", "1e-110"), ("residual_upper", "NaN"),
                ("eigenvalue_lower", "1e-122"), ("eigenvalue_upper", "0"),
                ("matrix_rounding_scale_upper", "1e-120"), ("matrix_rounding_scale_upper", "0"),
                ("selected_gap_lower", "1"), ("residual_angle_upper", "1")):
            report = copy.deepcopy(original)
            report["stored_state_resolution"][field] = value
            report["capture_applicability"]["prerequisite_evidence"]["stored_state_resolution"][field] = value
            with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, "supported stored-precision"):
                reproduce._capture_coverage(report, "control.json")
        for field in ("arithmetic", "residual_upper", "eigenvalue_lower", "eigenvalue_upper",
                "matrix_rounding_scale_upper", "selected_gap_lower", "residual_angle_upper"):
            report = copy.deepcopy(original)
            del report["stored_state_resolution"][field]
            del report["capture_applicability"]["prerequisite_evidence"]["stored_state_resolution"][field]
            with self.subTest(missing=field), self.assertRaisesRegex(ValueError, "supported stored-precision"):
                reproduce._capture_coverage(report, "control.json")
        for value in ("0", "1e-110"):
            report = copy.deepcopy(original)
            report["selected_eigenvalue"] = value
            report["capture_applicability"]["prerequisite_evidence"]["selected_eigenvalue"] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "supported stored-precision"):
                reproduce._capture_coverage(report, "control.json")
        for reason in (original["ground_index_admission"]["reason"] + " trailing",
                "CCM ground-index inertia is inconclusive within the guard precision budget",
                "ground-index stage exceeds workspace budget"):
            report = copy.deepcopy(original)
            report["ground_index_admission"]["reason"] = reason
            report["stored_state_resolution"]["separation_unresolved_reason"] = reason
            report["capture_applicability"]["ground_index_admission"] = copy.deepcopy(report["ground_index_admission"])
            report["capture_applicability"]["prerequisite_evidence"]["stored_state_resolution"] = copy.deepcopy(report["stored_state_resolution"])
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, "supported stored-precision"):
                reproduce._capture_coverage(report, "control.json")

    def test_v3_nonground_floor_uses_strict_margin_and_checks_sign_classification(self):
        report = {"precision_bits_working": 397, "selected_eigenvalue": "1"}
        resolution = {"arithmetic": "stored_state_residual_and_admitted_gap_v2",
            "eigenvalue_resolution": "stored_sign_unresolved", "residual_upper": "1",
            "eigenvalue_lower": "0", "eigenvalue_upper": "2", "matrix_rounding_scale_upper": "18"}
        self.assertFalse(reproduce._source_below_storage_scale(report, resolution))
        resolution["matrix_rounding_scale_upper"] = "19"
        self.assertTrue(reproduce._source_below_storage_scale(report, resolution))
        resolution["eigenvalue_resolution"] = "below_storage_floor"
        self.assertFalse(reproduce._source_below_storage_scale(report, resolution))
        report["selected_eigenvalue"] = "-3"
        resolution.update(eigenvalue_lower="-4", eigenvalue_upper="-2", matrix_rounding_scale_upper="100")
        self.assertTrue(reproduce._source_below_storage_scale(report, resolution))
        resolution["eigenvalue_resolution"] = "stored_sign_unresolved"
        self.assertFalse(reproduce._source_below_storage_scale(report, resolution))


class ArithmeticReferenceBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.ordinates = self.root / "ordinates.json"
        self.ordinates.write_text('["14.134725"]', encoding="utf-8")
        self.identity = {"schema_version": 1, "resource": "test/explicit",
            "content_sha256": reproduce._sha256(self.ordinates),
            "record_count": 1136, "decimal_digits": 2500}
        self.identity_path = self.root / "identity.json"
        self.identity_path.write_text(json.dumps(self.identity), encoding="utf-8")
        self.env = {"XC_ARITHMETIC_REFERENCE_JSON": str(self.ordinates),
            "XC_ARITHMETIC_REFERENCE_IDENTITY": str(self.identity_path)}

    def binding(self, n=1200):
        with mock.patch.dict(reproduce.os.environ, self.env, clear=True):
            return reproduce._external_input_binding(None, n)

    def journal(self):
        journal = self.root / "journal"
        journal.mkdir()
        (journal / "arithmetic-reference-ordinates.json").write_bytes(self.ordinates.read_bytes())
        (journal / "arithmetic-reference-identity.json").write_text(
            json.dumps({"identity": self.identity, "scope": "test"}), encoding="utf-8")
        report = self.root / "report.json"
        report.write_text(json.dumps({"journal": str(journal)}), encoding="utf-8")
        return report, journal

    def test_small_configuration_keeps_original_binding(self):
        self.ordinates.unlink()
        self.assertEqual(self.binding(1064), {"target_sha256": None})

    def test_missing_pair_or_insufficient_prefix_fails_before_claim(self):
        with mock.patch.dict(reproduce.os.environ,
                {"XC_ARITHMETIC_REFERENCE_JSON": str(self.ordinates)}, clear=True):
            with self.assertRaisesRegex(ValueError, "both JSON and identity"):
                reproduce._external_input_binding(None, 1100)
        with self.assertRaisesRegex(ValueError, "prefix coverage"):
            self.binding(1201)

    def test_mutated_input_does_not_reuse_old_identity(self):
        self.ordinates.write_text('["14.134726"]', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "identity or prefix"):
            self.binding()

    def test_retained_input_and_identity_are_checked_again_at_sealing(self):
        configuration = {"external_inputs": self.binding()}
        report, journal = self.journal()
        reproduce._check_arithmetic_reference_binding(report, configuration)
        path = journal / "arithmetic-reference-ordinates.json"
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "differs from the admitted"):
            reproduce._check_arithmetic_reference_binding(report, configuration)

    def test_retained_identity_change_is_rejected(self):
        configuration = {"external_inputs": self.binding()}
        report, journal = self.journal()
        changed = dict(self.identity, resource="different/producer")
        (journal / "arithmetic-reference-identity.json").write_text(
            json.dumps({"identity": changed}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "differs from the admitted"):
            reproduce._check_arithmetic_reference_binding(report, configuration)

    def test_unexpected_or_unjournaled_extension_is_rejected(self):
        report, _ = self.journal()
        with self.assertRaisesRegex(ValueError, "unexpected explicit"):
            reproduce._check_arithmetic_reference_binding(report, {})
        report.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "lacks a retained journal"):
            reproduce._check_arithmetic_reference_binding(report, {"external_inputs": self.binding()})
        reproduce._check_arithmetic_reference_binding(report, {})


if __name__ == "__main__":
    unittest.main()
