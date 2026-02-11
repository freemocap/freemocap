"""Run anipose-based camera calibration (legacy solver)."""

from pathlib import Path

from freemocap.core.pipeline.posthoc.posthoc_tasks.calibration_task.anipose_calibration.helpers.calibration_helpers import (
    GroundPlaneSuccess,
    pin_camera_zero_to_origin,
    set_charuco_board_as_groundplane,
    get_real_world_matrices,
    logger,
)
from freemocap.core.pipeline.posthoc.posthoc_tasks.calibration_task.anipose_calibration.helpers.freemocap_anipose import (
    AniposeCamera,
    AniposeCameraGroup,
    AniposeCharucoBoard,
)
from freemocap.core.pipeline.posthoc.posthoc_tasks.calibration_task.calibration_paths import (
    get_calibrations_folder_path,
    get_last_successful_calibration_toml_path,
    create_camera_calibration_file_name,
)
from freemocap.core.pipeline.posthoc.posthoc_tasks.calibration_task.charuco_observation_aggregator import (
    CharucoObservationAggregator,
)
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraIdString
from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseRecorder
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation

from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata
from freemocap.core.pipeline.shared.pipeline_configs import CalibrationPipelineConfig
from freemocap.core.types.type_overloads import VideoIdString


def run_anipose_calibration(
    *,
    charuco_observations_by_frame: list[dict[CameraIdString, CharucoObservation]],
    calibration_pipeline_config: CalibrationPipelineConfig,
    video_metadata: dict[VideoIdString, VideoMetadata],
    recording_info: RecordingInfo,
    pin_camera_0_to_origin: bool = True,
    use_charuco_as_groundplane: bool = False,
    init_intrinsics: bool = True,
    init_extrinsics: bool = True,
    verbose: bool = True,
) -> Path:
    """Run anipose calibration from charuco observations.

    Returns the path to the saved calibration TOML.
    """
    anipose_cameras: list[AniposeCamera] = [
        AniposeCamera(
            name=video_id,
            size=(video_meta.height, video_meta.width),
        )
        for video_id, video_meta in video_metadata.items()
    ]
    anipose_camera_group = AniposeCameraGroup(cameras=anipose_cameras)

    anipose_charuco_board = AniposeCharucoBoard(
        squaresX=calibration_pipeline_config.charuco_board_x_squares,
        squaresY=calibration_pipeline_config.charuco_board_y_squares,
        square_length=calibration_pipeline_config.charuco_square_length,
        marker_length=calibration_pipeline_config.charuco_square_length * 0.8,
    )
    logger.info(
        f"Starting Anipose calibration with {len(charuco_observations_by_frame)} frames of charuco observations"
    )

    # Aggregate all observations
    charuco_observation_aggregator: CharucoObservationAggregator | None = None
    for charuco_observations_by_camera in charuco_observations_by_frame:
        if charuco_observation_aggregator is None:
            charuco_observation_aggregator = CharucoObservationAggregator.from_charuco_observation_payload(
                charuco_observations_by_camera=charuco_observations_by_camera,
                anipose_camera_ordering=[camera.name for camera in anipose_camera_group.cameras],
            )
        charuco_observation_aggregator.add_observations(charuco_observations_by_camera)

    if charuco_observation_aggregator is None:
        raise ValueError("No charuco observations were provided for calibration")

    # Perform calibration on aggregated rows
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

    # Apply camera 0 pinning
    if pin_camera_0_to_origin:
        anipose_camera_group = pin_camera_zero_to_origin(camera_group=anipose_camera_group)
        logger.info("Pinned camera 0 to origin")

    # Apply groundplane correction
    if use_charuco_as_groundplane:
        observation_recorders_by_video = {
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

        anipose_camera_group, groundplane_success = set_charuco_board_as_groundplane(
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

    # Calculate real-world camera positions and orientations
    get_real_world_matrices(camera_group=anipose_camera_group)

    # Save to recording folder
    calibration_file_name = create_camera_calibration_file_name(
        recording_name=recording_info.recording_name,
    )
    recording_folder_calibration_toml_path = Path(recording_info.full_recording_path) / calibration_file_name
    anipose_camera_group.dump(recording_folder_calibration_toml_path)
    logger.info(f"Saved calibration to: {recording_folder_calibration_toml_path}")

    # Save to main calibrations folder
    calibration_folder_calibration_toml_path = get_calibrations_folder_path() / calibration_file_name
    anipose_camera_group.dump(calibration_folder_calibration_toml_path)
    logger.info(f"Saved calibration to: {calibration_folder_calibration_toml_path}")

    # Save as last successful calibration
    anipose_camera_group.dump(get_last_successful_calibration_toml_path())
    logger.info(f"Saved as last successful calibration: {get_last_successful_calibration_toml_path()}")

    return recording_folder_calibration_toml_path
