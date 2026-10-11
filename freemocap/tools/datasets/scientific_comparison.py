"""Real videos through tracking, frame triangulation, and canonical raw-3D saving."""
import argparse
from dataclasses import asdict
from contextlib import closing
import json
import multiprocessing
from pathlib import Path
import shutil
from time import perf_counter

import numpy as np
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.recorders.videos.recording_info import RecordingInfo

from freemocap.core.pipeline.dataflow.video_sources import RecordingVideoSources
from freemocap.core.pipeline.dataflow.tracker_adapter import SkellyTrackerAdapter
from freemocap.core.pipeline.dataflow.scientific_recording import process_scientific_recording, observation_buffers
from freemocap.core.pipeline.inference_service import InferenceService
from freemocap.core.pipeline.performance_report import PerformanceReport
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.tasks.calibration.shared.calibration_result import CalibrationResult
from freemocap.core.reconstruction.posthoc_reconstruction import triangulate_observation_buffers
from freemocap.core.reconstruction.posthoc_timing import PosthocTimingReport
from freemocap.core.recording.result_processing.observation_inputs import TrackerRecordingDefinition, DetectorRecordingDefinition
from freemocap.core.recording.result_processing.saved_reconstruction import read_saved_channel
from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
from freemocap.core.types.channel_kind import ChannelKind
from freemocap.system.recording_structure.recording_structure import RecordingStructure
from freemocap.tools.datasets.preparation import file_digest, software_identity


def render_report(report: dict) -> str:
    lines = ["SCIENTIFIC RECORDING COMPARISON", "=" * 40,
             f"Recording: {report['recording']}", f"Requested provider: {report['provider']}",
             f"Status: {report['status']}", f"Scope: {report['scope']}"]
    counts = report.get("frame_counts", {})
    lines += [f"Coverage: {len(counts)} videos; {sum(counts.values())} camera images total"]
    lines += [f"  {name}: {count} frames" for name, count in counts.items()]
    for name in ("tracking_matching_frame_triangulation_s", "batch_triangulation_s", "save_and_readback_s"):
        if name in report:
            lines.append(f"{name}: {report[name]:.3f} s")
    lines.append(f"Camera assignment: {report.get('matching_status', 'not evaluated')}")
    matching = report.get("camera_matching", {})
    if matching.get("fitness"):
        lines.append("Assignment fitness errors: pixels normalized to a 1000-pixel image diagonal")
        for camera in matching["fitness"]["cameras"]:
            lines.append(f"  {camera['camera_id']}: median={camera['median_error']:.3f}; "
                         f"p90={camera['p90_error']:.3f}; valid={camera['valid_fraction']:.1%}")
    policy = report.get("configuration", {}).get("camera_matching", {}).get("failure_policy")
    if policy:
        lines.append(f"Configured matching failure policy: {policy}; fitness status is retained unchanged")
    for name, comparison in report.get("frame_versus_batch", {}).items():
        lines.append(f"{name}: parity passed; {comparison['compared_values']} finite values; "
                     f"max absolute difference {comparison['maximum_absolute_error']:.6g}")
    if "error" in report:
        lines.append(f"Incomplete: {report['error']}")
    if "parquet" in report:
        lines.append(f"Validated saved recording: {report['parquet']}")
    lines.append("A solver comparison is not an end-to-end throughput benchmark.")
    return "\n".join(lines) + "\n"


