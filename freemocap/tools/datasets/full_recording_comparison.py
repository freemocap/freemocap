"""Complete experimental recording graph versus the current scientific task.

Tracking runs once; both scientific paths consume identical observations. This is
downstream parity, not a full old/new tracking-throughput benchmark.
"""
import argparse
from contextlib import nullcontext
from dataclasses import replace, asdict
import json
from pathlib import Path
import shutil
import traceback
from time import perf_counter

import numpy as np
import cv2
from freemocap.core.pipeline.dataflow.annotation_workers import RecordingAnnotationWorkers

from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.timestamps.recording_timing_reader import recorded_camera_timing_path, recorded_multiframe_timing_path
from freemocap.core.pipeline.dataflow.video_sources import RecordingVideoSources
from freemocap.core.pipeline.dataflow.recording_pipeline import build_recording_pipeline
from freemocap.core.pipeline.dataflow.recording_executor import execute_recording_graph
from freemocap.core.pipeline.performance_report import PerformanceReport
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.tasks.mocap.posthoc_mocap_task import run_posthoc_mocap_task
from freemocap.core.tasks.calibration.shared.calibration_result import CalibrationResult
from freemocap.core.tracking.board_selection import CharucoBoardMode
from freemocap.core.reconstruction.posthoc_filtering import PosthocFilterConfig
from freemocap.core.reconstruction.recording_timing import RecordingGroupTiming
from freemocap.core.recording.exports.requests import ScientificExportOptions
from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
from freemocap.core.recording.result_processing.saved_reconstruction import (
    read_saved_channel, read_saved_reconstruction, SavedReconstructionRequest, SavedPointPolicy,
)
from freemocap.system.recording_structure.recording_structure import RecordingStructure
from freemocap.tools.datasets.validation import validate_outputs
from freemocap.tools.datasets.preparation import software_identity, file_digest


