"""Run anipose-based camera calibration using shared CameraModel types throughout.

Accepts the shared CharucoBoardDefinition and returns a CalibrationResult.
"""

import logging
import time
from pathlib import Path

from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraIdString
from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseRecorder
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation

from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata
from freemocap.core.tasks.calibration.anipose_calibration.helpers.anipose_calibration_helpers import (
    pin_camera_zero_to_origin,
    set_charuco_board_as_groundplane,
)
from freemocap.core.tasks.calibration.anipose_calibration.helpers.bundle_adjust import (
    calibrate_cameras_from_rows,
)
from freemocap.core.tasks.calibration.shared.camera_intrinsics import CameraIntrinsics
from freemocap.core.tasks.calibration.shared.camera_extrinsics import CameraExtrinsics
from freemocap.core.tasks.calibration.shared.camera_model import CameraModel
from freemocap.core.tasks.calibration.shared.calibration_result import CalibrationResult
from skellytracker.trackers.charuco_tracker import CharucoBoardDefinition
from freemocap.core.tasks.calibration.charuco_board.charuco_observation_aggregator import CharucoObservationAggregator
from freemocap.core.tasks.calibration.shared.groundplane_alignment import GroundPlaneResult
from freemocap.core.types.type_overloads import VideoIdString

logger = logging.getLogger(__name__)


def run_anipose_calibration(
    *,
    charuco_observations_by_frame: list[dict[CameraIdString, CharucoObservation]],
    board: CharucoBoardDefinition,
    video_metadata: dict[CameraIdString, VideoMetadata],
    recording_info: RecordingInfo,
    pin_camera_0_to_origin: bool = True,
    use_charuco_as_groundplane: bool = True,
) -> tuple[CalibrationResult, GroundPlaneResult | None]:
    """Run anipose calibration from charuco observations.

    Returns a CalibrationResult with optimized camera models.
    """
    t_start = time.monotonic()

    cameras: list[CameraModel] = [
        CameraModel(
            id=camera_id,
            index=video_meta.camera_index,
            image_size=(video_meta.width, video_meta.height),
            intrinsics=CameraIntrinsics.from_image_size(
                width=video_meta.width, height=video_meta.height
            ),
            extrinsics=CameraExtrinsics.identity(),
        )
        for camera_id, video_meta in video_metadata.items()
    ]

    logger.info(
        f"Starting Anipose calibration with "
        f"{len(charuco_observations_by_frame)} frames of charuco observations"
    )

    charuco_observation_aggregator: CharucoObservationAggregator | None = None
    for charuco_observations_by_camera in charuco_observations_by_frame:
        if charuco_observation_aggregator is None:
            charuco_observation_aggregator = CharucoObservationAggregator.from_charuco_observation_payload(
                charuco_observations_by_camera=charuco_observations_by_camera,
                anipose_camera_ordering=[cam.id for cam in cameras],
            )
        else:
            charuco_observation_aggregator.add_observations(charuco_observations_by_camera)

    if charuco_observation_aggregator is None:
        raise ValueError("No charuco observations were provided for calibration")

    all_camera_rows = charuco_observation_aggregator.to_anipose_rows(n_corners=board.n_corners)
    logger.info(f"Aggregated charuco observations for {len(all_camera_rows)} cameras")

    error, merged, charuco_frame_numbers = calibrate_cameras_from_rows(
        cameras=cameras,
        all_rows=all_camera_rows,
        board=board,
    )

    logger.info(f"Anipose calibration completed — error: {error}")

    if pin_camera_0_to_origin:
        cameras = pin_camera_zero_to_origin(cameras)
        logger.info("Pinned camera 0 to origin")

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

        cameras, groundplane_success, ground_plane_result = set_charuco_board_as_groundplane(
            observation_recorders=observation_recorders_by_video,
            cameras=cameras,
            board=board,
            recording_folder_path=Path(recording_info.full_recording_path),
        )
        if groundplane_success.success:
            logger.info("Successfully set charuco board as groundplane")
        else:
            logger.warning(f"Failed to set groundplane: {groundplane_success.error}")

    elapsed = time.monotonic() - t_start

    result = CalibrationResult(
        cameras=cameras,
        board=board,
        reprojection_error_px=float(error),
        initial_cost=0.0,
        final_cost=float(error),
        n_iterations=0,
        time_seconds=elapsed,
        n_observations_used=len(charuco_frame_numbers) * len(cameras),
        n_observations_rejected=0,
    )
    return result, ground_plane_result
