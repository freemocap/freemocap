"""Triangulate recording observations and reconstruct the selected tracked models."""
from __future__ import annotations
import json
from freemocap.core.pipeline.performance_report import PerformanceReport
import time
from freemocap.utilities.numerical_statistics import DISTRIBUTION_COLUMNS, distribution_row
from collections.abc import Callable  # noqa: TC003 - runtime type checking
from concurrent.futures import CancelledError
from dataclasses import replace

from freemocap.core.recording.result_processing.observation_inputs import (
    DetectorRecordingDefinition,
    ObservationGroup,
    ObservationRecordingRequest,
    TrackerRecordingDefinition,
    camera_group_name,
)
from skellytracker.core.detectors.object_detectors.yolox import YoloxPersonDetectorConfig
from freemocap.core.recording.data_descriptors.recording_model import RecordedModel
from freemocap.core.tasks.calibration.shared.calibration_result import CalibrationResult
from freemocap.core.tasks.calibration.shared.calibration_update import (
    CalibrationFileChangedError, CalibrationUpdateRequest,
)
from freemocap.core.tasks.calibration.shared.camera_model import CameraModel  # noqa: TC001 - runtime type checking
from freemocap.core.tasks.calibration.camera_matching.posthoc_matching import PosthocMatchingRequest
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition  # noqa: TC002 - runtime type checking
from freemocap.core.skeletons.charuco_board_skeleton import build_charuco_board_bundle
from freemocap.core.recording.sample_encoding.spatial_points import SpatialPointSeries, PointSeriesDefinition, SpatialReference
import logging
import numpy as np
from skellyforge.core.biomechanics.alignment_definition import AlignmentDefinition
from freemocap.core.reconstruction.mocap_alignment import MocapAlignmentRequest, align_mocap_recording
from freemocap.core.reconstruction.recording_timing import RecordingGroupTiming
from freemocap.core.reconstruction.posthoc_filtering import prepare_recording_points
from freemocap.core.types.channel_kind import ChannelKind
from freemocap.core.recording.sample_encoding.spatial_points import ReferenceAlignmentDescriptor
import shutil
from pathlib import Path
from freemocap.core.tasks.triangulation.helpers.reprojection_diagnostics import NamedReprojectionDiagnostics

from freemocap.core.reconstruction.recording_reconstruction import RecordingReconstructionInput
from freemocap.core.recording.sample_encoding.reconstruction_samples import ReconstructionRecording, ReconstructionSourceDefinition

from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig  # noqa: TC001
from freemocap.core.tracking.tracker_definitions import MEDIAPIPE_WHOLEBODY_DEFINITION
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
from freemocap.core.tracking.observation_buffer import ObservationBuffer
from freemocap.core.recording.result_processing.observation_publication import publish_posthoc_observations
from freemocap.core.recording.result_processing.provenance import ProvenanceContext
from skellycam.core.types.type_overloads import CameraIdString  # noqa: TC002

from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata  # noqa: TC001
logger = logging.getLogger(__name__)


def _keypoint_model_name(task_config: PosthocMocapPipelineConfig) -> str:
    """What to call the model that measured the keypoints, in the recording.

    RTMPose reports its weights variant, because which weights ran is what a reader
    needs to reproduce the numbers. MediaPipe has no single weights name — it is three
    detectors in one stage — so it reports the composite tracker definition instead.
    Either way the full configuration rides in the Source definition blob.
    """
    if task_config.detector_type == "rtmpose":
        return task_config.rtmpose_model_name
    return MEDIAPIPE_WHOLEBODY_DEFINITION.name


