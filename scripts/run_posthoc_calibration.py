"""
Run posthoc camera calibration from synchronized video files.

Uses VideoGroupHelper to validate that all videos are synchronized (matching
frame counts), then runs the full PosthocPipelineManager calibration pipeline
with either the Anipose or Pyceres solver.

Accepts three input forms:
  - A recording path containing a ``synchronized_videos/`` subfolder
  - A folder path containing video files directly
  - An explicit list of video file paths

Configure the constants in the ``__main__`` block at the bottom.
"""

import logging
import multiprocessing
import time
from pathlib import Path

from freemocap.core.pipeline.posthoc.posthoc_pipeline_manager import PosthocPipelineManager
from freemocap.core.pipeline.posthoc.video_group_helper import VideoGroupHelper
from freemocap.core.pipeline.shared.pipeline_configs import (
    CalibrationPipelineConfig,
    CalibrationSolverMethod,
)
from skellycam.core.ipc.process_management.process_registry import ProcessRegistry
from skellycam.core.recorders.videos.recording_info import RecordingInfo


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


def _resolve_video_paths(recording_path: Path | list[str]) -> list[str]:
    """Resolve any of the three supported input forms into a list of video file paths.

    Accepted inputs:
      - ``Path`` to a recording directory containing a ``synchronized_videos/`` subfolder
      - ``Path`` to a folder containing video files directly
      - ``list[str]`` of explicit video file paths
    """
    if isinstance(recording_path, list):
        for p in recording_path:
            if not Path(p).is_file():
                raise FileNotFoundError(f"Video file not found: {p}")
        return sorted(recording_path)

    if not recording_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {recording_path}")

    sync_subfolder = recording_path / SYNCHRONIZED_VIDEOS_SUBFOLDER
    if sync_subfolder.is_dir():
        logger.info(f"Found {SYNCHRONIZED_VIDEOS_SUBFOLDER}/ subfolder — treating as recording path")
        return _find_videos_in_folder(sync_subfolder)

    logger.info(f"No {SYNCHRONIZED_VIDEOS_SUBFOLDER}/ subfolder — treating as video folder")
    return _find_videos_in_folder(recording_path)




def run_posthoc_calibration(
    *,
    recording_path: Path ,
    calibration_config:CalibrationPipelineConfig,
) -> None:
    """Validate videos, set up recording directory, and run the calibration pipeline.

    Args:
        recording_path: A recording directory (must contain ``synchronized_videos/``)
        solver_method: Which calibration solver to use.
    """
    video_paths = _resolve_video_paths(recording_path=recording_path)

    # Validate that all videos are synchronized (same frame count)
    logger.info(f"Validating {len(video_paths)} videos via VideoGroupHelper...")
    video_group = VideoGroupHelper.from_video_paths(video_paths=video_paths)
    first_meta = next(iter(video_group.video_metadata_by_id.values()))
    logger.info(
        f"Validation passed: {len(video_group.video_ids)} videos, "
        f"{first_meta.frame_count} frames each, "
        f"{first_meta.width}x{first_meta.height} @ {first_meta.fps:.1f}fps"
    )


    recording_info = RecordingInfo(
        recording_name=recording_path.name,
        recording_directory=str(recording_path.parent),
    )



    # Create the multiprocessing infrastructure the pipeline requires
    global_kill_flag: multiprocessing.Value = multiprocessing.Value("b", False)
    process_registry = ProcessRegistry(
        global_kill_flag=global_kill_flag,
    )
    process_registry.start_heartbeat()

    pipeline_manager = PosthocPipelineManager(
        global_kill_flag=global_kill_flag,
        process_registry=process_registry,
    )

    # Launch the calibration pipeline (starts all worker processes)
    logger.info(f"Launching calibration pipeline with solver: {calibration_config.solver_method.value}")
    pipeline = pipeline_manager.create_calibration_pipeline(
        recording_info=recording_info,
        calibration_config=calibration_config,
    )
    logger.info(f"Pipeline [{pipeline.id}] started")

    # Poll until the pipeline finishes (all worker processes exit)
    try:
        while pipeline.alive:
            time.sleep(POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        logger.info("Interrupted — shutting down pipeline...")
        pipeline_manager.shutdown()
        process_registry.shutdown_all()
        raise

    logger.info(f"Pipeline [{pipeline.id}] completed. Output saved to {recording_path}")
    pipeline_manager.shutdown()
    process_registry.shutdown_all()


if __name__ == "__main__":
    RECORDING_PATH: Path | list[str] = Path().home() / "freemocap_data" / "recordings" / "2026-02-11_14-35-59_GMT-5_calibration"

    CONFIG: CalibrationPipelineConfig = CalibrationPipelineConfig()
    CONFIG.solver_method = CalibrationSolverMethod.PYCERES
    CONFIG.charuco_board_x_squares = 5
    CONFIG.charuco_board_y_squares = 3
    # CONFIG.solver_method = CalibrationSolverMethod.ANIPOSE
    # CONFIG.charuco_board_x_squares = 7
    # CONFIG.charuco_board_y_squares = 5

    run_posthoc_calibration(
        recording_path=RECORDING_PATH,
        calibration_config=CONFIG
    )