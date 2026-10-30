"""Batch triangulation and two-pass skeleton reconstruction with a frozen recording fit."""

import logging
import time
from dataclasses import dataclass, replace
from freemocap.core.reconstruction.coordinate_conventions import CALIBRATION_TO_RECONSTRUCTION
from freemocap.core.reconstruction.recording_fit import FittedRecordingScale

import numpy as np
from skellyforge.core.math.geometry.spatial_vectors import Point

from freemocap.core.reconstruction.posthoc_timing import PosthocTimingReport
from freemocap.core.reconstruction.recording_pose_outputs import RecordingPoseOutputs
from freemocap.core.skeletons.reconstruction_state import (
    FrozenModelScale,
    build_reconstruction_states,
)
from freemocap.core.reconstruction.recording_reconstruction import (
    RecordingReconstructionInput,
    ModelRecordingReconstruction,
)
from freemocap.core.tasks.calibration.shared.camera_model import CameraModel
from freemocap.core.tasks.calibration.shared.calibration_state import (
    _strip_stage_prefix,
)
from freemocap.core.tasks.triangulation.helpers.project_single_camera import (
    project_2d_batch_to_3d,
)
from freemocap.core.tasks.triangulation.helpers.triangulation_config import (
    TriangulationConfig,
)
from freemocap.core.tasks.triangulation.triangulator import Triangulator
from freemocap.core.tasks.triangulation.helpers.triangulation_result import TriangulationResult
from freemocap.core.tracking.observation_buffer import ObservationBuffer
from skellycam.core.types.type_overloads import CameraIdString

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RecordingTriangulation:
    """Named recording axes and complete solver output, with positions in Blender axes.

    Per-camera weights are solver contributions, not detector confidence. Single-camera
    projection has synthetic zero reprojection errors and must not supply ground evidence.
    """

    sources: tuple[CameraIdString, ...]
    keypoint_names: tuple[str, ...]
    reconstruction: TriangulationResult
    diagnostic_point_names: tuple[str, ...]


def triangulate_observation_buffers(
    *,
    observation_buffers: dict[CameraIdString, ObservationBuffer],
    camera_geometry: dict[str, CameraModel],
    triangulation_config: TriangulationConfig | None,
    max_reprojection_error_px: float | None,
    timing: PosthocTimingReport,
    stage_name: str | None = None,
    n_points: int | None = None,
    point_names: tuple[str, ...] | None = None,
) -> RecordingTriangulation:
    """Triangulate the whole recording 2D -> 3D in ONE batched call, Blender-converted.

    Retains source/name axes, solver weights and reprojection errors. Points whose mean reprojection error exceeds
    `max_reprojection_error_px` are set to NaN.

    By default the declared whole-keypoint tensor axis is used. Pass
    `stage_name` (and optionally `n_points`) to triangulate one detector stage — the
    board path uses `stage_name="charuco"` clamped to `board.n_corners`.
    `point_names` declares a stable whole-keypoint axis for incremental calls.
    """
    if point_names is not None and (stage_name is not None or not point_names or len(set(point_names)) != len(point_names)):
        raise ValueError("Explicit point names require a unique nonempty whole-keypoint axis")
    if not observation_buffers:
        raise ValueError("No observation buffers provided to triangulate.")

    if triangulation_config is None:
        triangulation_config = TriangulationConfig()

    first_buffer = next(iter(observation_buffers.values()))
    frame_numbers = first_buffer.frame_numbers
    if not frame_numbers:
        raise ValueError("Cannot triangulate an empty recording")
    for buffer in observation_buffers.values():
        if buffer.frame_numbers != frame_numbers:
            raise ValueError("Camera observation frame numbers must match exactly")
    if stage_name is not None:
        stage_names = first_buffer.stage_point_names(stage_name)
        prefixed_names = stage_names[:n_points] if n_points is not None else stage_names
        data2d_by_camera: dict[CameraIdString, np.ndarray] = {
            camera_id: buffer.to_stage_array(stage_name, n_points)[..., :2]
            for camera_id, buffer in observation_buffers.items()
        }
    else:
        prefixed_names = point_names if point_names is not None else tuple(dict.fromkeys(
            name for buffer in observation_buffers.values() for name in buffer.keypoint_names
        ))
        data2d_by_camera = {
            camera_id: buffer.to_keypoints_array(names=prefixed_names)[..., :2]
            for camera_id, buffer in observation_buffers.items()
        }
    t0 = time.perf_counter()
    camera_ids = list(data2d_by_camera.keys())

    if len(camera_ids) == 1:
        result = project_2d_batch_to_3d(data2d=data2d_by_camera[camera_ids[0]])
        points_3d = result.points_3d
        reprojection_error = None
    else:
        if set(camera_geometry) != set(camera_ids):
            raise ValueError(
                "Multi-camera triangulation requires resolved calibration geometry"
            )
        triangulator = Triangulator(cameras=[camera_geometry[source] for source in camera_ids])
        result = triangulator.triangulate(
            data2d=np.stack([data2d_by_camera[source] for source in camera_ids]),
            camera_order=triangulator.camera_ids,
            config=triangulation_config,
        )
        points_3d = result.points_3d
        reprojection_error = result.reprojection_error
    timing.record(
        "triangulate",
        time.perf_counter() - t0,
        note=f"{points_3d.shape[0]} frames x {points_3d.shape[1]} points x {len(camera_ids)} cams",
    )

    t0 = time.perf_counter()
    if reprojection_error is not None and max_reprojection_error_px is not None:
        # (n_cameras, T, P) -> mean over cameras -> (T, P); NaN-out points above the gate.
        mean_reproj = np.nanmean(reprojection_error, axis=0)
        points_3d = np.asarray(points_3d).copy()
        points_3d[mean_reproj > max_reprojection_error_px] = np.nan
    keypoints_blender = CALIBRATION_TO_RECONSTRUCTION.convert_point(
        point=Point.from_prevalidated_array(array=np.asarray(points_3d, dtype=np.float64))
    ).array
    unprefixed_names = tuple(_strip_stage_prefix(name) for name in prefixed_names)
    timing.record("reprojection_gate_and_blender", time.perf_counter() - t0)
    return RecordingTriangulation(
        sources=tuple(camera_ids), keypoint_names=unprefixed_names,
        reconstruction=replace(result, points_3d=keypoints_blender),
        diagnostic_point_names=prefixed_names,
    )


