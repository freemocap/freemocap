"""Prepare reusable reference Parquet through isolated, real production pipelines.

Run with the repository Python: -B -m freemocap.tests.prepare_recording_dataset.
"""

import argparse
import hashlib
import importlib.metadata
import json
import logging
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from uuid import uuid4

from filelock import FileLock

from freemocap.tests.inspect_recording_datasets import inspect_recording
from freemocap.tests.recording_datasets import SAMPLE_DATA, TEST_DATA, acquire_recording, synchronized_video_directory

logger = logging.getLogger(__name__)
PREPARATION_VERSION = 1


def file_digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def software_identity() -> dict:
    """Fingerprint actual core files and installed dependency code, not branch names."""
    package = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    paths = sorted(path for path in package.rglob("*")
                   if path.is_file() and path.suffix in (".py", ".yaml", ".yml", ".json")
                   and "tests" not in path.relative_to(package).parts)
    for path in paths:
        digest.update(str(path.relative_to(package)).replace("\\", "/").encode())
        digest.update(path.read_bytes())
    dependencies = {}
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata["Name"]
        if not name:
            continue
        entry = {"version": distribution.version, "origin": distribution.read_text("direct_url.json")}
        if name.lower() in {"skellycam", "skellytracker", "skellyforge", "skellylogs"}:
            dependency_digest = hashlib.sha256()
            for path in sorted(distribution.files or (), key=str):
                if path.suffix in (".py", ".yaml", ".yml", ".json"):
                    resolved = Path(distribution.locate_file(path))
                    if resolved.is_file():
                        dependency_digest.update(str(path).encode())
                        dependency_digest.update(resolved.read_bytes())
            entry["content_sha256"] = dependency_digest.hexdigest()
        dependencies[name] = entry
    return {"core_sha256": digest.hexdigest(), "python": sys.version, "packages": dependencies}