def private_recording(*, sources: RecordingVideoSources, calibration: Path, root: Path):
    destination = root / sources.recording_path.name
    (destination / "synchronized_videos").mkdir(parents=True, exist_ok=False)
    private_sources = []
    for source in sources.camera_sources:
        path = destination / "synchronized_videos" / source.video_metadata.file_path.name
        shutil.copy2(source.video_metadata.file_path, path)
        private_sources.append(replace(source, video_metadata=source.video_metadata.model_copy(update={"file_path": path})))
    calibration_copy = destination / calibration.name
    shutil.copy2(calibration, calibration_copy)
    timing_paths = [recorded_camera_timing_path(recording_folder=sources.recording_path, camera_id=source.camera_id)
                    for source in sources.camera_sources]
    timing_paths.append(recorded_multiframe_timing_path(recording_folder=sources.recording_path))
    for path in timing_paths:
        if path is not None and path.is_file():
            target = destination / path.relative_to(sources.recording_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    return replace(sources, recording_path=destination, camera_sources=tuple(private_sources)), calibration_copy


def compare_saved_channels(left: RecordingStructure, right: RecordingStructure) -> list[dict]:
    metadata = [read_metadata(path=structure.data_parquet_path) for structure in (left, right)]
    def compare_definition(expected, actual, path):
        if path.startswith('scale_fits/') and path.endswith(('/fit/measured_segment_names', '/fit/voting_segment_names')):
            # ModelScaleFit declares these as frozensets. JSON order varies with
            # each interpreter's hash seed; membership is the scientific contract.
            if sorted(expected) != sorted(actual):
                raise ValueError(f'Scientific segment membership differs: {path}')
            return
        if path.startswith("scale_fits/") and path.endswith("/inputs/points"):
            # Roundoff-equivalent arrays can have different exact byte hashes;
            # their complete numerical channels are compared below.
            return
        if isinstance(expected, dict):
            if not isinstance(actual, dict) or expected.keys() != actual.keys():
                raise ValueError(f"Scientific definition keys differ: {path}")
            for key in expected:
                compare_definition(expected[key], actual[key], f"{path}/{key}")
        elif isinstance(expected, list):
            if not isinstance(actual, list) or len(expected) != len(actual):
                raise ValueError(f"Scientific definition lengths differ: {path}")
            for index, (first, second) in enumerate(zip(expected, actual, strict=True)):
                compare_definition(first, second, f"{path}/{index}")
        elif isinstance(expected, float):
            np.testing.assert_allclose(actual, expected, atol=1e-6, rtol=1e-8, err_msg=path)
        elif expected != actual:
            raise ValueError(f"Scientific definition differs: {path}")
    # Compare equivalent arrays across routes, but verify each local fit fingerprint
    # against its own exact saved inputs using the production resume reader.
    for structure, item in zip((left, right), metadata, strict=True):
        run = item.runs[0]
        for fit in run.scale_fits:
            source = run.sources[fit.source].definition
            read_saved_reconstruction(SavedReconstructionRequest(structure=structure, run_id=0,
                sensor_group=fit.sensor_group, point_source=source["tracker"], model_id=source["model_id"],
                point_policy=SavedPointPolicy.FILTERED, compute_center_of_mass=True))
    definitions = [item.runs[0].model_dump(mode="json") for item in metadata]
    for name in ("sensor_groups", "reference_frames", "models", "camera_geometry", "static_channels", "scale_fits"):
        compare_definition(definitions[0][name], definitions[1][name], name)
    def channel_key(channel):
        return (channel.sensor_group, channel.source, channel.reference_frame, channel.kind)
    channels = [{channel_key(channel): channel for channel in item.runs[0].channels} for item in metadata]
    if channels[0].keys() != channels[1].keys():
        raise ValueError("Saved channel coverage differs")
    reports = []
    for key, channel in channels[0].items():
        other = channels[1][key]
        if channel != other:
            raise ValueError(f"Saved channel definitions differ: {key}")
        expected = read_saved_channel(structure=left, run_id=0, metadata=metadata[0], channel=channel)
        actual = read_saved_channel(structure=right, run_id=0, metadata=metadata[1], channel=other)
        if expected.frames != actual.frames or expected.timestamps_s != actual.timestamps_s:
            raise ValueError(f"Saved sample identity differs: {key}")
        np.testing.assert_array_equal(np.isnan(expected.values), np.isnan(actual.values))
        np.testing.assert_allclose(actual.values, expected.values, atol=1e-6, rtol=1e-8)
        finite = np.isfinite(expected.values)
        maximum = float(np.max(np.abs(actual.values[finite] - expected.values[finite]), initial=0))
        reports.append(dict(channel=list(key), values=int(expected.values.size), maximum_absolute_error=maximum,
                            absolute_tolerance=1e-6, relative_tolerance=1e-8))
    return reports


def render_report(report: dict) -> str:
    lines = ["FULL RECORDING GRAPH COMPARISON", "=" * 45, f"Status: {report['status']}",
             f"Execution: {report.get('execution_mode', 'concurrent')}; profiled: {report.get('profiled', False)}",
             f"Recording: {report.get('recording', 'unknown')}",
             f"Detector: {report.get('detector', 'unknown')}; requested provider: {report.get('provider', 'unknown')}",
             "Scope: shared tracking observations; compare complete scientific processing and saved channels."]
    if "camera_count" in report:
        lines.append(f"Coverage: {report['camera_count']} videos x {report['frames_per_camera']} frames each "
                     f"= {report['camera_count'] * report['frames_per_camera']} camera images")
    for name, seconds in report.get("operations_seconds", {}).items():
        frames = report.get("frames_per_camera", 0)
        rate = frames / seconds if seconds > 0 else 0
        unit = "video frames/s" if name.startswith("annotate_camera_") else "mocap frames/s"
        suffix = "" if name in ("observation_request", "spatial_request", "reconstruction_input") else f"   {rate:9.2f} {unit}"
        cpu = report.get("component_measurements", {}).get(name, {}).get("process_cpu_seconds")
        cpu_text = "" if cpu is None else f"   process CPU {cpu:.3f} s"
        lines.append(f"  {name:28} {seconds:10.3f} s{suffix}{cpu_text}")
    if report.get("execution_mode") == "isolated":
        lines.append("Diagnostic isolation: one graph handler at a time; internal batching/native workers remain enabled. Not a production scheduling proposal.")
        lines.append("Process CPU sums this process's threads; excludes GPU time and child-process CPU. Profiled runs include profiler overhead.")
    if report.get("operations_seconds"):
        lines.append("Rates are recording coverage / elapsed handler time, including resource contention; not exclusive CPU time. Overlapping durations must not be added.")
    if report.get("scientific_subphases"):
        lines.append("Matching / triangulation breakdown:")
        for stage in report["scientific_subphases"]:
            lines.append(f"  {stage['name']:36} {stage['elapsed_seconds']:9.3f} s")
    for name in ("graph_wall_seconds", "scientific_completion_seconds", "current_scientific_seconds"):
        if name in report:
            lines.append(f"{name}: {report[name]:.3f} s")
    workers = report.get("annotation_workers")
    if workers:
        lines.append(f"Annotation workers: launch {workers['launch_seconds']:.3f} s; shutdown {workers['shutdown_seconds']:.3f} s; alive afterward {workers['alive_after_close']}")
        lines.append("Process initialization overlaps graph work; any remaining readiness wait is included in each annotation handler.")
    if "motion_capture_throughput" in report:
        throughput = report["motion_capture_throughput"]
        lines.append(f"Full graph: {throughput['seconds_per_frame']:.6f} seconds per motion-capture frame; "
                     f"{throughput['frames_per_second']:.3f} motion-capture frames/s")
        lines.append("One motion-capture frame includes all cameras. Includes requested sinks and worker lifecycle; excludes comparison-harness verification.")
    lines.append("These wall times cover different work; they are not a speedup ratio.")
    for row in report.get("channels", []):
        lines.append(f"{' / '.join(str(item) for item in row['channel'])}: {row['values']} values; max difference {row['maximum_absolute_error']:.6g}")
    for name, count in sorted(report.get("tracking_counts", {}).items()):
        lines.append(f"{name}: {count}")
    for video in report.get("annotated_videos", []):
        lines.append(f"Annotated video: {video['camera']}: {video['frames']} frames")
    if report.get("blocked"):
        lines.append(f"Blocked operations: {report['blocked']}")
    if report.get("failures"):
        lines.append(f"Graph failures: {report['failures']}")
    if report.get("error"):
        lines.append(f"Error: {report['error']}")
    return "\n".join(lines) + "\n"


def run_comparison(*, recording: Path, calibration: Path, output: Path, provider: str,
                   annotate: bool = False, detector: str = "rtmpose", with_board: bool = False,
                   annotation_workers: int = 2, annotation_execution: str = "process",
                   isolate_components: bool = False, profile_components: bool = False) -> dict:
    if profile_components and not isolate_components:
        raise ValueError("Component profiling requires isolated execution")
    if annotation_execution not in ("thread", "process"):
        raise ValueError("Annotation execution must be thread or process")
    if annotation_workers < 1:
        raise ValueError("Annotation worker count must be positive")
    output.mkdir(parents=True, exist_ok=False)
    report = dict(status="running", recording=str(recording), provider=provider, detector=detector,
                  execution_mode="isolated" if isolate_components else "concurrent", profiled=profile_components)
    def write_report():
        if report.get("graph_wall_seconds", 0) > 0 and report.get("frames_per_camera", 0) > 0:
            seconds = report["graph_wall_seconds"]
            frames = report["frames_per_camera"]
            report["motion_capture_throughput"] = dict(frame_count=frames,
                seconds_per_frame=seconds/frames, frames_per_second=frames/seconds)
        (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        (output / "report.txt").write_text(render_report(report), encoding="utf-8")
    write_report()
    try:
        original = RecordingVideoSources.resolve(recording)
        report.update(camera_count=len(original.camera_sources),
                      frames_per_camera=original.camera_sources[0].video_metadata.frame_count)
        report["software"] = software_identity()
        report["calibration_sha256"] = file_digest(calibration)
        graph_sources, graph_calibration = private_recording(sources=original, calibration=calibration, root=output / "graph")
        baseline_sources, baseline_calibration = private_recording(sources=original, calibration=calibration, root=output / "current")
        fps = original.camera_sources[0].video_metadata.fps
        # Match the reference preparer's explicit filter choice for its 6-FPS test recording.
        config = PosthocMocapPipelineConfig(charuco_tracking_enabled=with_board, detector_type=detector,
            board_mode=CharucoBoardMode.EXPLICIT, charuco_board=CalibrationResult.load_toml(graph_calibration).board,
            calibration_toml_path=str(graph_calibration), video_fps=fps, export_to_blender=False,
            filter_config=PosthocFilterConfig(enabled=fps > 12),
            scientific_exports=ScientificExportOptions(formats=("npz",)))
        report["configuration"] = config.model_dump(mode="json")
        report["resource_capacity"] = dict(compute=2, annotation=annotation_workers, recording_io=1)
        performance = PerformanceReport()
        recording_info = RecordingInfo(recording_name=recording.name, recording_directory=str(output / "graph"))
        annotation_service = RecordingAnnotationWorkers(count=annotation_workers) if annotate and annotation_execution == "process" else None
        report["annotation_execution"] = annotation_execution if annotate else "disabled"
        graph, handlers = build_recording_pipeline(sources=graph_sources, recording=recording_info,
            config=config, execution_provider=provider, annotate=annotate, performance=performance,
            annotation_service=annotation_service)
        (output / "graph.json").write_text(graph.model_dump_json(indent=2), encoding="utf-8")
        report["phase"] = "graph_execution"
        write_report()
        started = perf_counter()
        with annotation_service if annotation_service is not None else nullcontext():
            execution_offset = perf_counter() - started
            if isolate_components:
                from freemocap.tools.datasets.component_diagnostics import measure_isolated_components
                result = measure_isolated_components(graph=graph, handlers=handlers,
                    output=output / "components", profile=profile_components)
            else:
                result = execute_recording_graph(graph=graph, handlers=handlers, resource_capacity=report["resource_capacity"])
        if isolate_components:
            report["component_measurements"] = json.loads((output / "components" / "components.json").read_text())["measurements"]
        if annotation_service is not None:
            report["annotation_workers"] = dict(launch_seconds=annotation_service.launch_seconds,
                shutdown_seconds=annotation_service.shutdown_seconds, jobs=annotation_service.measurements,
                alive_after_close=sum(worker.is_alive() for worker in annotation_service.workers))
        scientific_nodes = {node.id for node in graph.definition.nodes if not node.id.startswith("annotate_camera_")}
        if scientific_nodes.issubset(result.outputs):
            report["scientific_completion_seconds"] = execution_offset + max(
                result.finished_seconds[name] for name in scientific_nodes)
        report.update(graph_wall_seconds=perf_counter() - started, operations_seconds=result.elapsed_seconds,
            operation_started_seconds=result.started_seconds, operation_finished_seconds=result.finished_seconds,
            failures=result.failures, failure_tracebacks=result.failure_tracebacks,
            blocked=result.blocked, tracking_timings=performance.snapshot(),
            tracking_counts=performance.counts_snapshot())
        if "match_and_triangulate" in result.outputs:
            report["scientific_subphases"] = [asdict(stage) for stage in
                result.outputs["match_and_triangulate"]["result"].execution_timing.stages]
        write_report()
        if not result.complete:
            raise RuntimeError("Recording graph did not complete; see operation failures")
        annotation_reports = []
        if annotate:
            for index, source in enumerate(graph_sources.camera_sources):
                video_path = result.outputs[f"annotate_camera_{index}"]["result"]
                reader = cv2.VideoCapture(str(video_path))
                try:
                    count = int(reader.get(cv2.CAP_PROP_FRAME_COUNT))
                    if not reader.isOpened() or count != source.video_metadata.frame_count:
                        raise ValueError(f"Annotated video coverage differs: {source.camera_id}")
                    annotation_reports.append(dict(camera=source.camera_id, path=str(video_path), frames=count))
                finally:
                    reader.release()
        report["annotated_videos"] = annotation_reports
        collection = result.outputs["load_and_track"]["result"]
        baseline_config = config.model_copy(update={"calibration_toml_path": str(baseline_calibration), "sensor_group": original.sensor_group})
        report["phase"] = "current_scientific_task"
        write_report()
        started = perf_counter()
        run_posthoc_mocap_task(frame_observations=collection.frames,
            recording_info=RecordingInfo(recording_name=recording.name, recording_directory=str(output / "current")),
            video_metadata={source.camera_id: source.video_metadata for source in baseline_sources.camera_sources},
            task_config=baseline_config, selected_board=config.charuco_board if with_board else None,
            saved_timing=None)
        report["current_scientific_seconds"] = perf_counter() - started
        report["phase"] = "saved_output_validation"
        write_report()
        structures = [RecordingStructure(base_directory=output / route, recording_name=recording.name) for route in ("current", "graph")]
        report["validation"] = [validate_outputs(output / route / recording.name,
            expected_frames=original.camera_sources[0].video_metadata.frame_count) for route in ("current", "graph")]
        report["channels"] = compare_saved_channels(*structures)
        saved_graph = read_metadata(path=structures[1].data_parquet_path)
        assignment = saved_graph.runs[0].processing[original.sensor_group]["camera_assignment"]
        if set(assignment["source_to_calibration"]) != {source.camera_id for source in original.camera_sources}:
            raise ValueError("Saved camera assignment does not cover the source cameras")
        if assignment["error_units"] != "pixels_at_1000_pixel_image_diagonal":
            raise ValueError("Saved camera assignment diagnostic units differ")
        report["camera_assignment"] = assignment
        report["status"] = "passed"
        report["phase"] = "complete"
    except Exception as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
        report["traceback"] = traceback.format_exc()
    write_report()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recording", type=Path)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provider", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--detector", choices=("rtmpose", "mediapipe"), default="rtmpose")
    parser.add_argument("--annotate", action="store_true")
    parser.add_argument("--annotation-workers", type=int, default=2,
                        help="Experimental annotation concurrency; does not change scientific work")
    parser.add_argument("--annotation-execution", choices=("thread", "process"), default="process")
    parser.add_argument("--isolate-components", action="store_true", help="Diagnostic: run graph handlers one at a time")
    parser.add_argument("--profile-components", action="store_true", help="Profile isolated handler thread; timings include profiler overhead")
    parser.add_argument("--with-board", action="store_true", help="Track the explicit board recorded in the selected calibration")
    args = parser.parse_args()
    report = run_comparison(recording=args.recording, calibration=args.calibration, output=args.output,
                            provider=args.provider, annotate=args.annotate, detector=args.detector, with_board=args.with_board,
                            annotation_workers=args.annotation_workers, annotation_execution=args.annotation_execution,
                            isolate_components=args.isolate_components, profile_components=args.profile_components)
    print(render_report(report))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
