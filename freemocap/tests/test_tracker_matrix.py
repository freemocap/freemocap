"""One broken native subprocess must not erase evidence or skip other detectors."""
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from freemocap.tools.datasets.tracker_matrix import run_matrix, compare_backend_observations
from freemocap.tools.datasets import tracker_comparison  # Load native dependencies before mocking subprocess.run.


class TrackerMatrixTests(unittest.TestCase):
    def test_cross_backend_reports_pixel_distance_and_missingness_separately(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            for backend, coordinates, visibility in (
                ("cpu", [[0.0, 0.0, 0.0], [1.0, 1.0, 0.0]], [1.0, 1.0]),
                ("cuda", [[3.0, 4.0, 0.0], [float("nan"), float("nan"), 0.0]], [1.0, 0.0]),
            ):
                directory = root / backend
                (directory / "baseline_observations").mkdir(parents=True)
                report = dict(case=f"rtmpose_{backend}", status="passed", recording="same-recording",
                              frame_counts={"camera": 1}, tracker_config={}, temporal_input="same-timeline")
                (directory / "report.json").write_text(json.dumps(report))
                document = {"observation": {"stages": {"body": {
                    "detector_ran": True, "keypoints": {"names": ["a", "b"], "xyz": coordinates, "visibility": visibility},
                }}}}
                (directory / "baseline_observations/0-0.json").write_text(json.dumps(document))
            report = compare_backend_observations(root / "cpu", root / "cuda")
            self.assertEqual(report["status"], "measured")
            pixels = report["body_xy_pixel_distances"]
            self.assertEqual(pixels["maximum_px"], 5.0)
            self.assertEqual(pixels["matched_visible_points"], 1)
            self.assertEqual(pixels["different_visible_masks"], 1)
            self.assertNotIn("passed", report["comparison"])

    def test_crashed_and_truncated_cases_do_not_stop_later_datasets(self):
        with TemporaryDirectory() as temporary:
            output = Path(temporary) / "matrix"

            def run(command, **kwargs):
                case_output = Path(command[-1])
                case_output.mkdir()
                if "rtmpose_cpu" in case_output.name:
                    (case_output / "report.json").write_text('{"status":', encoding="utf-8")
                return subprocess.CompletedProcess(command, 1)

            with patch("freemocap.tools.datasets.tracker_matrix.subprocess.run", side_effect=run) as calls:
                result = run_matrix(datasets=["test_data", "sample_data"], recordings_root=Path(temporary), output=output)
            self.assertEqual(result, 1)
            self.assertEqual(calls.call_count, 10)
            reports = json.loads((output / "matrix.json").read_text(encoding="utf-8"))
            self.assertEqual(len(reports), 10)
            self.assertTrue(all(report["status"] == "failed" for report in reports))
            self.assertEqual(json.loads((output / "sample_data-cpu-versus-cuda.json").read_text())["status"], "not_compared")

    def test_missing_backend_evidence_is_not_a_pass(self):
        with TemporaryDirectory() as temporary:
            result = compare_backend_observations(Path(temporary) / "cpu", Path(temporary) / "cuda")
            self.assertEqual(result["status"], "not_compared")
