"""
run_calibration_task: posthoc calibration processing.

Routes to either the legacy anipose solver or the new pyceres bundle
adjustment solver based on task_config.solver_method.

Both paths use the shared CharucoBoardDefinition for board geometry and
return a CalibrationResult. Saving is handled uniformly here via
CalibrationResult.dump_anipose_toml.

Called by PosthocAggregationNode after all frames are collected.
Pre-bind task_config via functools.partial when creating the pipeline.
"""

import json
import logging
from pathlib import Path

import numpy as np
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseRecorder
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation

from freemocap.core.calibration.anipose_calibration.run_anipose_calibration import run_anipose_calibration
from freemocap.core.calibration.pyceres_calibration.pyceres_calibration_pipeline import run_pyceres_calibration
from freemocap.core.calibration.shared.calibration_models import CharucoBoardDefinition, CharucoCornersObservation, \
    CornerObservation, CalibrationResult
from freemocap.core.calibration.shared.groundplane_alignment import GroundPlaneResult, groundplane_metadata
from freemocap.core.calibration.shared.calibration_paths import get_last_successful_calibration_toml_path
from freemocap.core.calibration.shared.calibration_save import save_calibration_copies
from freemocap.utilities.toml_mixin import numpy_to_python
from freemocap.core.mocap.mocap_helpers.charuco_model_from_observations import charuco_model_from_observations
from freemocap.core.pipeline.pipeline_configs import CalibrationPipelineConfig, CalibrationSolverMethod
from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata
from freemocap.core.types.type_overloads import VideoIdString
from scripts.compare_calibrations import compute_calibration_health

logger = logging.getLogger(__name__)


# =============================================================================
# SHARED: BOARD DEFINITION FACTORY
# =============================================================================


def _create_board(task_config: CalibrationPipelineConfig) -> CharucoBoardDefinition:
    """Create the shared charuco board definition from pipeline config.

    Single source of truth — both solver paths use this exact board.
    """
    return CharucoBoardDefinition(
        squares_x=task_config.charuco_board_x_squares,
        squares_y=task_config.charuco_board_y_squares,
        square_length_mm=task_config.detector_config.square_length,
        marker_length_mm=task_config.detector_config.marker_length,
    )


# =============================================================================
# SHARED: OBSERVATION CONVERSION
# =============================================================================


