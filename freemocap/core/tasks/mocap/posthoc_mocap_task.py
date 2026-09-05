"""
run_mocap_task: posthoc motion capture processing.

Receives collected mediapipe observations, builds skeleton via triangulation.

Called by PosthocAggregationNode after all frames are collected.
Pre-bind task_config via functools.partial when creating the pipeline.
"""
from __future__ import annotations

from freemocap.core.recording.observation_recording_models import ObservationRecordingRequest, ObservationGroup, TrackerRecordingDefinition
import csv
from freemocap.core.recording.recorded_model import RecordedModel
from freemocap.core.tasks.calibration.shared.calibration_result import CalibrationResult
from freemocap.core.recording.resolved_camera_geometry import ResolvedCameraGeometry
from freemocap.core.recording.spatial_point_series import SpatialPointSeries, PointSeriesDefinition, SpatialReference
import json
import logging
import shutil
import time
from pathlib import Path

from freemocap.core.reconstruction.recording_reconstruction import RecordingReconstructionInput
from freemocap.core.recording.reconstruction_recording import ReconstructionRecording, ReconstructionSourceDefinition
import numpy as np
from numpy.typing import NDArray  # noqa: TC002 - runtime type checking
from freemocap.core.skeletons.tracked_skeleton_bundle import TrackedSkeletonBundle  # noqa: TC001 - runtime type checking
from freemocap.core.skeletons.skeleton_reconstruction import SkeletonReconstruction  # noqa: TC001 - runtime type checking

from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig  # noqa: TC001
from skellytracker.core.data_primitives.observation import Observation  # noqa: TC002
from skellycam.core.recorders.videos.recording_info import RecordingInfo  # noqa: TC002

from freemocap.core.blender.export_to_blender import export_to_blender
from freemocap.core.pipeline.posthoc.pipeline_phases import MocapStage
from freemocap.core.pipeline.posthoc.task_progress_reporter import TaskProgressReporter
from freemocap.core.reconstruction.posthoc_reconstruction import (
    reconstruct_skeletons_for_recording,
    triangulate_observation_buffers,
)
from freemocap.core.reconstruction.posthoc_timing import PosthocTimingReport
from freemocap.core.skeletons.standard_human_skeleton import (
    STANDARD_HUMAN_MODEL_ID,
    build_standard_human_bundle,
)
from freemocap.core.tasks.calibration.shared.calibration_paths import get_last_successful_calibration_toml_path
from freemocap.core.tracking.observation_buffer import ObservationBuffer
from freemocap.core.tracking.tracker_definitions import RTMPOSE_WHOLEBODY_DEFINITION
from freemocap.core.recording.posthoc_observation_recording import publish_posthoc_observations
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

    # ---- Get calibration path: not needed for single-camera (planar projection fallback) ----
    recording_folder = Path(recording_info.full_recording_path)
    calibration_toml_path: Path | None = None
    if len(camera_ids) == 1:
        logger.info("Single camera recording; skipping calibration requirement (using planar projection fallback).")
    elif task_config.calibration_toml_path:
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
    if calibration_toml_path is not None:
        recording_calibration_copy = recording_folder / calibration_toml_path.name
        if calibration_toml_path.resolve() != recording_calibration_copy.resolve():
            shutil.copy2(calibration_toml_path, recording_calibration_copy)
            logger.info(f"Copied calibration file to recording folder: {recording_calibration_copy}")
        else:
            logger.info(f"Calibration file already in recording folder, skipping copy: {recording_calibration_copy}")

    # ---- Triangulate + reconstruct on the shared realtime core ----
    _reporter.report(stage=MocapStage.TRIANGULATING, detail="Triangulating skeleton")
    logger.info("Starting skeleton triangulation...")

    output_folder = Path(recording_info.full_recording_path) / "output_data"
    output_folder.mkdir(parents=True, exist_ok=True)

    timing = PosthocTimingReport()

    calibration = CalibrationResult.load_anipose_toml(calibration_toml_path) if calibration_toml_path is not None else None
    keypoints_blender, keypoint_names, per_camera_weights = triangulate_observation_buffers(
        observation_buffers=observation_recorders,
        calibration=calibration,
        triangulation_config=task_config.triangulation_config,
        max_reprojection_error_px=None,
        timing=timing,
    )
    frame_count = keypoints_blender.shape[0]

    bundle = build_standard_human_bundle(detector_type=task_config.detector_type)
    reconstructions = reconstruct_skeletons_for_recording(RecordingReconstructionInput(
        bundles=(bundle,),
        keypoint_names=keypoint_names,
        keypoints_3d=keypoints_blender,
        compute_center_of_mass=True,
        timing=timing,
    ))

    publication = ObservationRecordingRequest(
        models=(RecordedModel.from_bundle(bundle),),
        reconstructions=(ReconstructionRecording(
            sensor_group="mocap", reference=SpatialReference.for_camera_count(len(camera_ids)),
            definition=ReconstructionSourceDefinition.from_bundle(bundle),
            result=reconstructions[bundle.model_id],
        ),),
        camera_geometry=tuple(ResolvedCameraGeometry.from_camera(calibration.get_camera(camera)) for camera in camera_ids) if calibration is not None else (),
        recording=recording_info,
        spatial_series=(SpatialPointSeries(
            definition=PointSeriesDefinition(sensor_group="mocap", source=task_config.detector_type,
                names=keypoint_names, reference=SpatialReference.for_camera_count(len(camera_ids))),
            values=keypoints_blender,
        ),),
        group=ObservationGroup(name="mocap", frames=frame_observations, videos=video_metadata),
        tracker=TrackerRecordingDefinition(
            name=task_config.detector_type,
            configuration=task_config.model_dump(mode="json"),
            point_names=tuple(dict.fromkeys(
                name for frame in frame_observations for observation in frame.values()
                for name in observation.to_keypoints().names
            )),
        ),
    )
    publish_posthoc_observations(publication)
    t0 = time.perf_counter()
    _write_provisional_human_outputs(
        output_folder=output_folder,
        detector_type=task_config.detector_type,
        bundle=bundle,
        reconstructions=reconstructions[STANDARD_HUMAN_MODEL_ID].frames,
        frame_count=frame_count,
        per_camera_weights=per_camera_weights,
    )
    timing.record("write_outputs", time.perf_counter() - t0)
    logger.info("\n" + timing.summary_table())

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
                detector = task_config.detector_type
            )
        except Exception as e:
            # Don't crash the whole aggregator if blender export fails —
            # mocap outputs are already saved; blender is an optional post-step.
            logger.exception(f"Blender export failed (mocap data still saved): {e}")
    logger.info(
        f"Posthoc mocap complete! Output saved to {output_folder}"
    )


