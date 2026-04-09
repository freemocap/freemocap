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

import toml

from freemocap.core.tasks.calibration.calibration_task_config import CalibrationSource
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig

if TYPE_CHECKING:
    from skellyforge.skellymodels.managers.human import Human
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseObservation, BaseRecorder
from skellytracker.trackers.legacy_mediapipe_tracker.legacy_mediapipe_observation import LegacyMediapipeObservation
from skellytracker.trackers.mediapipe_tracker import MediapipeObservation

from freemocap.core.blender.export_to_blender import export_to_blender
from freemocap.core.tasks.calibration.shared.calibration_models import CalibrationResult
from freemocap.core.tasks.calibration.shared.calibration_paths import get_last_successful_calibration_toml_path
from freemocap.core.tasks.calibration.shared.feet_groundplane import (
    estimate_groundplane_from_feet,
    build_mediapipe_body_marker_name_to_index,
)
from freemocap.core.tasks.calibration.shared.groundplane_alignment import (
    apply_groundplane_to_cameras,
    groundplane_metadata,
)
from freemocap.core.tasks.mocap.mocap_helpers.skeleton_from_mediapipe_observations import \
    skeleton_from_mediapipe_observation_recorders
from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata
from freemocap.core.types.type_overloads import VideoIdString
from freemocap.utilities.toml_mixin import numpy_to_python

logger = logging.getLogger(__name__)


def run_posthoc_mocap_aggregator_task(
        *,
        frame_observations: list[dict[VideoIdString, BaseObservation]],
        recording_info: RecordingInfo,
        video_metadata: dict[VideoIdString, VideoMetadata],
        task_config: PosthocMocapPipelineConfig,
        create_blender_output: bool=True, #TODO - Add this to the mocap config, after we split the RT and PH pipeline
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
            if not isinstance(obs, MediapipeObservation) and not isinstance(obs, LegacyMediapipeObservation):
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
        if calibration_toml_path is None:
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

    # ---- Feet-based ground plane → camera calibration update ----
    _maybe_apply_feet_groundplane(
        skeleton=skeleton,
        calibration_toml_path=recording_calibration_copy,
        recording_id=recording_info.recording_name,
        task_config=task_config,
    )

    if create_blender_output:

        export_to_blender(
            recording_folder_path=str(recording_info.full_recording_path),
        )
    if report_progress is not None:
        report_progress("Mocap complete", 1.0)
    logger.info(
        f"Posthoc mocap complete! Output saved to {output_folder}"
    )


def _maybe_apply_feet_groundplane(
    *,
    skeleton: "Human",
    calibration_toml_path: Path,
    recording_id: str,
    task_config: PosthocMocapPipelineConfig,
) -> None:
    """Apply feet-based ground plane to camera calibration if appropriate.

    Skips if:
    - update_camera_positions_from_feet is False in config
    - Ground plane was already applied during calibration (unless force_reestimate)
    """


    # Check if groundplane was already applied during calibration
    if not task_config.force_reestimate_groundplane:
        try:
            toml_data = toml.loads(calibration_toml_path.read_text())
            metadata = toml_data.get("metadata", {})
            if metadata.get("groundplane_applied", False):
                logger.info(
                    f"Groundplane already applied (method: {metadata.get('groundplane_method', 'unknown')}), "
                    f"skipping feet-based estimation"
                )
                return
        except Exception as e:
            logger.warning(f"Could not read calibration TOML metadata: {e}")

    # Get body 3D data from skeleton
    try:
        body_3d = skeleton.body.xyz.as_array  # (n_frames, n_body_markers, 3)
    except Exception as e:
        logger.warning(f"Could not access body 3D data for feet ground plane: {e}")
        return

    marker_name_to_index = build_mediapipe_body_marker_name_to_index()

    ground_plane = estimate_groundplane_from_feet(
        skeleton_3d=body_3d,
        marker_name_to_index=marker_name_to_index,
    )

    if ground_plane is None:
        logger.warning("Feet ground plane estimation returned None — skipping camera update")
        return

    # Load calibration, apply ground plane, re-save
    try:
        calibration = CalibrationResult.load_anipose_toml(calibration_toml_path)
        updated_cameras = apply_groundplane_to_cameras(calibration.cameras, ground_plane)

        # Read existing TOML to preserve metadata, then update
        toml_data = toml.loads(calibration_toml_path.read_text())
        existing_metadata = toml_data.get("metadata", {})

        # Merge groundplane metadata
        gp_meta = groundplane_metadata(ground_plane, recording_id)
        existing_metadata.update(gp_meta)

        # Re-save with updated cameras and metadata
        updated_result = CalibrationResult(
            cameras=updated_cameras,
            board=calibration.board,
            reprojection_error_px=calibration.reprojection_error_px,
            initial_cost=calibration.initial_cost,
            final_cost=calibration.final_cost,
            n_iterations=calibration.n_iterations,
            time_seconds=calibration.time_seconds,
            n_observations_used=calibration.n_observations_used,
            n_observations_rejected=calibration.n_observations_rejected,
        )
        updated_result.dump_anipose_toml(
            path=calibration_toml_path,
            metadata=numpy_to_python(existing_metadata),
        )
        logger.info(
            f"Updated calibration TOML with feet-based ground plane "
            f"(recording: {recording_id})"
        )
    except Exception as e:
        logger.warning(f"Failed to apply feet ground plane to calibration: {e}", exc_info=True)