def run_comparison(*, recording: Path, calibration: Path, output: Path, provider: str) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    report = dict(status="running", recording=str(recording), provider=provider,
                  scope="tracking through raw triangulation; no filtering, alignment, reconstruction or annotation")
    def save_report():
        (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        (output / "report.txt").write_text(render_report(report), encoding="utf-8")
    save_report()
    try:
        sources = RecordingVideoSources.resolve(recording)
        calibration_digest = file_digest(calibration)
        cameras = tuple(CalibrationResult.load_toml(calibration).cameras)
        if file_digest(calibration) != calibration_digest:
            raise ValueError("Calibration changed while loading")
        config = PosthocMocapPipelineConfig(charuco_tracking_enabled=False,
            video_fps=sources.camera_sources[0].video_metadata.fps, calibration_toml_path=str(calibration),
            export_to_blender=False)
        report.update(frame_counts={s.camera_id: s.video_metadata.frame_count for s in sources.camera_sources},
                      calibration_sha256=calibration_digest, configuration=config.model_dump(mode="json"),
                      software_identity=software_identity())
        performance = PerformanceReport()
        flag = multiprocessing.Value("b", False)
        registry = WorkerRegistry(global_kill_flag=flag, worker_mode=WorkerMode.THREAD)
        service = InferenceService(worker_registry=registry)
        service.start()
        started = perf_counter()
        try:
            adapter = SkellyTrackerAdapter(inference_service=service, tracker_config=config.tracker_config,
                performance_report=performance, execution_provider=provider)
            with closing(adapter.track_recording(sources=sources, execution_id="scientific-comparison", shutdown_flag=flag)) as events:
                result = process_scientific_recording(events=events, sources=sources, execution_id="scientific-comparison",
                    calibration_cameras=cameras, matching_config=config.camera_matching, triangulation_config=config.triangulation_config)
        finally:
            service.close()
            registry.remove_dead()
        report["tracking_matching_frame_triangulation_s"] = perf_counter() - started
        report["tracking_timings"] = performance.snapshot()
        report["matching_status"] = result.matching_result.status.value
        report["camera_matching"] = asdict(result.matching_result)
        started = perf_counter()
        baseline = triangulate_observation_buffers(
            observation_buffers=observation_buffers(result.observations.frames, result.observations.cameras),
            camera_geometry=result.camera_geometry, triangulation_config=config.triangulation_config,
            max_reprojection_error_px=None, timing=PosthocTimingReport())
        report["batch_triangulation_s"] = perf_counter() - started
        comparison = {}
        for name in ("points_3d", "per_camera_weights", "reprojection_error"):
            left, right = getattr(baseline.reconstruction, name), getattr(result.triangulation.reconstruction, name)
            np.testing.assert_array_equal(np.isnan(left), np.isnan(right))
            np.testing.assert_allclose(left, right, atol=1e-8, rtol=1e-10)
            difference = np.abs(left[np.isfinite(left)] - right[np.isfinite(left)])
            comparison[name] = dict(compared_values=int(difference.size), maximum_absolute_error=float(difference.max(initial=0)))
        for name in ("errors", "observed", "reconstructed", "weights"):
            np.testing.assert_allclose(getattr(baseline.reconstruction.diagnostics, name),
                getattr(result.triangulation.reconstruction.diagnostics, name), atol=1e-8, rtol=1e-10)
        report["frame_versus_batch"] = comparison
        # Self-contained private result recording; originals and accepted datasets are untouched.
        destination = output / recording.name
        videos = destination / "synchronized_videos"
        videos.mkdir(parents=True)
        for source in sources.camera_sources:
            shutil.copy2(source.video_metadata.file_path, videos / source.video_metadata.file_path.name)
        shutil.copy2(calibration, destination / calibration.name)
        configuration = config.model_dump(mode="json")
        configuration["execution"] = {"requested_provider": provider,
            "runtime_placement_verified": False, "timestamp_policy": "relative_recording_group_milliseconds"}
        started = perf_counter()
        metadata = result.save(recording_info=RecordingInfo(recording_name=recording.name, recording_directory=str(output)),
            tracker_definition=TrackerRecordingDefinition(name=f"keypoint_model:{config.rtmpose_model_name}",
                point_names=result.triangulation.diagnostic_point_names, configuration=configuration),
            detector_definition=DetectorRecordingDefinition(name="object_detector:yolox-m", box_names=("body",), configuration=configuration))
        structure = RecordingStructure(base_directory=output, recording_name=recording.name)
        metadata = read_metadata(path=structure.data_parquet_path)
        stored_assignment = metadata.runs[0].sources[f"keypoint_model:{config.rtmpose_model_name}"].definition["camera_assignment"]
        if stored_assignment["status"] != result.matching_result.status.value:
            raise ValueError("Saved camera fitness status differs from the measured result")
        report["saved_camera_assignment"] = stored_assignment
        channel = next(c for c in metadata.runs[0].channels if c.kind == ChannelKind.RAW_KEYPOINTS_3D)
        saved = read_saved_channel(structure=structure, run_id=0, metadata=metadata, channel=channel)
        np.testing.assert_array_equal(saved.values, result.triangulation.reconstruction.points_3d)
        report.update(status="passed", save_and_readback_s=perf_counter() - started,
                      saved_shape=list(saved.values.shape), parquet=str(structure.data_parquet_path),
                      parquet_sha256=file_digest(structure.data_parquet_path))
    except Exception as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
    save_report()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recording", type=Path)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New ignored diagnostic directory")
    parser.add_argument("--provider", choices=("cpu", "cuda"), default="cpu")
    args = parser.parse_args()
    report = run_comparison(recording=args.recording, calibration=args.calibration, output=args.output, provider=args.provider)
    print(render_report(report))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
