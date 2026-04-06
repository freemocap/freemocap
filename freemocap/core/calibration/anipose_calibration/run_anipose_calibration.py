"""Run anipose-based camera calibration (legacy solver).

Accepts the shared CharucoBoardDefinition and returns a CalibrationResult,
so both solver paths produce the same output type.
"""

import logging
import time
from pathlib import Path

from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraIdString
from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseRecorder
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation

from freemocap.core.calibration.anipose_calibration.anipose_adapters import create_anipose_board, \
    anipose_group_to_camera_models
from freemocap.core.calibration.anipose_calibration.helpers.calibration_helpers import anipose_pin_camera_zero_to_origin, \
    set_charuco_board_as_groundplane, get_real_world_matrices
from freemocap.core.calibration.anipose_calibration.helpers.freemocap_anipose import AniposeCamera, AniposeCameraGroup
from freemocap.core.calibration.shared.calibration_models import CharucoBoardDefinition, CalibrationResult
from freemocap.core.calibration.shared.groundplane_alignment import GroundPlaneResult
from freemocap.core.calibration.shared.charuco_observation_aggregator import CharucoObservationAggregator
from freemocap.core.pipeline.pipeline_configs import CalibrationPipelineConfig
from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata
from freemocap.core.types.type_overloads import VideoIdString

logger = logging.getLogger(__name__)


def run_anipose_calibration(
    *,
    charuco_observations_by_frame: list[dict[CameraIdString, CharucoObservation]],
    board: CharucoBoardDefinition,
    calibration_pipeline_config: CalibrationPipelineConfig,
    video_metadata: dict[VideoIdString, VideoMetadata],
    recording_info: RecordingInfo,
    pin_camera_0_to_origin: bool = True,
    use_charuco_as_groundplane: bool = False,
    init_intrinsics: bool = True,
    init_extrinsics: bool = True,
    verbose: bool = True,
) -> tuple[CalibrationResult, GroundPlaneResult | None]:
    """Run anipose calibration from charuco observations.

    Returns a CalibrationResult with optimized camera models.
    """
    t_start = time.monotonic()

    anipose_cameras: list[AniposeCamera] = [
        AniposeCamera(
            name=video_id,
            size=(video_meta.width, video_meta.height),
        )
        for video_id, video_meta in video_metadata.items()
    ]
    anipose_camera_group = AniposeCameraGroup(cameras=anipose_cameras)
    anipose_charuco_board = create_anipose_board(board=board)

    logger.info(
        f"Starting Anipose calibration with "
        f"{len(charuco_observations_by_frame)} frames of charuco observations"
    )

    # Aggregate all observations into anipose row format
    charuco_observation_aggregator: CharucoObservationAggregator | None = None
    for charuco_observations_by_camera in charuco_observations_by_frame:
        if charuco_observation_aggregator is None:
            charuco_observation_aggregator = CharucoObservationAggregator.from_charuco_observation_payload(
                charuco_observations_by_camera=charuco_observations_by_camera,
                anipose_camera_ordering=[camera.name for camera in anipose_camera_group.cameras],
            )
        else:
            charuco_observation_aggregator.add_observations(charuco_observations_by_camera)

    if charuco_observation_aggregator is None:
        raise ValueError("No charuco observations were provided for calibration")

    # Run anipose bundle adjustment
    all_camera_rows = charuco_observation_aggregator.all_camera_rows
    logger.info(f"Aggregated charuco observations for {len(all_camera_rows)} cameras")
    error, merged, charuco_frame_numbers = anipose_camera_group.calibrate_rows(
        all_camera_rows,
        anipose_charuco_board,
        init_intrinsics=init_intrinsics,
        init_extrinsics=init_extrinsics,
        verbose=verbose,
    )

    logger.info(f"Anipose calibration completed — error: {error}")

    # Add metadata
    anipose_camera_group.metadata["groundplane_calibration"] = False
    anipose_camera_group.metadata["recording_info"] = recording_info.model_dump()

    # Pin camera 0 to origin
    if pin_camera_0_to_origin:
        anipose_camera_group = anipose_pin_camera_zero_to_origin(camera_group=anipose_camera_group)
        logger.info("Pinned camera 0 to origin")

    # Ground plane correction
    ground_plane_result: GroundPlaneResult | None = None
    if use_charuco_as_groundplane:
        observation_recorders_by_video: dict[VideoIdString, BaseRecorder] = {
            video_id: BaseRecorder() for video_id in charuco_observations_by_frame[0].keys()
        }
        for frame_number, charuco_observations_by_camera in enumerate(charuco_observations_by_frame):
            if not all(
                isinstance(output, CharucoObservation) for output in charuco_observations_by_camera.values()
            ):
                raise ValueError(
                    f"Non-CharucoObservation found in frame {frame_number} observations"
                )
            for video_id, recorder in observation_recorders_by_video.items():
                recorder.add_observation(observation=charuco_observations_by_camera[video_id])

        anipose_camera_group, groundplane_success, ground_plane_result = set_charuco_board_as_groundplane(
            observation_recorders=observation_recorders_by_video,
            anipose_camera_group=anipose_camera_group,
            anipose_charuco_board=anipose_charuco_board,
            recording_folder_path=Path(recording_info.full_recording_path),
        )
        if groundplane_success.success:
            anipose_camera_group.metadata["groundplane_calibration"] = True
            logger.info("Successfully set charuco board as groundplane")
        else:
            logger.warning(f"Failed to set groundplane: {groundplane_success.error}")

    # Compute real-world camera positions and orientations
    get_real_world_matrices(camera_group=anipose_camera_group)

    # Convert anipose results to shared CameraModel types
    camera_models = anipose_group_to_camera_models(group=anipose_camera_group)

    elapsed = time.monotonic() - t_start

    result = CalibrationResult(
        cameras=camera_models,
        board=board,
        reprojection_error_px=float(error),
        initial_cost=0.0,
        final_cost=float(error),
        n_iterations=0,
        time_seconds=elapsed,
        n_observations_used=len(charuco_frame_numbers) * len(camera_models),
        n_observations_rejected=0,
    )
    return result, ground_plane_result
