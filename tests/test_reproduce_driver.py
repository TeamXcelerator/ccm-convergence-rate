"""Unit tests for the non-numerical reproduction-driver behavior."""

import importlib.util
import io
import pathlib
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
        self.assertEqual(reproduce.verdict(True), "EXPLORATORY")
        self.assertEqual(reproduce.verdict(False), "EXPLORATORY")

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


if __name__ == "__main__":
    unittest.main()