def wait_for_success(manager, pipeline, *, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    last_detail = None
    while True:
        manager.refresh_progress()
        task = manager.registry.tasks[pipeline.id]
        if task.progress.detail != last_detail:
            logger.info("%s: %s (%s)", task.task_type, task.progress.detail, task.status)
            last_detail = task.progress.detail
        if task.status in ("failed", "cancelled"):
            raise RuntimeError(f"{task.task_type} {task.status}: {task.progress.detail}")
        if pipeline.id not in manager.pipelines:
            if task.status != "complete":
                raise RuntimeError(f"{task.task_type} stopped without successful completion: {task.progress.detail}")
            return task.model_dump(mode="json")
        if time.monotonic() >= deadline:
            raise TimeoutError(f"{task.task_type} exceeded {timeout}s: {task.progress.detail}")
        time.sleep(0.1)


def validate_parquet(recording: Path, *, expected_frames: int) -> dict:
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
    from freemocap.core.recording.sample_encoding.arrow_schema import SampleValidator
    from freemocap.core.skeletons.standard_human_skeleton import STANDARD_HUMAN_MODEL_ID
    from freemocap.system.recording_structure.recording_structure import RecordingStructure

    structure = RecordingStructure(base_directory=recording.parent, recording_name=recording.name)
    metadata = read_metadata(path=structure.data_parquet_path)
    if metadata.recording_id != recording.name:
        raise ValueError("Prepared recording identity does not match its directory")
    run = metadata.runs[metadata.selected_run_id]
    if STANDARD_HUMAN_MODEL_ID not in run.models:
        raise ValueError("Prepared recording has no standard human model")
    if len(run.sensor_groups) != 1 or any(group.sample_count != expected_frames for group in run.sensor_groups.values()):
        raise ValueError("Prepared recording does not cover the expected frame grid")
    if any(len(run.camera_geometry.get(group, ())) != 3 for group in run.sensor_groups):
        raise ValueError("Prepared recording must retain three calibrated cameras")
    validator = SampleValidator(metadata=metadata)
    finite_by_channel: dict[str, int] = {}
    rows = 0
    with pq.ParquetFile(structure.data_parquet_path) as parquet:
        for batch in parquet.iter_batches(batch_size=65536):
            batch = batch.replace_schema_metadata(None)
            validator.accept(batch=batch)
            rows += batch.num_rows
            for kind in ("OVERLAY_2D", "RAW_KEYPOINTS_3D", "KEYPOINTS_3D", "LANDMARKS_3D", "ROTATIONS_WORLD"):
                selected = batch.filter(pc.and_(pc.equal(batch.column("channel"), kind),
                                               pc.equal(batch.column("run_id"), metadata.selected_run_id)))
                finite = pc.sum(pc.cast(pc.fill_null(pc.is_finite(selected.column("value")), False), "int64")).as_py() or 0
                finite_by_channel[kind] = finite_by_channel.get(kind, 0) + finite
    validator.finish()
    if not all(finite_by_channel.values()):
        raise ValueError(f"Required channels contain no finite values: {finite_by_channel}")
    return {"rows": rows, "frames": expected_frames, "finite_values": finite_by_channel,
            "parquet_sha256": file_digest(structure.data_parquet_path),
            "calibration_updates": {key: value.model_dump(mode="json") for key, value in run.calibration_updates.items()}}


def run_worker(request_path: Path) -> None:
    """Called only in a dedicated process with FREEMOCAP_BASE_FOLDER isolated."""
    import multiprocessing
    from skellycam.core.ipc.process_management.managed_worker import WorkerMode
    from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
    from skellycam.core.recorders.videos.recording_info import RecordingInfo
    from skellylogs.handlers.websocket_log_queue_handler import create_websocket_log_queue
    from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition
    from freemocap.core.pipeline.inference_service import InferenceService
    from freemocap.core.pipeline.posthoc.posthoc_pipeline_manager import PosthocPipelineManager
    from freemocap.core.tasks.calibration.calibration_task_config import PosthocCalibrationPipelineConfig
    from freemocap.core.tasks.calibration.shared.calibration_paths import find_recording_calibration
    from freemocap.core.tasks.calibration.shared.calibration_result import CalibrationResult
    from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
    from freemocap.core.reconstruction.posthoc_filtering import PosthocFilterConfig
    from freemocap.core.tracking.board_selection import CharucoBoardMode

    request = json.loads(request_path.read_text(encoding="utf-8"))
    recording = Path(request["recording"])
    base = Path(os.environ["FREEMOCAP_BASE_FOLDER"])
    if base.resolve() != request_path.parent.resolve() / "app-data":
        raise ValueError("Preparation worker requires an isolated application directory")
    (base / "calibrations").mkdir(parents=True, exist_ok=True)
    create_websocket_log_queue()
    flag = multiprocessing.Value("b", False)
    registry = WorkerRegistry(global_kill_flag=flag, worker_mode=WorkerMode.THREAD)
    registry.start_heartbeat()
    service = InferenceService(worker_registry=registry)
    manager = PosthocPipelineManager(global_kill_flag=flag, worker_registry=registry, inference_service=service)
    info = RecordingInfo(recording_directory=str(recording.parent), recording_name=recording.name, mic_device_index=-1)
    board = CharucoBoardDefinition.create_test_data_7x5()
    try:
        service.start()
        calibration_config = PosthocCalibrationPipelineConfig(board_mode=CharucoBoardMode.EXPLICIT, charuco_board=board)
        calibration_task = manager.create_calibration_pipeline(recording_info=info, calibration_config=calibration_config)
        calibration_status = wait_for_success(manager, calibration_task, timeout=request["timeout"])
        calibration_path = find_recording_calibration(recording_folder=recording)
        if calibration_path is None:
            raise ValueError("Calibration task completed without a recording-local TOML")
        calibration = CalibrationResult.load_toml(calibration_path)
        if len(calibration.cameras) != 3 or not math.isfinite(calibration.reprojection_error_px):
            raise ValueError("Invalid prepared calibration")
        config = PosthocMocapPipelineConfig(
            calibration_toml_path=str(calibration_path), detector_type="rtmpose",
            board_mode=CharucoBoardMode.EXPLICIT, charuco_board=board,
            video_fps=request["fps"], export_to_blender=False, auto_open_blend_file=False,
            filter_config=PosthocFilterConfig(enabled=request["filtering_enabled"]),
        )
        mocap_task = manager.create_mocap_pipeline(recording_info=info, mocap_config=config)
        mocap_status = wait_for_success(manager, mocap_task, timeout=request["timeout"])
        validation = validate_parquet(recording, expected_frames=request["frames"])
        result = {"calibration_task": calibration_status, "mocap_task": mocap_status,
                  "calibration_config": calibration_config.model_dump(mode="json"),
                  "mocap_config": config.model_dump(mode="json"), "validation": validation,
                  "calibration": calibration.to_metadata().model_dump(mode="json"),
                  "calibration_filename": calibration_path.name, "calibration_sha256": file_digest(calibration_path)}
        (request_path.parent / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    finally:
        try:
            manager.shutdown()
        finally:
            try:
                service.close()
            finally:
                registry.shutdown_all()


def reuse_recording(root: Path, identity: dict) -> Path | None:
    marker = root / "ready.json"
    if not marker.is_file():
        return None
    ready = json.loads(marker.read_text(encoding="utf-8"))
    if ready["identity"] != identity:
        return None
    recording = Path(ready["recording"])
    if not recording.resolve().is_relative_to(root.resolve()):
        raise ValueError("Prepared recording escapes its preparation directory")
    result = ready["result"]
    parquet = recording / f"{recording.name}_data.parquet"
    calibration = recording / result["calibration_filename"]
    if not parquet.is_file() or file_digest(parquet) != result["validation"]["parquet_sha256"]:
        raise ValueError("Prepared Parquet changed or is missing; use --fresh to rebuild")
    if not calibration.is_file() or file_digest(calibration) != result["calibration_sha256"]:
        raise ValueError("Prepared calibration changed or is missing; use --fresh to rebuild")
    return recording


def execute_worker(command: list[str], *, environment: dict, log_path: Path, timeout: float) -> None:
    """Keep the full log and stream task progress without separate log access."""
    with log_path.open("w", encoding="utf-8") as log:
        with subprocess.Popen(command, env=environment, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                              creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0) as process:
            def relay():
                for line in process.stdout:
                    log.write(line)
                    log.flush()
                    if "calibration:" in line or "mocap:" in line or " ERROR " in line:
                        encoding = sys.stdout.encoding or "utf-8"
                        printable = line.encode(encoding, errors="backslashreplace").decode(encoding)
                        print(printable, end="", flush=True)
            reader = threading.Thread(target=relay, daemon=True)
            reader.start()
            try:
                code = process.wait(timeout=timeout)
            except BaseException:
                process.kill()
                process.wait()
                raise
            finally:
                reader.join(timeout=10.0)
            if code:
                raise subprocess.CalledProcessError(code, command)


def prepare(dataset, *, recordings_root: Path, prepared_root: Path, fresh: bool, timeout: float) -> Path:
    raw = acquire_recording(dataset, recordings_root=recordings_root)
    report = inspect_recording(dataset, recordings_root=recordings_root)
    identity = {"preparation_version": PREPARATION_VERSION, "source": report,
                "software": software_identity(), "preparer_sha256": file_digest(Path(__file__))}
    signature = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    root = prepared_root.expanduser().resolve() / dataset.name / signature[:16]
    # Never place generated files inside the downloaded recording.
    if root.is_relative_to(raw.resolve()) or raw.resolve().is_relative_to(root):
        raise ValueError("Prepared output must be separate from the raw recording")
    root.mkdir(parents=True, exist_ok=True)
    with FileLock(str(root / "prepare.lock"), timeout=timeout * 2 + 120):
        existing = None if fresh else reuse_recording(root, identity)
        if existing is not None:
            logger.info("Reusing validated preparation: %s", existing)
            return existing
        attempt = root / uuid4().hex[:8]
        recording = attempt / "recordings" / dataset.name
        folder = recording / "synchronized_videos"
        folder.mkdir(parents=True)
        for video in report["videos"]:
            destination = folder / video["filename"]
            shutil.copy2(synchronized_video_directory(raw) / video["filename"], destination)
            if file_digest(destination) != video["sha256"]:
                raise ValueError("Source video changed during preparation")
        shutil.copy2(raw / "charuco_board_info.json", recording / "charuco_board_info.json")
        request = {"recording": str(recording), "timeout": timeout,
                   "filtering_enabled": dataset.name == SAMPLE_DATA.name,
                   "frames": report["videos"][0]["decoded_frames"], "fps": report["videos"][0]["nominal_fps"]}
        request_path = attempt / "request.json"
        request_path.write_text(json.dumps(request, indent=2), encoding="utf-8")
        environment = dict(os.environ, FREEMOCAP_BASE_FOLDER=str(attempt / "app-data"), PYTHONUTF8="1")
        command = [sys.executable, "-B", "-m", "freemocap.tests.prepare_recording_dataset", "--worker", str(request_path)]
        logger.info("Running preparation; log: %s", attempt / "preparation.log")
        try:
            execute_worker(command, environment=environment, log_path=attempt / "preparation.log",
                           timeout=timeout * 2 + 120)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            logger.error("Preparation failed; log tail:\n%s", (attempt / "preparation.log").read_text(encoding="utf-8", errors="replace")[-10000:])
            raise
        result = json.loads((attempt / "result.json").read_text(encoding="utf-8"))
        ready = {"identity": identity, "recording": str(recording), "result": result}
        temporary = root / "ready.json.tmp"
        temporary.write_text(json.dumps(ready, indent=2), encoding="utf-8")
        temporary.replace(root / "ready.json")
        return recording


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--dataset", choices=("test", "sample"), default="test")
    parser.add_argument("--recordings-root", type=Path, default=Path.home() / "freemocap_data" / "recordings")
    parser.add_argument("--prepared-root", type=Path, default=Path.home() / "freemocap_data" / "testing" / "prepared")
    parser.add_argument("--fresh", action="store_true", help="Execute both pipelines again in a new attempt")
    parser.add_argument("--timeout", type=float, default=1800.0, help="Per-pipeline time limit in seconds")
    arguments = parser.parse_args()
    if not math.isfinite(arguments.timeout) or arguments.timeout <= 0:
        parser.error("--timeout must be finite and positive")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if arguments.worker:
        run_worker(arguments.worker)
    else:
        print(prepare(TEST_DATA if arguments.dataset == "test" else SAMPLE_DATA,
                      recordings_root=arguments.recordings_root, prepared_root=arguments.prepared_root,
                      fresh=arguments.fresh, timeout=arguments.timeout), flush=True)


if __name__ == "__main__":
    main()