def reconstruct_skeletons_for_recording(
    request: RecordingReconstructionInput,
) -> dict[str, ModelRecordingReconstruction]:
    """Fit complete-recording evidence once, then reconstruct with fresh temporal state."""
    return reconstruct_skeletons_with_fits(request=request, fits=fit_skeletons_for_recording(request))


def fit_skeletons_for_recording(request: RecordingReconstructionInput) -> dict[str, FittedRecordingScale]:
    """Fit recording-wide dimensions without running the reconstruction pass."""
    fit_inputs = {
        bundle.model_id: request.fit_inputs(bundle) for bundle in request.bundles
    }
    t0 = time.perf_counter()
    # Map and recover the recording arrays without per-frame dictionaries.
    from skellytracker.core.io.prepared_tracker_mapping import PreparedTrackerMapping
    from skellyforge.core.skeleton.pose.hydration_batch import LandmarkPoseGeometry
    from skellyforge.core.skeleton.pose.model_scale_fitting import (
        fit_model_scale_arrays, scale_voting_segment_names,
    )
    fits = {}
    for bundle in request.bundles:
        mapping = PreparedTrackerMapping.prepare(bundle.landmark_mapping, tracker_names=request.keypoint_names)
        geometry = LandmarkPoseGeometry.from_skeleton(skeleton=bundle.skeleton, landmark_names=mapping.landmark_names)
        scales = np.empty((request.frame_count, len(geometry.segment_names)), np.float64)
        presence = np.empty(scales.shape, bool)
        for start in range(0, request.frame_count, 256):
            stop = min(start + 256, request.frame_count)
            points = request.keypoints_3d[start:stop]
            if request.measured_support is not None:
                points = np.where(request.measured_support[start:stop, :, None], points, np.nan)
            mapped = mapping.apply(tracker_names=request.keypoint_names, positions=points)
            poses = geometry.recover_tensor(positions=mapped.positions, landmark_present=mapped.present)
            scales[start:stop] = poses.scale_estimates
            presence[start:stop] = poses.segment_present
        voters = scale_voting_segment_names(skeleton=bundle.skeleton,
            measured_landmark_names=bundle.landmark_mapping.directly_measured_landmark_names)
        voting_columns = [column for column, name in enumerate(geometry.segment_names) if name in voters]
        fit = fit_model_scale_arrays(skeleton=bundle.skeleton, segment_names=geometry.segment_names,
            scales=scales, segment_present=presence,
            voting_segment_names=voters) if presence[:, voting_columns].any() else None
        fits[bundle.model_id] = FittedRecordingScale(inputs=fit_inputs[bundle.model_id], fit=fit)
    request.timing.record("fit_recording_scale", time.perf_counter() - t0)
    return fits


