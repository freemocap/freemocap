"""Run detector/backend comparisons in isolated processes and summarize evidence."""
import argparse
import json
from pathlib import Path
import subprocess
import sys


TRACKER_CASES = ("charuco_cpu", "mediapipe_cpu", "rtmpose_cpu", "rtmpose_cuda", "mediapipe_cuda")


def compare_backend_observations(cpu_output: Path, cuda_output: Path) -> dict:
    """Measure backend differences without treating a regression threshold as accuracy."""
    from .tracker_comparison import NumericalComparison
    import numpy as np
    try:
        cpu = json.loads((cpu_output / "report.json").read_text(encoding="utf-8"))
        cuda = json.loads((cuda_output / "report.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return {"status": "not_compared", "reason": f"Missing or unreadable backend report: {error}"}
    if cpu["status"] != "passed" or cuda["status"] != "passed":
        return {"status": "not_compared", "reason": "Both same-backend comparisons must pass first"}
    if cpu["case"] != "rtmpose_cpu" or cuda["case"] != "rtmpose_cuda":
        raise ValueError("Cross-backend comparison requires RTMPose CPU and CUDA")
    for field in ("recording", "frame_counts", "tracker_config", "temporal_input"):
        if cpu.get(field) != cuda.get(field) or field not in cpu:
            raise ValueError(f"Incompatible backend comparison inputs: {field}")
    # Filenames use the report's insertion-ordered camera indices.
    if list(cpu["frame_counts"]) != list(cuda["frame_counts"]):
        raise ValueError("Different camera index assignments")
    comparison = NumericalComparison()
    pixel_errors = []
    visible_mask_changes = 0
    detector_schedule_changes = 0
    missing_point_set_frames = 0
    largest_pixel_difference = None
    for camera_index, frame_count in enumerate(cpu["frame_counts"].values()):
        for frame in range(frame_count):
            relative = Path("baseline_observations") / f"{camera_index}-{frame}.json"
            left = json.loads((cpu_output / relative).read_text(encoding="utf-8"))
            right = json.loads((cuda_output / relative).read_text(encoding="utf-8"))
            comparison.compare(left, right, str(relative))
            left_body = left["observation"]["stages"]["body"]
            right_body = right["observation"]["stages"]["body"]
            detector_schedule_changes += left_body["detector_ran"] != right_body["detector_ran"]
            left_points, right_points = left_body["keypoints"], right_body["keypoints"]
            if not left_points or not right_points or not left_points["names"] or not right_points["names"]:
                missing_point_set_frames += 1
                continue
            if left_points["names"] != right_points["names"]:
                raise ValueError("Point names differ; cannot report matched pixel errors")
            left_xy, right_xy = np.asarray(left_points["xyz"])[:, :2], np.asarray(right_points["xyz"])[:, :2]
            left_valid = np.isfinite(left_xy).all(axis=1) & (np.asarray(left_points["visibility"]) > 0)
            right_valid = np.isfinite(right_xy).all(axis=1) & (np.asarray(right_points["visibility"]) > 0)
            visible_mask_changes += int((left_valid != right_valid).sum())
            matched = left_valid & right_valid
            distances = np.linalg.norm(left_xy[matched] - right_xy[matched], axis=1)
            pixel_errors.extend(distances.tolist())
            if distances.size and (largest_pixel_difference is None or distances.max() > largest_pixel_difference["distance_px"]):
                point_index = int(np.flatnonzero(matched)[distances.argmax()])
                largest_pixel_difference = dict(camera=list(cpu["frame_counts"])[camera_index], frame=frame,
                    point=left_points["names"][point_index], distance_px=float(distances.max()),
                    cpu_xy=left_xy[point_index].tolist(), cuda_xy=right_xy[point_index].tolist(),
                    cpu_visibility=left_points["visibility"][point_index], cuda_visibility=right_points["visibility"][point_index])
    numbers = comparison.report()
    numbers.pop("passed")
    pixel_summary = dict(matched_visible_points=len(pixel_errors), different_visible_masks=visible_mask_changes,
                         different_detector_schedule_frames=detector_schedule_changes,
                         frames_without_matched_point_sets=missing_point_set_frames,
                         largest_difference=largest_pixel_difference)
    if pixel_errors:
        pixel_summary.update(zip(("median_px", "p95_px", "p99_px", "maximum_px"),
                                 np.percentile(pixel_errors, [50, 95, 99, 100]).tolist()))
    return {"status": "measured", "comparison": numbers, "body_xy_pixel_distances": pixel_summary,
            "interpretation": "CPU/CUDA differences, not an acceptance verdict. The 1e-6 threshold is descriptive only; quantities have mixed units."}


def matrix_summary(reports: list[dict]) -> str:
    lines = ["# Tracker comparison results", "",
             "Full recordings; each path uses fresh tracking state. Counts are camera-frame observations.", "",
             "| Recording | Detector/backend | Status | Observations per path | Baseline wall (s) | Adapter wall (s) | Max absolute difference |",
             "| --- | --- | --- | ---: | ---: | ---: | ---: |"]
    for report in reports:
        baseline = report.get("paths", {}).get("baseline", {})
        adapter = report.get("paths", {}).get("adapter", {})
        elapsed = lambda row: f"{row['elapsed_s']:.3f}" if "elapsed_s" in row else "—"
        lines.append(f"| {Path(report['recording']).name} | {report['case']} | {report['status']} | "
                     f"{baseline.get('observations', '—')} / {adapter.get('observations', '—')} | "
                     f"{elapsed(baseline)} | {elapsed(adapter)} | "
                     f"{report.get('comparison', {}).get('maximum_absolute_error', '—')} |")
    lines.extend(["", "Parity compares the sequential-read baseline with the bounded streaming adapter on the SAME backend.",
                  "The baseline uses the existing inference service, not the entire current posthoc pipeline.",
                  "Both paths receive the recording timeline (recorded or inferred). This corrects MediaPipe's processing-time fallback.",
                  "Wall times include asymmetric diagnostic serialization/comparison and cold/warm setup: no speedup claim.",
                  "CUDA provider registration is checked; individual ONNX kernel placement is not profiled.",
                  "Unsupported is not passed. MediaPipe exposes no CUDA backend here; ChArUco uses CPU.",
                  "These are default app model configurations, not every downloadable model variant.",
                  "Raw observations are private diagnostics; no accepted scientific recording outputs are saved.", ""])
    return "\n".join(lines)


def run_matrix(*, datasets: list[str], recordings_root: Path, output: Path) -> int:
    output.mkdir(parents=True, exist_ok=False)
    reports = []
    failed = False
    for dataset in datasets:
        for case in TRACKER_CASES:
            case_output = output / f"{dataset}-{case}"
            with (output / f"{dataset}-{case}.log").open("w", encoding="utf-8") as log:
                result = subprocess.run([
                    sys.executable, "-B", "-m", "freemocap.tools.datasets.tracker_comparison",
                    dataset, case, "--recordings-root", str(recordings_root), "--output", str(case_output),
                ], stdout=log, stderr=subprocess.STDOUT, check=False)
            report_path = case_output / "report.json"
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
                if not isinstance(report, dict) or not all(key in report for key in ("recording", "case", "status")):
                    raise ValueError("Invalid report header")
            except (OSError, ValueError) as error:
                report = {"recording": dataset, "case": case, "status": "failed",
                          "error": f"Unreadable report; inspect subprocess log: {error}"}
            # A crash must not leave a stale running/passed report looking successful.
            if result.returncode or report["status"] not in ("passed", "unsupported"):
                failed = True
                report = {**report, "status": "failed" if report["status"] in ("running", "passed") else report["status"],
                          "subprocess_exit_code": result.returncode}
            reports.append(report)
            (output / "matrix.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
            (output / "report.md").write_text(matrix_summary(reports), encoding="utf-8")
            print(f"{dataset} / {case}: {report['status']}", flush=True)
        try:
            cross_backend = compare_backend_observations(output / f"{dataset}-rtmpose_cpu",
                                                         output / f"{dataset}-rtmpose_cuda")
        except (OSError, ValueError, KeyError, TypeError) as error:
            cross_backend = {"status": "not_compared", "reason": f"Invalid backend evidence: {error}"}
            failed = True
        (output / f"{dataset}-cpu-versus-cuda.json").write_text(json.dumps(cross_backend, indent=2), encoding="utf-8")
    return int(failed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("datasets", nargs="+", choices=("test_data", "sample_data"))
    parser.add_argument("--recordings-root", type=Path, default=Path.home() / "freemocap_data/recordings")
    parser.add_argument("--output", type=Path, required=True, help="New ignored diagnostic directory")
    args = parser.parse_args()
    return run_matrix(datasets=list(dict.fromkeys(args.datasets)), recordings_root=args.recordings_root, output=args.output)


if __name__ == "__main__":
    raise SystemExit(main())
