"""
run_mocap_task: posthoc motion capture processing.

Extracted from the old PosthocMocapAggregationNode._run().
Receives collected mediapipe observations, builds skeleton via triangulation.

Called by PosthocAggregationNode after all frames are collected.
Pre-bind task_config via functools.partial when creating the pipeline.
"""
import logging
from collections.abc import Callable
from pathlib import Path

from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseObservation, BaseRecorder
from skellytracker.trackers.mediapipe_tracker.mediapipe_observation import MediapipeObservation

from freemocap.core.pipeline.shared.pipeline_configs import MocapPipelineConfig
from freemocap.core.pipeline.posthoc.posthoc_tasks.calibration_task import \
    get_last_successful_calibration_toml_path
from freemocap.core.pipeline.posthoc.posthoc_tasks.mocap_task.mocap_helpers.skeleton_from_mediapipe_observations import \
    skeleton_from_mediapipe_observation_recorders
from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata

from freemocap.core.types.type_overloads import VideoIdString

logger = logging.getLogger(__name__)


def run_mocap_task(
    *,
    frame_observations: list[dict[VideoIdString, BaseObservation]],
    recording_info: RecordingInfo,
    video_metadata: dict[VideoIdString, VideoMetadata],
    report_progress: Callable[[str, float], None],
    task_config: MocapPipelineConfig,
) -> None:
    """
    Run posthoc motion capture on collected mediapipe observations.

    Args:
        frame_observations: Per-frame dict of {video_id: MediapipeObservation}.
        recording_info: Recording metadata.
        video_metadata: Per-video metadata.
        report_progress: Callback for (detail, fraction) progress updates.
        task_config: Mocap-specific config (pre-bound via partial).
    """
    video_ids = list(video_metadata.keys())

    # ---- Build observation recorders ----
    report_progress("Building observation recorders", 0.1)

    observation_recorders: dict[VideoIdString, BaseRecorder] = {
        vid_id: BaseRecorder() for vid_id in video_ids
    }

    for frame_idx, frame_obs in enumerate(frame_observations):
        for vid_id, obs in frame_obs.items():
            if not isinstance(obs, MediapipeObservation):
                raise TypeError(
                    f"Expected MediapipeObservation for video {vid_id} frame {frame_idx}, "
                    f"got {type(obs).__name__}"
                )
            observation_recorders[vid_id].add_observation(observation=obs)

    # ---- Get calibration path ----
    calibration_toml_path = get_last_successful_calibration_toml_path()
    if calibration_toml_path is None:
        raise RuntimeError(
            "No calibration file found — cannot run mocap without calibration. "
            "Run a calibration pipeline first."
        )

    # ---- Run skeleton triangulation ----
    report_progress("Triangulating skeleton", 0.3)
    logger.info("Starting skeleton triangulation...")

    output_folder = Path(recording_info.full_recording_path) / "output_data"

    skeleton_from_mediapipe_observation_recorders(
        observation_recorders=observation_recorders,
        path_to_calibration_toml=calibration_toml_path,
        path_to_output_data_folder=output_folder,
    )

    report_progress("Mocap complete", 1.0)
    logger.info(
        f"Posthoc mocap complete! Output saved to {output_folder}"
    )
