"""
run_mocap_task: posthoc motion capture processing.

Receives collected mediapipe observations, builds skeleton via triangulation.

Called by PosthocAggregationNode after all frames are collected.
Pre-bind task_config via functools.partial when creating the pipeline.
"""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
# Load pyarrow FIRST, before the native libs pulled in by the imports below.
# pandas>=3.0 uses the pyarrow-backed string dtype by default, so writing the
# output CSV/parquet calls into pyarrow's native code. On Windows, if another
# native lib in this module's import graph loads before pyarrow, pyarrow's Arrow
# DLLs fail to initialize and the worker dies with a STATUS_ACCESS_VIOLATION
# (0xC0000005) — a hard segfault, not a catchable exception. Importing pyarrow
# up front makes it win the DLL load-order race. Do not remove or reorder.
import pyarrow  # noqa: F401

from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig  # noqa: TC001
from skellytracker.core.data_primitives.observation import Observation  # noqa: TC002
from skellycam.core.recorders.videos.recording_info import RecordingInfo  # noqa: TC002

from freemocap.core.blender.export_to_blender import export_to_blender
from freemocap.core.pipeline.posthoc.pipeline_phases import MocapStage
from freemocap.core.pipeline.posthoc.task_progress_reporter import TaskProgressReporter
from freemocap.core.tasks.calibration.shared.calibration_paths import get_last_successful_calibration_toml_path
from freemocap.core.tasks.mocap.mocap_helpers.skeleton_from_mediapipe_observations import \
    skeleton_from_mediapipe_observation_recorders
from freemocap.core.tracking.observation_buffer import ObservationBuffer
from freemocap.core.tracking.tracker_definitions import RTMPOSE_WHOLEBODY_DEFINITION
from skellycam.core.types.type_overloads import CameraIdString  # noqa: TC002

from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata  # noqa: TC001
logger = logging.getLogger(__name__)


def run_posthoc_mocap_aggregator_task(
        *,
        frame_observations: list[dict[CameraIdString, Observation]],
        recording_info: RecordingInfo,
        video_metadata: dict[CameraIdString, VideoMetadata],
        task_config: PosthocMocapPipelineConfig,
        reporter: TaskProgressReporter | None = None,
) -> None:
    """
    Run posthoc motion capture on collected skeleton observations.

    Args:
        frame_observations: Per-frame dict of {camera_id: Observation}.
        recording_info: Recording metadata.
        video_metadata: Per-camera metadata.
        reporter: Progress reporter for named stage updates.
        task_config: Mocap-specific config (pre-bound via partial).
    """
    _reporter = reporter or TaskProgressReporter.noop()
    camera_ids = list(video_metadata.keys())

    # ---- Build observation buffers ----
    _reporter.report(stage=MocapStage.BUILDING_RECORDERS, detail="Building observation buffers")

    observation_recorders: dict[CameraIdString, ObservationBuffer] = {
        cam_id: ObservationBuffer() for cam_id in camera_ids
    }

    for frame_idx, frame_obs in enumerate(frame_observations):
        for cam_id, obs in frame_obs.items():
            observation_recorders[cam_id].add_observation(obs)

    # ---- Get calibration path: explicit path wins; else fall back to most-recent ----
    if task_config.calibration_toml_path:
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
        logger.info(f"No calibration path specified; using most-recent calibration: {calibration_toml_path}")

    # ---- Copy calibration file into recording folder ----
    recording_folder = Path(recording_info.full_recording_path)
    recording_calibration_copy = recording_folder / calibration_toml_path.name
    if calibration_toml_path.resolve() != recording_calibration_copy.resolve():
        shutil.copy2(calibration_toml_path, recording_calibration_copy)
        logger.info(f"Copied calibration file to recording folder: {recording_calibration_copy}")
    else:
        logger.info(f"Calibration file already in recording folder, skipping copy: {recording_calibration_copy}")

    # ---- Run skeleton triangulation ----
    _reporter.report(stage=MocapStage.TRIANGULATING, detail="Triangulating skeleton")
    logger.info("Starting skeleton triangulation...")

    output_folder = Path(recording_info.full_recording_path) / "output_data"

    skeleton = skeleton_from_mediapipe_observation_recorders(
        detector= task_config.detector_type,
        observation_recorders=observation_recorders,
        path_to_calibration_toml=calibration_toml_path,
        path_to_output_data_folder=output_folder,
    )

    # ---- Save tracker schema alongside outputs ----
    definition = RTMPOSE_WHOLEBODY_DEFINITION

    schema_path = recording_folder / "tracker_schema.json"
    schema_path.write_text(json.dumps(definition.model_dump(), indent=2))
    logger.info(f"Saved tracker schema ({definition.name}) to {schema_path}")


    if task_config.export_to_blender:
        _reporter.report(stage=MocapStage.EXPORTING_BLENDER, detail="Exporting to Blender")
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
    logger.info(
        f"Posthoc mocap complete! Output saved to {output_folder}"
    )