def run_posthoc_mocap_task(
        *,
        frame_observations: list[dict[CameraIdString, Observation]],
        recording_info: RecordingInfo,
        video_metadata: dict[CameraIdString, VideoMetadata],
        task_config: PosthocMocapPipelineConfig,
        selected_board: CharucoBoardDefinition | None,
        reporter: TaskProgressReporter | None = None,
        cancelled: Callable[[], bool] | None = None,
        saved_timing: RecordingGroupTiming | None = None,
        performance: PerformanceReport | None = None,
) -> None:
    """
    Reconstruct the selected models from collected recording observations.

    Args:
        frame_observations: Per-frame dict of {camera_id: Observation}.
        recording_info: Recording metadata.
        video_metadata: Per-camera metadata.
        reporter: Progress reporter for named stage updates.
        task_config: Resolved Mocap detector configuration.
    """
    performance = performance if performance is not None else PerformanceReport()
    _reporter = reporter or TaskProgressReporter.noop()
    camera_ids = list(video_metadata.keys())

    def check_cancelled():
        if cancelled is not None and cancelled():
            raise CancelledError('Mocap processing cancelled; completed stages remain on disk')

    check_cancelled()
    bundles = (build_standard_human_bundle(detector_type=task_config.detector_type),)
    if selected_board is not None:
        bundles += (build_charuco_board_bundle(board=selected_board),)
    group_name = (task_config.sensor_group if saved_timing is not None else None) or camera_group_name(camera_ids)
    keypoint_source = f"keypoint_model:{_keypoint_model_name(task_config)}"
    detector_source = (f"object_detector:{YoloxPersonDetectorConfig().model_name}"
        if task_config.detector_type == 'rtmpose' else None)
    observation_checkpoint = ObservationRecordingRequest(
        reprojection=None, filtering=None, reconstructions=(), spatial_series=(), camera_geometry=(),
        models=tuple(RecordedModel.from_bundle(bundle) for bundle in bundles), recording=recording_info,
        group=ObservationGroup(name=group_name, frames=frame_observations, videos=video_metadata),
        tracker=TrackerRecordingDefinition(name=keypoint_source, configuration=task_config.model_dump(mode='json'),
            point_names=tuple(dict.fromkeys(name for frame in frame_observations for obs in frame.values()
                for name in obs.to_keypoints().names))),
        detector=DetectorRecordingDefinition(name=detector_source, configuration=task_config.model_dump(mode='json'),
            box_names=tuple(dict.fromkeys(stage.name for frame in frame_observations for obs in frame.values()
                for stage in obs.stages.values()))) if detector_source else None,
        base_run_id=task_config.base_run_id, reuse_observations=saved_timing is not None,
        resolved_timing=saved_timing,
        provenance_context=ProvenanceContext.create(),
        provenance_defaults=PosthocMocapPipelineConfig().model_dump(mode='json'),
    )
    if saved_timing is None:
        _reporter.report(stage=MocapStage.BUILDING_RECORDERS, detail='Saving completed 2D tracking')
        with performance.measure("checkpoint.observations"):
            publish_posthoc_observations(observation_checkpoint)
    check_cancelled()

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
        raise ValueError(
            "Multicamera triangulation requires an explicitly selected calibration TOML. "
            "Select a calibration or run the separate calibration task first."
        )

    # ---- Copy calibration file into recording folder ----
    if calibration_toml_path is not None:
        recording_calibration_copy = recording_folder / calibration_toml_path.name
        if calibration_toml_path.resolve() != recording_calibration_copy.resolve():
            shutil.copy2(calibration_toml_path, recording_calibration_copy)
            logger.info(f"Copied calibration file to recording folder: {recording_calibration_copy}")
        else:
            logger.info(f"Calibration file already in recording folder, skipping copy: {recording_calibration_copy}")

    # ---- Triangulate + reconstruct on the shared realtime core ----
    _reporter.report(stage=MocapStage.TRIANGULATING, detail="Triangulating observations")
    logger.info("Starting observation triangulation...")


    timing = PosthocTimingReport()

    calibration_mtime_ms = (
        calibration_toml_path.stat().st_mtime_ns / 1_000_000
        if calibration_toml_path is not None else None
    )
    calibration = CalibrationResult.load_toml(calibration_toml_path) if calibration_toml_path is not None else None
    if calibration_toml_path is not None and (
        calibration_toml_path.stat().st_mtime_ns / 1_000_000 != calibration_mtime_ms
    ):
        raise CalibrationFileChangedError("Calibration changed while loading; retry processing.")
    camera_geometry: dict[str, CameraModel] = {}
    if calibration is not None:
        matching_request = PosthocMatchingRequest(
            frames=frame_observations, videos=video_metadata,
            cameras=tuple(calibration.cameras), config=task_config.camera_matching,
        )
        matching_result = matching_request.evaluate()
        camera_geometry = matching_request.resolve(result=matching_result)
        _reporter.report(stage=MocapStage.TRIANGULATING, detail=f"Camera matching: {matching_result.status}")
        logger.info("Camera matching: %s; source assignments: %s; fitness: %s",
                    matching_result.status, {source: camera.id for source, camera in camera_geometry.items()}, matching_result.fitness)
    triangulation_started = time.perf_counter()
    triangulation = triangulate_observation_buffers(
        observation_buffers=observation_recorders,
        camera_geometry=camera_geometry,
        triangulation_config=task_config.triangulation_config,
        max_reprojection_error_px=None,
        timing=timing,
    )
    triangulation_seconds = time.perf_counter() - triangulation_started
    performance.record("triangulation.total", triangulation_seconds)
    diagnostics = triangulation.reconstruction.diagnostics
    if diagnostics is not None:
        count_rows, error_rows, legend = [], [], []
        for index, (source, summary) in enumerate(zip(triangulation.sources, diagnostics.summaries(), strict=True)):
            camera = f'C{index + 1}'
            legend.append(f'{camera} = {source}')
            count_rows.append([camera, summary.observed_count, summary.reconstructed_count,
                               summary.contributing_count])
            # Include missing reconstructions in the missing-error percentage.
            errors = np.where(diagnostics.reconstructed[index], diagnostics.errors[index], np.nan)
            error_rows.append([camera, *distribution_row(errors[diagnostics.observed[index]])])
        logger.info('Processing statistics: %s', json.dumps(dict(stage='Triangulation | point samples',
            columns=['Camera', 'Observed', 'Reprojected', 'Contributing'], rows=count_rows,
            caption=f'Wall time {triangulation_seconds:.3f} s | output shape {triangulation.reconstruction.points_3d.shape}\n'
                    + '\n'.join(legend))))
        logger.info('Processing statistics: %s', json.dumps(dict(
            stage=f'Triangulation | reprojection error ({diagnostics.units})',
            columns=['Camera', *DISTRIBUTION_COLUMNS], rows=error_rows,
            caption='Percentages use all observed 2D point samples; missing 3D reconstructions count as NaN.\n'
                    'Error statistics use finite residuals before downstream filtering. P05–P95 is not a confidence interval.')))

    group_timing = saved_timing or RecordingGroupTiming.resolve(
        recording_folder=recording_folder, videos=video_metadata,
        frame_numbers=tuple(frame[camera_ids[0]].frame_number for frame in frame_observations),
    )
    _reporter.report(stage=MocapStage.FILTERING, detail="Filling trajectory gaps, then filtering")
    filtered = prepare_recording_points(
        points=triangulation.reconstruction.points_3d,
        timestamps_s=np.asarray(group_timing.synchronized.timestamps_s, dtype=np.float64),
        config=task_config.filter_config,
    )
    preserve_reference_frame = task_config.body_alignment.preserve_reference_frame(
        calibration_aligned=calibration.aligned if calibration is not None else False,
    )
    _reporter.report(stage=MocapStage.FILTERING, detail=(
        "Preserving calibration coordinate frame" if preserve_reference_frame
        else "Estimating alignment from person and foot support"
    ))
    aligned = align_mocap_recording(request=MocapAlignmentRequest(
        filtered_points=filtered.points,
        measured_support=filtered.report.gap_filling.measured_support(filtered.points),
        triangulation=triangulation, camera_geometry=camera_geometry, bundle=bundles[0],
        definition=AlignmentDefinition.from_default_human(skeleton=bundles[0].skeleton),
        timestamps_seconds=np.asarray(group_timing.synchronized.timestamps_s, dtype=np.float64),
        preserve_reference_frame=preserve_reference_frame,
        config=task_config.body_alignment,
    ))
    triangulation = aligned.triangulation
    camera_geometry = aligned.camera_geometry
    logger.info("Mocap reference alignment: %s", aligned.alignment.outcome)
    spatial_reference = SpatialReference.for_camera_count(len(camera_ids))
    if len(camera_ids) > 1:
        spatial_reference = spatial_reference.model_copy(update={
            "alignment": ReferenceAlignmentDescriptor.from_result(result=aligned.alignment),
            "additional_transform": task_config.body_alignment.additional_transform,
        })
    # Publish the aligned 3D streams before the more expensive reconstruction.
    check_cancelled()
    spatial_checkpoint = replace(observation_checkpoint,
        reuse_observations=True, resolved_timing=group_timing,
        camera_geometry=tuple(camera_geometry[source] for source in camera_ids) if camera_geometry else (),
        filtering=filtered.report,
        reprojection=NamedReprojectionDiagnostics(source_ids=triangulation.sources,
            point_names=triangulation.diagnostic_point_names, values=triangulation.reconstruction.diagnostics)
            if triangulation.reconstruction.diagnostics is not None else None,
        spatial_series=tuple(SpatialPointSeries(definition=PointSeriesDefinition(kind=kind,
            sensor_group=group_name, source=keypoint_source, names=triangulation.keypoint_names,
            reference=spatial_reference), values=values) for kind, values in (
                (ChannelKind.RAW_KEYPOINTS_3D, triangulation.reconstruction.points_3d),
                (ChannelKind.KEYPOINTS_3D, aligned.filtered_points))),
    )
    with performance.measure("checkpoint.spatial"):
        publish_posthoc_observations(spatial_checkpoint)
    check_cancelled()
    _reporter.report(stage=MocapStage.RECONSTRUCTING, detail=(
        f"Reconstructing skeletons; filtered {filtered.report.filtered_runs} trajectory runs, "
        f"preserved {filtered.report.preserved_short_runs} short runs"
    ))
    with performance.measure("reconstruction.total"):
        reconstructions = reconstruct_skeletons_for_recording(RecordingReconstructionInput(
            bundles=bundles,
            keypoint_names=triangulation.keypoint_names,
            keypoints_3d=aligned.filtered_points,
            measured_support=filtered.report.gap_filling.measured_support(aligned.filtered_points),
            compute_center_of_mass=True,
            timing=timing,
        ))


    publication = replace(spatial_checkpoint,
        calibration_update=CalibrationUpdateRequest(
            path=calibration_toml_path.resolve(),
            expected_mtime_ms=calibration_mtime_ms,
            transformations=aligned.transformations,
            recording_id=recording_info.recording_name,
        ) if calibration_toml_path is not None
            and calibration_mtime_ms is not None
            and aligned.transformations else None,
        reconstructions=tuple(ReconstructionRecording(
            sensor_group=group_name, reference=spatial_reference,
            definition=ReconstructionSourceDefinition.from_bundle(bundle, tracker_source=keypoint_source,
                point_kind=ChannelKind.KEYPOINTS_3D),
            result=reconstructions[bundle.model_id],
        ) for bundle in bundles),
    )
    check_cancelled()
    with performance.measure("checkpoint.final"):
        published = publish_posthoc_observations(publication)
    if task_config.skeleton_fit_enabled:
        from freemocap.core.recording.result_processing.skeleton_fitting import fit_saved_skeleton
        from freemocap.system.recording_structure.recording_structure import RecordingStructure

        _reporter.report(stage=MocapStage.FITTING_SKELETON, detail="Fitting connected human skeleton")

        def fit_progress(window, total):
            _reporter.report(stage=MocapStage.FITTING_SKELETON,
                detail=f"Skeleton fit window {window['index'] + 1}/{total}; converged={window['converged']}",
                fraction=(window['index'] + 1) / total)

        fit_saved_skeleton(
            structure=RecordingStructure(base_directory=recording_folder.parent, recording_name=recording_folder.name),
            run_id=published.selected_run_id, sensor_group=group_name,
            progress=fit_progress, cancelled=cancelled,
        )
    logger.info("Posthoc mocap complete: recording data saved to disk as Parquet")
