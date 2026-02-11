"""
run_calibration_task: posthoc calibration processing.

Routes to either the legacy anipose solver or the new pyceres bundle
adjustment solver based on task_config.solver_method.

Called by PosthocAggregationNode after all frames are collected.
Pre-bind task_config via functools.partial when creating the pipeline.
"""
import logging
from collections.abc import Callable
from pathlib import Path

import numpy as np
from freemocap.core.pipeline.posthoc.posthoc_tasks.calibration_task.anipose_calibration.run_anipose_calibration import (
    run_anipose_calibration,
)
from freemocap.core.pipeline.posthoc.posthoc_tasks.calibration_task.calibration_paths import (
    get_calibrations_folder_path,
    get_last_successful_calibration_toml_path,
    create_camera_calibration_file_name,
)
from freemocap.core.pipeline.posthoc.posthoc_tasks.calibration_task.charuco_model_from_observations import (
    charuco_model_from_observations,
)
from freemocap.core.pipeline.posthoc.posthoc_tasks.calibration_task.pyceres_calibration.helpers.models import (
    CharucoBoardDefinition,
    CornerObservation,
    FrameObservation,
)
from freemocap.core.pipeline.posthoc.posthoc_tasks.calibration_task.pyceres_calibration.helpers.toml_io import (
    save_calibration_toml,
)
from freemocap.core.pipeline.posthoc.posthoc_tasks.calibration_task.pyceres_calibration.pyceres_calibration_pipeline import (
    run_pyceres_calibration,
)
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseObservation, BaseRecorder
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation

from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata
from freemocap.core.pipeline.shared.pipeline_configs import (
    CalibrationPipelineConfig,
    CalibrationSolverMethod,
)
from freemocap.core.types.type_overloads import VideoIdString

logger = logging.getLogger(__name__)


# =============================================================================
# ADAPTER: CharucoObservation → FrameObservation
# =============================================================================


def _charuco_observation_to_frame_observation(
    *,
    charuco_obs: CharucoObservation,
    camera_name: str,
    frame_index: int,
) -> FrameObservation:
    """Convert a skellytracker CharucoObservation to a calibration FrameObservation.

    CharucoObservation.to_2d_array() returns shape (n_corners, 2) with NaN for
    undetected corners. The array index IS the corner ID.
    """
    points_2d = charuco_obs.to_2d_array()  # (n_corners, 2)

    corners: list[CornerObservation] = []
    for corner_id in range(points_2d.shape[0]):
        xy = points_2d[corner_id]
        if np.isnan(xy).any():
            continue
        corners.append(
            CornerObservation(
                corner_id=corner_id,
                pixel_xy=xy,
            )
        )

    return FrameObservation(
        camera_name=camera_name,
        frame_index=frame_index,
        corners=corners,
    )


def _convert_all_observations(
    *,
    charuco_observations_by_frame: list[dict[VideoIdString, CharucoObservation]],
) -> list[FrameObservation]:
    """Convert all charuco observations to FrameObservation models."""
    all_frame_obs: list[FrameObservation] = []

    for frame_idx, frame_obs_by_camera in enumerate(charuco_observations_by_frame):
        for camera_name, charuco_obs in frame_obs_by_camera.items():
            frame_obs = _charuco_observation_to_frame_observation(
                charuco_obs=charuco_obs,
                camera_name=camera_name,
                frame_index=frame_idx,
            )
            if frame_obs.n_corners > 0:
                all_frame_obs.append(frame_obs)

    return all_frame_obs


# =============================================================================
# PYCERES CALIBRATION PATH
# =============================================================================


def _run_pyceres_path(
    *,
    charuco_observations_by_frame: list[dict[VideoIdString, CharucoObservation]],
    task_config: CalibrationPipelineConfig,
    recording_info: RecordingInfo,
    video_metadata: dict[VideoIdString, VideoMetadata],
    report_progress: Callable[[str, float], None],
) -> Path:
    """Run calibration using the pyceres bundle adjustment solver."""
    report_progress("Converting observations", 0.05)

    board = CharucoBoardDefinition(
        squares_x=task_config.charuco_board_x_squares,
        squares_y=task_config.charuco_board_y_squares,
        square_length_mm=task_config.charuco_square_length,
        marker_length_mm=task_config.charuco_square_length * 0.8,
    )

    all_observations = _convert_all_observations(
        charuco_observations_by_frame=charuco_observations_by_frame,
    )
    if len(all_observations) == 0:
        raise ValueError("No valid charuco observations found after conversion")

    camera_names = list(video_metadata.keys())
    image_sizes: dict[str, tuple[int, int]] = {
        vid_id: (vm.width, vm.height)
        for vid_id, vm in video_metadata.items()
    }

    calibration_file_name = create_camera_calibration_file_name(
        recording_name=recording_info.recording_name,
    )
    output_toml_path = Path(recording_info.full_recording_path) / calibration_file_name

    report_progress("Running pyceres bundle adjustment", 0.1)

    result = run_pyceres_calibration(
        board=board,
        all_observations=all_observations,
        image_sizes=image_sizes,
        camera_names=camera_names,
        config=task_config.pyceres_solver_config,
        output_toml_path=output_toml_path,
        use_groundplane=task_config.use_groundplane,
        extra_metadata={
            "solver_method": "pyceres",
            "recording_info": recording_info.model_dump(),
        },
    )

    report_progress("Saving calibration copies", 0.9)

    # Save to calibrations folder + last successful
    calibration_folder_path = get_calibrations_folder_path() / calibration_file_name
    save_calibration_toml(
        result=result,
        path=calibration_folder_path,
        metadata={"solver_method": "pyceres", "recording_info": recording_info.model_dump()},
    )
    save_calibration_toml(
        result=result,
        path=get_last_successful_calibration_toml_path(),
        metadata={"solver_method": "pyceres", "recording_info": recording_info.model_dump()},
    )

    logger.info(
        f"Pyceres calibration complete — "
        f"reprojection error: {result.reprojection_error_px:.4f}px, "
        f"time: {result.time_seconds:.2f}s"
    )
    return output_toml_path


