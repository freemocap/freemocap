"""
Run both anipose and pyceres calibration on the same recording data
and compare the results side-by-side.

Runs each solver through the full PosthocPipelineManager pipeline (charuco
detection → calibration → save), preserves both TOML outputs, loads them
back as CalibrationResult, and prints a structured comparison.

Configure the recording path and board parameters in the ``__main__`` block.
"""

import json
import logging
import multiprocessing
import shutil
import time
from pathlib import Path

from freemocap.core.pipeline.posthoc.posthoc_calibration_task.shared.calibration_models import CalibrationResult, \
    CharucoCornersObservation
from freemocap.core.pipeline.posthoc.posthoc_calibration_task.shared.calibration_paths import (
    create_camera_calibration_file_name,
)

from freemocap.core.pipeline.posthoc.posthoc_pipeline_manager import PosthocPipelineManager
from freemocap.core.pipeline.posthoc.video_group_helper import VideoGroupHelper
from freemocap.core.pipeline.shared.pipeline_configs import (
    CalibrationPipelineConfig,
    CalibrationSolverMethod,
)
from skellycam.core.ipc.process_management.process_registry import ProcessRegistry
from skellycam.core.recorders.videos.recording_info import RecordingInfo

from scripts.compare_calibrations import CalibrationComparisonResult, compare_calibration_results

logger = logging.getLogger(__name__)

SYNCHRONIZED_VIDEOS_SUBFOLDER = "synchronized_videos"
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}
POLL_INTERVAL_SECONDS = 0.5


def _find_videos_in_folder(folder: Path) -> list[str]:
    """Find all video files in a folder. Raises if none are found."""
    videos = sorted(
        str(p) for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
    )
    if not videos:
        raise FileNotFoundError(
            f"No video files ({', '.join(VIDEO_EXTENSIONS)}) found in {folder}"
        )
    return videos


def _resolve_video_paths(recording_path: Path) -> list[str]:
    """Resolve a recording directory into a list of video file paths."""
    if not recording_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {recording_path}")

    sync_subfolder = recording_path / SYNCHRONIZED_VIDEOS_SUBFOLDER
    if sync_subfolder.is_dir():
        logger.info(f"Found {SYNCHRONIZED_VIDEOS_SUBFOLDER}/ subfolder")
        return _find_videos_in_folder(sync_subfolder)

    return _find_videos_in_folder(recording_path)