def _charuco_observation_to_frame_observation(
    *,
    charuco_obs: CharucoObservation,
    camera_name: str,
    frame_index: int,
) -> CharucoCornersObservation:
    """Convert a skellytracker CharucoObservation to a CharucoCornersObservation.

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

    return CharucoCornersObservation(
        camera_name=camera_name,
        frame_index=frame_index,
        corners=corners,
    )


def _convert_all_observations(
    *,
    charuco_observations_by_frame: list[dict[VideoIdString, CharucoObservation]],
) -> list[CharucoCornersObservation]:
    """Convert all charuco observations to CharucoCornersObservation models."""
    all_frame_obs: list[CharucoCornersObservation] = []

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
# SHARED: SAVE CALIBRATION RESULT
# =============================================================================


def _save_result(
    *,
    result: CalibrationResult,
    recording_info: RecordingInfo,
    solver_method: str,
    ground_plane: GroundPlaneResult | None = None,
) -> Path:
    """Save CalibrationResult to all standard locations via anipose-compatible TOML."""
    metadata: dict = {
        "solver_method": solver_method,
        "recording_info": recording_info.model_dump(),
    }
    if ground_plane is not None:
        metadata.update(groundplane_metadata(ground_plane, recording_info.recording_name))

    recording_toml = save_calibration_copies(
        save_fn=lambda path: result.dump_anipose_toml(path=path, metadata=metadata),
        recording_name=recording_info.recording_name,
        recording_folder_path=recording_info.full_recording_path,
    )

    return recording_toml


# =============================================================================
# PYCERES CALIBRATION PATH
# =============================================================================


def _run_pyceres_path(
    *,
    all_observations: list[CharucoCornersObservation],
    board: CharucoBoardDefinition,
    task_config: CalibrationPipelineConfig,
    video_metadata: dict[VideoIdString, VideoMetadata],
) -> tuple[CalibrationResult, GroundPlaneResult | None]:
    """Run calibration using the pyceres bundle adjustment solver."""
    if len(all_observations) == 0:
        raise ValueError("No valid charuco observations found")

    camera_names = list(video_metadata.keys())
    image_sizes: dict[str, tuple[int, int]] = {
        vid_id: (vm.width, vm.height)
        for vid_id, vm in video_metadata.items()
    }

    result, ground_plane = run_pyceres_calibration(
        board=board,
        all_observations=all_observations,
        image_sizes=image_sizes,
        camera_names=camera_names,
        config=task_config.pyceres_solver_config,
        use_groundplane=task_config.use_groundplane,
    )

    logger.info(
        f"Pyceres calibration complete — "
        f"reprojection error: {result.reprojection_error_px:.4f}px, "
        f"time: {result.time_seconds:.2f}s"
    )
    return result, ground_plane


# =============================================================================
# ANIPOSE CALIBRATION PATH (legacy)
# =============================================================================


def _run_anipose_path(
    *,
    charuco_observations_by_frame: list[dict[VideoIdString, CharucoObservation]],
    board: CharucoBoardDefinition,
    task_config: CalibrationPipelineConfig,
    recording_info: RecordingInfo,
    video_metadata: dict[VideoIdString, VideoMetadata],
) -> tuple[CalibrationResult, GroundPlaneResult | None]:
    """Run calibration using the legacy anipose solver."""
    logger.info("Starting anipose calibration...")

    result, ground_plane = run_anipose_calibration(
        charuco_observations_by_frame=charuco_observations_by_frame,
        board=board,
        calibration_pipeline_config=task_config,
        recording_info=recording_info,
        video_metadata=video_metadata,
        use_charuco_as_groundplane=task_config.use_groundplane,
    )

    logger.info(
        f"Anipose calibration complete — "
        f"reprojection error: {result.reprojection_error_px:.4f}px"
    )
    return result, ground_plane


# =============================================================================
# ENTRY POINT
# =============================================================================


def run_calibration_task(
    *,
    frame_observations: list[dict[VideoIdString, CharucoObservation]],
    recording_info: RecordingInfo,
    video_metadata: dict[VideoIdString, VideoMetadata],
    task_config: CalibrationPipelineConfig,
) -> None:
    """Run posthoc calibration on collected charuco observations.

    Routes to either the anipose or pyceres solver based on
    task_config.solver_method. Both paths produce a CalibrationResult
    that is saved via the same anipose-compatible TOML format.
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
    views_per_camera = {vid_id: len(charuco_observations_by_frame) for vid_id in video_ids}
    logger.debug(f"Received (video id: charuco observation count): {views_per_camera}")

    # ---- Create shared board definition ----
    board = _create_board(task_config=task_config)

    # ---- Convert to shared observation format (used by pyceres and health check) ----
    all_observations = _convert_all_observations(
        charuco_observations_by_frame=charuco_observations_by_frame,
    )

    # Save observations so comparison tools can run board reconstruction tests
    observations_json_path = Path(recording_info.full_recording_path) / "output_data"/"charuco_observations.json"
    observations_json_path.parent.mkdir(parents=True, exist_ok=True)
    observations_json_path.write_text(
        json.dumps([numpy_to_python(obs.model_dump()) for obs in all_observations], indent=4)
    )
    logger.info(f"Saved {len(all_observations)} charuco observations to {observations_json_path}")

    # ---- Route to solver ----
    logger.info(f"Using calibration solver: {task_config.solver_method.value}")

    ground_plane: GroundPlaneResult | None = None
    match task_config.solver_method:
        case CalibrationSolverMethod.ANIPOSE:
            result, ground_plane = _run_anipose_path(
                charuco_observations_by_frame=charuco_observations_by_frame,
                board=board,
                task_config=task_config,
                recording_info=recording_info,
                video_metadata=video_metadata,
            )
        case CalibrationSolverMethod.PYCERES:
            result, ground_plane = _run_pyceres_path(
                all_observations=all_observations,
                board=board,
                task_config=task_config,
                video_metadata=video_metadata,
            )
        case _:
            raise ValueError(f"Unknown solver method: {task_config.solver_method}")

    # ---- Save calibration result (unified for both paths) ----
    _save_result(
        result=result,
        recording_info=recording_info,
        solver_method=task_config.solver_method.value,
        ground_plane=ground_plane,
    )

    # ---- Log calibration health (including board reconstruction accuracy) ----
    health = compute_calibration_health(
        result=result,
        label=task_config.solver_method.value,
        all_observations=all_observations,
    )
    logger.info(f"\n{health.summary}")

    # ---- Build charuco board model from observations ----
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

    logger.info(
        f"Posthoc calibration complete! Output saved to {recording_info.full_recording_path}"
    )
