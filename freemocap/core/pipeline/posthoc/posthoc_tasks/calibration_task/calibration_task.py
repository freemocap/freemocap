"""
run_calibration_task: posthoc calibration processing.

Extracted from the old PosthocCalibrationAggregationNode._run().
This is a plain function that receives collected observations and
runs anipose calibration + charuco model fitting.

Called by PosthocAggregationNode after all frames are collected.
Pre-bind task_config via functools.partial when creating the pipeline.
"""
import logging
from collections.abc import Callable
from pathlib import Path

from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseObservation, BaseRecorder
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation

from freemocap.core.pipeline.shared.pipeline_configs import CalibrationPipelineConfig
from freemocap.core.pipeline.posthoc.posthoc_tasks.calibration_task import \
    anipose_calibration_from_charuco_observations, get_last_successful_calibration_toml_path
from freemocap.core.pipeline.posthoc.posthoc_tasks.mocap_task.mocap_helpers.charuco_model_from_observations import \
    charuco_model_from_observations
from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata

from freemocap.core.types.type_overloads import VideoIdString

logger = logging.getLogger(__name__)


def run_calibration_task(
    *,
    frame_observations: list[dict[VideoIdString, BaseObservation]],
    recording_info: RecordingInfo,
    video_metadata: dict[VideoIdString, VideoMetadata],
    report_progress: Callable[[str, float], None],
    task_config: CalibrationPipelineConfig,
) -> None:
    """
    Run posthoc calibration on collected charuco observations.

    Args:
        frame_observations: Per-frame dict of {video_id: CharucoObservation}.
        recording_info: Recording metadata.
        video_metadata: Per-video metadata.
        report_progress: Callback for (detail, fraction) progress updates.
        task_config: Calibration-specific config (pre-bound via partial).
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

    # ---- Run anipose calibration ----
    report_progress("Running anipose calibration", 0.1)
    logger.info("Starting anipose calibration...")

    calibration_toml_path = anipose_calibration_from_charuco_observations(
        charuco_observations_by_frame=charuco_observations_by_frame,
        calibration_pipeline_config=task_config,
        recording_info=recording_info,
        video_metadata=video_metadata,
    )

    logger.info(f"Anipose calibration complete — saved to {calibration_toml_path}")
    report_progress("Anipose calibration complete", 0.6)

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