def _run_single_pipeline(
    *,
    recording_path: Path,
    calibration_config: CalibrationPipelineConfig,
) -> None:
    """Run one calibration pipeline to completion."""
    recording_info = RecordingInfo(
        recording_name=recording_path.name,
        recording_directory=str(recording_path.parent),
    )

    global_kill_flag = multiprocessing.Value("b", False)
    process_registry = ProcessRegistry(global_kill_flag=global_kill_flag)
    process_registry.start_heartbeat()

    pipeline_manager = PosthocPipelineManager(
        global_kill_flag=global_kill_flag,
        process_registry=process_registry,
    )

    solver_name = calibration_config.solver_method.value
    logger.info(f"Launching {solver_name} calibration pipeline...")
    pipeline = pipeline_manager.create_calibration_pipeline(
        recording_info=recording_info,
        calibration_config=calibration_config,
    )
    logger.info(f"Pipeline [{pipeline.id}] started ({solver_name})")

    try:
        while pipeline.alive:
            time.sleep(POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        logger.info("Interrupted — shutting down pipeline...")
        pipeline_manager.shutdown()
        process_registry.shutdown_all()
        raise

    logger.info(f"Pipeline [{pipeline.id}] completed ({solver_name})")
    pipeline_manager.shutdown()
    process_registry.shutdown_all()


def run_both_and_compare(
    *,
    recording_path: Path,
    base_config: CalibrationPipelineConfig,
) -> CalibrationComparisonResult:
    """Run both anipose and pyceres calibration, then compare results.

    Runs each solver sequentially through the full pipeline. After each
    run the calibration TOML is copied to a solver-specific filename so
    the second run doesn't overwrite the first.

    Args:
        recording_path: Recording directory containing synchronized_videos/.
        base_config: Pipeline config with board parameters. The solver_method
                     field is overridden for each run.

    Returns:
        CalibrationComparisonResult with per-camera and aggregate metrics.
    """
    # Validate videos once up front
    video_paths = _resolve_video_paths(recording_path=recording_path)
    video_group = VideoGroupHelper.from_video_paths(video_paths=video_paths)
    first_meta = next(iter(video_group.video_metadata_by_id.values()))
    logger.info(
        f"Validated {len(video_group.video_ids)} videos, "
        f"{first_meta.frame_count} frames each, "
        f"{first_meta.width}x{first_meta.height} @ {first_meta.fps:.1f}fps"
    )

    calibration_filename = create_camera_calibration_file_name(
        recording_name=recording_path.name,
    )
    pipeline_output_toml = recording_path / calibration_filename

    # ---- Run anipose ----
    anipose_config = base_config.model_copy()
    anipose_config.solver_method = CalibrationSolverMethod.ANIPOSE

    _run_single_pipeline(
        recording_path=recording_path,
        calibration_config=anipose_config,
    )

    anipose_toml = recording_path / f"{recording_path.name}_anipose_calibration.toml"
    if not pipeline_output_toml.is_file():
        raise FileNotFoundError(
            f"Anipose pipeline did not produce expected output: {pipeline_output_toml}"
        )
    shutil.copy2(pipeline_output_toml, anipose_toml)
    logger.info(f"Anipose result preserved at: {anipose_toml}")

    # ---- Run pyceres ----
    pyceres_config = base_config.model_copy()
    pyceres_config.solver_method = CalibrationSolverMethod.PYCERES

    _run_single_pipeline(
        recording_path=recording_path,
        calibration_config=pyceres_config,
    )

    pyceres_toml = recording_path / f"{recording_path.name}_pyceres_calibration.toml"
    if not pipeline_output_toml.is_file():
        raise FileNotFoundError(
            f"Pyceres pipeline did not produce expected output: {pipeline_output_toml}"
        )
    shutil.copy2(pipeline_output_toml, pyceres_toml)
    logger.info(f"Pyceres result preserved at: {pyceres_toml}")

    # ---- Load and compare ----
    anipose_result = CalibrationResult.load_anipose_toml(path=anipose_toml)
    pyceres_result = CalibrationResult.load_anipose_toml(path=pyceres_toml)

    # Load saved observations for board reconstruction accuracy test
    observations_json_path = recording_path / "charuco_observations.json"
    all_observations: list[CharucoCornersObservation] | None = None
    if observations_json_path.is_file():
        raw_list = json.loads(observations_json_path.read_text())
        all_observations = [CharucoCornersObservation.model_validate(o) for o in raw_list]
        logger.info(f"Loaded {len(all_observations)} observations for board reconstruction test")
    else:
        logger.warning(
            f"No observations file at {observations_json_path} — "
            f"board reconstruction test will be skipped"
        )

    comparison = compare_calibration_results(
        result_a=anipose_result,
        result_b=pyceres_result,
        label_a="Anipose",
        label_b="Pyceres",
        all_observations=all_observations,
    )

    # Save comparison as JSON
    comparison_json_path = recording_path / f"{recording_path.name}_calibration_comparison.json"
    comparison_json_path.write_text(comparison.model_dump_json(indent=2))
    logger.info(f"Comparison saved to: {comparison_json_path}")

    return comparison


if __name__ == "__main__":

    RECORDING_PATH = (
        Path.home()
        / "freemocap_data"
        / "recording_sessions"
        / "freemocap_test_data2"
    )

    CONFIG = CalibrationPipelineConfig()
    CONFIG.charuco_board_x_squares = 7
    CONFIG.charuco_board_y_squares = 5
    comparison = run_both_and_compare(
        recording_path=RECORDING_PATH,
        base_config=CONFIG,
    )

    print("\n" + comparison.summary)