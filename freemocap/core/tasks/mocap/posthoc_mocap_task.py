"""
run_mocap_task: posthoc motion capture processing.

Receives collected mediapipe observations, builds skeleton via triangulation.

Called by PosthocAggregationNode after all frames are collected.
Pre-bind task_config via functools.partial when creating the pipeline.
"""
from __future__ import annotations

import logging
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from freemocap.core.tasks.calibration.calibration_task_config import CalibrationSource
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from skellytracker.trackers.rtmpose_tracker.rtmpose_observation import RTMPoseObservation

if TYPE_CHECKING:
    pass
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseObservation, BaseRecorder
# from skellytracker.trackers.legacy_mediapipe_tracker.legacy_mediapipe_observation import LegacyMediapipeObservation
# from skellytracker.trackers.mediapipe_tracker import MediapipeObservation

from freemocap.core.blender.export_to_blender import export_to_blender
from freemocap.core.tasks.calibration.shared.calibration_paths import get_last_successful_calibration_toml_path
from freemocap.core.tasks.mocap.mocap_helpers.skeleton_from_mediapipe_observations import \
    skeleton_from_mediapipe_observation_recorders
from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata
from freemocap.core.types.type_overloads import VideoIdString
from skellytracker.trackers.mediapipe_tracker import MediapipeObservation
logger = logging.getLogger(__name__)


def run_posthoc_mocap_aggregator_task(
        *,
        frame_observations: list[dict[VideoIdString, BaseObservation]],
        recording_info: RecordingInfo,
        video_metadata: dict[VideoIdString, VideoMetadata],
        task_config: PosthocMocapPipelineConfig,
        report_progress: Callable[[str, float], None] | None = None,

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
    if report_progress is not None:
        report_progress("Building observation recorders", 0.1)

    observation_recorders: dict[VideoIdString, BaseRecorder] = {
        vid_id: BaseRecorder() for vid_id in video_ids
    }

    for frame_idx, frame_obs in enumerate(frame_observations):
        for vid_id, obs in frame_obs.items():
            if not isinstance(obs, RTMPoseObservation) and not isinstance(obs, MediapipeObservation):
                raise TypeError(
                    f"Expected MediapipeObservation for video {vid_id} frame {frame_idx}, "
                    f"got {type(obs).__name__}"
                )
            observation_recorders[vid_id].add_observation(observation=obs)

    # ---- Get calibration path ----
    if task_config.calibration_source == CalibrationSource.SPECIFIED:
        if not task_config.calibration_toml_path:
            raise RuntimeError("calibration_source is 'specified' but calibration_toml_path is not set.")
        calibration_toml_path = Path(task_config.calibration_toml_path)
        if not calibration_toml_path.exists():
            raise RuntimeError(
                f"Specified calibration TOML not found: {calibration_toml_path}"
            )
        logger.info(f"Using user-specified calibration TOML: {calibration_toml_path}")
    else:
        calibration_toml_path = get_last_successful_calibration_toml_path()
        if not calibration_toml_path.exists():
            raise RuntimeError(
                "No calibration file found — cannot run mocap without calibration. "
                "Run a calibration pipeline first."
            )
        logger.info(f"Using most recent calibration TOML: {calibration_toml_path}")

    # ---- Copy calibration file into recording folder ----
    recording_folder = Path(recording_info.full_recording_path)
    recording_calibration_copy = recording_folder / calibration_toml_path.name
    shutil.copy2(calibration_toml_path, recording_calibration_copy)
    logger.info(f"Copied calibration file to recording folder: {recording_calibration_copy}")

    # ---- Run skeleton triangulation ----
    if report_progress is not None:
        report_progress("Triangulating skeleton", 0.3)
    logger.info("Starting skeleton triangulation...")

    output_folder = Path(recording_info.full_recording_path) / "output_data"

    skeleton = skeleton_from_mediapipe_observation_recorders(
        observation_recorders=observation_recorders,
        path_to_calibration_toml=calibration_toml_path,
        path_to_output_data_folder=output_folder,
    )



    if task_config.export_to_blender:
        try:
            export_to_blender(
                recording_folder_path=str(recording_info.full_recording_path),
                blender_exe_path=task_config.blender_exe_path,
                open_file_on_completion=task_config.auto_open_blend_file,
            )
        except Exception as e:
            # Don't crash the whole aggregator if blender export fails —
            # mocap outputs are already saved; blender is an optional post-step.
            logger.exception(f"Blender export failed (mocap data still saved): {e}")
    if report_progress is not None:
        report_progress("Mocap complete", 1.0)
    logger.info(
        f"Posthoc mocap complete! Output saved to {output_folder}"
    )