def _write_provisional_human_outputs(
    *,
    output_folder: Path,
    detector_type: str,
    bundle: TrackedSkeletonBundle,
    reconstructions: tuple[SkeletonReconstruction | None, ...],
    frame_count: int,
    per_camera_weights: NDArray[np.float64] | None,
) -> None:
    """Provisional on-disk outputs (schema deferred — Phase 4/schema session replaces these).

    Writes the two body files `recording_status.BLENDER_INPUT_FILES_BY_DETECTOR` can already
    recognise — body landmarks and total centre of mass — plus per-camera triangulation
    weights. Face/hands/segment-CoM stay deferred with the schema.
    """
    landmark_names = tuple(bundle.skeleton.landmarks)
    body = np.full((frame_count, len(landmark_names), 3), np.nan)
    center_of_mass = np.full((frame_count, 1, 3), np.nan)

    for t, reconstruction in enumerate(reconstructions):
        if reconstruction is None:
            continue
        for i, name in enumerate(landmark_names):
            position = reconstruction.landmarks.get(name)
            if position is not None:
                body[t, i] = position
        if reconstruction.center_of_mass is not None:
            center_of_mass[t, 0] = reconstruction.center_of_mass

    np.save(output_folder / f"{detector_type}_body_3d_xyz.npy", body)
    np.save(output_folder / f"{detector_type}_body_total_body_center_of_mass.npy", center_of_mass)
    if per_camera_weights is not None:
        np.save(output_folder / "per_camera_weights.npy", per_camera_weights)

    with open(output_folder / f"{detector_type}_body_3d_xyz.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["frame", "keypoint", "x", "y", "z"])
        for t in range(frame_count):
            for i, name in enumerate(landmark_names):
                writer.writerow([t, name, body[t, i][0], body[t, i][1], body[t, i][2]])
    logger.info(f"Provisional outputs written to {output_folder} (schema deferred)")

