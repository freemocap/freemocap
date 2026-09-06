"""
run_mocap_task: posthoc motion capture processing.

Receives collected mediapipe observations, builds skeleton via triangulation.

Called by PosthocAggregationNode after all frames are collected.
Pre-bind task_config via functools.partial when creating the pipeline.
"""
from __future__ import annotations

from freemocap.core.recording.result_processing.observation_inputs import ObservationRecordingRequest, ObservationGroup, TrackerRecordingDefinition
from freemocap.core.recording.data_descriptors.recording_model import RecordedModel
from freemocap.core.tasks.calibration.shared.calibration_result import CalibrationResult
from freemocap.core.tasks.calibration.shared.camera_model import CameraModel
from freemocap.core.recording.sample_encoding.spatial_points import SpatialPointSeries, PointSeriesDefinition, SpatialReference
import logging
import shutil
from pathlib import Path

from freemocap.core.reconstruction.recording_reconstruction import RecordingReconstructionInput
from freemocap.core.recording.sample_encoding.reconstruction_samples import ReconstructionRecording, ReconstructionSourceDefinition

from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig  # noqa: TC001
from skellytracker.core.data_primitives.observation import Observation  # noqa: TC002
from skellycam.core.recorders.videos.recording_info import RecordingInfo  # noqa: TC002

from freemocap.core.pipeline.posthoc.pipeline_phases import MocapStage
from freemocap.core.pipeline.posthoc.task_progress_reporter import TaskProgressReporter
from freemocap.core.reconstruction.posthoc_reconstruction import (
    reconstruct_skeletons_for_recording,
    triangulate_observation_buffers,
)
from freemocap.core.reconstruction.posthoc_timing import PosthocTimingReport
from freemocap.core.skeletons.standard_human_skeleton import (
    build_standard_human_bundle,
)
from freemocap.core.tasks.calibration.shared.calibration_paths import find_recording_calibration, get_last_successful_calibration_toml_path
from freemocap.core.tracking.observation_buffer import ObservationBuffer
from freemocap.core.recording.result_processing.observation_publication import publish_posthoc_observations
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
        calibration_toml_path = find_recording_calibration(recording_folder=recording_folder)
        if calibration_toml_path is None:
            calibration_toml_path = get_last_successful_calibration_toml_path()
        if not calibration_toml_path.exists():
            raise RuntimeError(
                "Multicamera triangulation requires calibration geometry. "
                "Select a calibration TOML or run the separate calibration task first."
            )
        logger.info(f"Using resolved calibration: {calibration_toml_path}")

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


    timing = PosthocTimingReport()

    calibration = CalibrationResult.load_anipose_toml(calibration_toml_path) if calibration_toml_path is not None else None
    keypoints_blender, keypoint_names, _per_camera_weights = triangulate_observation_buffers(
        observation_buffers=observation_recorders,
        calibration=calibration,
        triangulation_config=task_config.triangulation_config,
        max_reprojection_error_px=None,
        timing=timing,
    )

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
        camera_geometry=tuple(calibration.get_camera(camera) for camera in camera_ids) if calibration is not None else (),
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
    logger.info("Posthoc mocap complete: canonical Parquet published")