def reconstruct_skeletons_with_fits(
    *,
    request: RecordingReconstructionInput,
    fits: dict[str, FittedRecordingScale],
) -> dict[str, ModelRecordingReconstruction]:
    """Reconstruct from explicit recording fits, without observing new scale evidence."""
    if set(fits) != {bundle.model_id for bundle in request.bundles}:
        raise ValueError("Saved fits must match the requested model set")
    for bundle in request.bundles:
        if fits[bundle.model_id].inputs != request.fit_inputs(bundle):
            raise ValueError(
                "Saved scale fit inputs changed; rerun recording-wide fitting"
            )
        fit = fits[bundle.model_id].fit
        if fit is not None and set(fit.segment_scales) != set(bundle.skeleton.segments):
            raise ValueError("Saved fit segment set does not match the skeleton")
    states = build_reconstruction_states(
        bundles=request.bundles,
        scale_source_for=lambda bundle: FrozenModelScale(fit=fits[bundle.model_id].fit),
    )
    t0 = time.perf_counter()
    from skellytracker.core.io.prepared_tracker_mapping import PreparedTrackerMapping
    from skellyforge.core.skeleton.pose.hydration_batch import LandmarkPoseGeometry
    from skellyforge.core.data_tensors import AxisDefinition, CompanionTensor, DataTensor
    empty_frames = ~np.isfinite(request.keypoints_3d).all(axis=-1).any(axis=-1)
    sample_axis = AxisDefinition("sample_position", range(request.frame_count))
    results = {}
    for bundle in request.bundles:
        mapping = PreparedTrackerMapping.prepare(bundle.landmark_mapping, tracker_names=request.keypoint_names)
        geometry = LandmarkPoseGeometry.from_skeleton(skeleton=bundle.skeleton, landmark_names=mapping.landmark_names)
        state = states[bundle.model_id]
        outputs = RecordingPoseOutputs(bundle=bundle, fit=fits[bundle.model_id].fit,
            compute_center_of_mass=request.compute_center_of_mass)
        channel_arrays = {}
        # Bound geometry temporaries; the Forge roll resolver preserves chronological state.
        for start in range(0, request.frame_count, 256):
            stop = min(start + 256, request.frame_count)
            mapped = mapping.apply(tracker_names=request.keypoint_names, positions=request.keypoints_3d[start:stop])
            poses = geometry.recover_tensor(positions=mapped.positions, landmark_present=mapped.present)
            if state.roll_resolver is not None:
                poses = state.roll_resolver.resolve_tensor(poses=poses, reset_before=empty_frames[start:stop])
            for tensor in outputs.calculate(poses=poses, landmark_names=mapped.landmark_names,
                landmark_positions=mapped.positions, landmark_present=mapped.present, start_position=start):
                kind = tensor.tensor_layout.channel_kind
                if kind not in channel_arrays:
                    layout = replace(tensor.tensor_layout, axes=(sample_axis, *tensor.tensor_layout.axes[1:]))
                    values = np.empty(layout.shape, dtype=layout.dtype)
                    companions = tuple(CompanionTensor(item.metadata_name,
                        np.empty((request.frame_count, *item.data_values.shape[1:]), dtype=item.data_values.dtype),
                        replace(item.tensor_layout, axes=(sample_axis, *item.tensor_layout.axes[1:])))
                        for item in tensor.companion_tensors)
                    channel_arrays[kind] = (layout, values, companions, tensor.scientific_provenance)
                _, values, companions, _ = channel_arrays[kind]
                values[start:stop] = tensor.data_values
                for destination, source in zip(companions, tensor.companion_tensors, strict=True):
                    destination.data_values[start:stop] = source.data_values
        channel_tensors = []
        # Publish once per channel; temporary output buffers are released as each is owned.
        for kind in tuple(channel_arrays):
            layout, values, companions, provenance = channel_arrays.pop(kind)
            channel_tensors.append(DataTensor(values, layout, provenance, companions).immutable_copy())
        results[bundle.model_id] = ModelRecordingReconstruction(
            fit_inputs=fits[bundle.model_id].inputs, compute_center_of_mass=request.compute_center_of_mass,
            model_id=bundle.model_id, channel_tensors=tuple(channel_tensors), scale_fit=fits[bundle.model_id].fit)
    request.timing.record(
        "reconstruct_frames", time.perf_counter() - t0,
        call_count=request.frame_count * len(request.bundles),
        note=f"{request.frame_count} frames x {len(request.bundles)} model(s)",
    )
    return results
