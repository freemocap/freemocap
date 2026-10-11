"""Parity reporting must not hide missingness, schema or numerical regressions."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from freemocap.tools.datasets.tracker_comparison import NumericalComparison, render_comparison


class TrackerComparisonTests(unittest.TestCase):
    def test_cpu_only_runtime_does_not_pretend_to_test_cuda(self):
        from freemocap.tools.datasets.tracker_comparison import run_comparison
        with TemporaryDirectory() as temporary, patch("onnxruntime.get_available_providers", return_value=["CPUExecutionProvider"]):
            report = run_comparison(recording=Path(temporary) / "absent-recording", case="rtmpose_cuda",
                                    output=Path(temporary) / "report")
        self.assertEqual(report["status"], "unsupported")
        self.assertEqual(report["paths"], {})

    def test_identical_data_including_missing_values_passes(self):
        comparison = NumericalComparison()
        value = {"names": ["hip"], "xyz": [1.0, float("nan"), 2.0], "frame": 2}
        comparison.compare(value, value)
        self.assertTrue(comparison.report()["passed"])
        self.assertEqual(comparison.numerical_values, 2)

    def test_missingness_identity_and_structure_are_not_tolerated(self):
        for actual in ({"xyz": [float("nan")], "frame": 1}, {"xyz": [2.0], "frame": 2},
                       {"xyz": [2.0, 3.0], "frame": 1}, {"frame": 1}):
            comparison = NumericalComparison()
            comparison.compare({"xyz": [2.0], "frame": 1}, actual)
            self.assertFalse(comparison.report()["passed"])
            self.assertGreater(comparison.structural_differences, 0)

    def test_numeric_errors_preserve_magnitude_and_threshold(self):
        comparison = NumericalComparison()
        comparison.compare([1.0, 2.0], [1.0 + 1e-8, 3.0])
        self.assertEqual(comparison.exact_differences, 2)
        self.assertEqual(comparison.outside_tolerance, 1)
        self.assertEqual(comparison.maximum_absolute_error, 1.0)

    def test_unsupported_is_not_reported_as_a_pass(self):
        report = dict(case="mediapipe_cuda", status="unsupported", scope="tracking", recording="test",
                      reason="No CUDA backend")
        text = render_comparison(report)
        self.assertIn("unsupported", text)
        self.assertIn("No CUDA backend", text)
        self.assertNotIn("NUMERICAL PARITY", text)