# =============================================================================
# ANIPOSE CALIBRATION PATH (legacy)
# =============================================================================


def _run_anipose_path(
    *,
    charuco_observations_by_frame: list[dict[VideoIdString, CharucoObservation]],
    task_config: CalibrationPipelineConfig,
    recording_info: RecordingInfo,
    video_metadata: dict[VideoIdString, VideoMetadata],
    report_progress: Callable[[str, float], None],
) -> Path:
    """Run calibration using the legacy anipose solver."""
    report_progress("Running anipose calibration", 0.1)
    logger.info("Starting anipose calibration...")

    calibration_toml_path = run_anipose_calibration(
        charuco_observations_by_frame=charuco_observations_by_frame,
        calibration_pipeline_config=task_config,
        recording_info=recording_info,
        video_metadata=video_metadata,
    )

    logger.info(f"Anipose calibration complete — saved to {calibration_toml_path}")
    return calibration_toml_path


# =============================================================================
# ENTRY POINT
# =============================================================================


def run_calibration_task(
    *,
    frame_observations: list[dict[VideoIdString, BaseObservation]],
    recording_info: RecordingInfo,
    video_metadata: dict[VideoIdString, VideoMetadata],
    report_progress: Callable[[str, float], None],
    task_config: CalibrationPipelineConfig,
) -> None:
    """Run posthoc calibration on collected charuco observations.

    Routes to either the anipose or pyceres solver based on
    task_config.solver_method.
    """
    video_ids = list(video_metadata.keys())

    # ---- Validate all observations are CharucoObservation ----
    charuco_observations_by_frame: list[dict[VideoIdString, CharucoObservation]] = []
    for frame_idx, frame_obs in enumerate(frame_observations):
        frame_charuco: dict[VideoIdString, CharucoObservation] = {}
        for vid_id, obs in frame_obs.items():
            if not isinstance(obs, CharucoObservation):
                raise TypeError(
                    f"Expected CharucoObservation for video {vid_id} frame {frame_idx}, "
                    f"got {type(obs).__name__}"
                )
            frame_charuco[vid_id] = obs
        charuco_observations_by_frame.append(frame_charuco)

    # ---- Route to solver ----
    logger.info(f"Using calibration solver: {task_config.solver_method.value}")

    match task_config.solver_method:
        case CalibrationSolverMethod.ANIPOSE:
            calibration_toml_path = _run_anipose_path(
                charuco_observations_by_frame=charuco_observations_by_frame,
                task_config=task_config,
                recording_info=recording_info,
                video_metadata=video_metadata,
                report_progress=report_progress,
            )
        case CalibrationSolverMethod.PYCERES:
            calibration_toml_path = _run_pyceres_path(
                charuco_observations_by_frame=charuco_observations_by_frame,
                task_config=task_config,
                recording_info=recording_info,
                video_metadata=video_metadata,
                report_progress=report_progress,
            )
        case _:
            raise ValueError(f"Unknown solver method: {task_config.solver_method}")

    report_progress("Calibration solver complete", 0.6)

    # ---- Build charuco board model from observations ----
    report_progress("Building charuco board model", 0.7)

    observation_recorders_by_video: dict[VideoIdString, BaseRecorder] = {
        vid_id: BaseRecorder() for vid_id in video_ids
    }
    for charuco_obs_by_camera in charuco_observations_by_frame:
        for vid_id, recorder in observation_recorders_by_video.items():
            recorder.add_observation(observation=charuco_obs_by_camera[vid_id])

    charuco_model_from_observations(
        observation_recorders=observation_recorders_by_video,
        calibration_toml_path=get_last_successful_calibration_toml_path(),
        output_data_folder=Path(recording_info.full_recording_path) / "output_data",
    )

    report_progress("Calibration complete", 1.0)
    logger.info(
        f"Posthoc calibration complete! Output saved to {recording_info.full_recording_path}"
    )
