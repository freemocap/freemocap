"""Batch triangulation and two-pass skeleton reconstruction with a frozen recording fit."""

import logging
import time
from dataclasses import dataclass, replace
from freemocap.core.reconstruction.coordinate_conventions import CALIBRATION_TO_RECONSTRUCTION
from freemocap.core.reconstruction.recording_fit import FittedRecordingScale

import numpy as np
from skellyforge.core.math.geometry.spatial_vectors import Point
from skellyforge.core.skeleton.pose.hydration import hydrate_skeleton

from freemocap.core.reconstruction.posthoc_timing import PosthocTimingReport
from freemocap.core.skeletons.reconstruct_skeleton import reconstruct_skeleton
from freemocap.core.skeletons.reconstruction_state import (
    FrozenModelScale,
    build_reconstruction_states,
    streaming_model_scale_source,
)
from freemocap.core.reconstruction.recording_reconstruction import (
    RecordingReconstructionInput,
    ModelRecordingReconstruction,
)
from freemocap.core.skeletons.skeleton_reconstruction import SkeletonReconstruction  # noqa: TC001 - runtime type checking
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
) -> RecordingTriangulation:
    """Triangulate the whole recording 2D -> 3D in ONE batched call, Blender-converted.

    Retains source/name axes, solver weights and reprojection errors. Points whose mean reprojection error exceeds
    `max_reprojection_error_px` are set to NaN.

    By default the WHOLE keypoint set is used (`Observation.to_keypoints()`). Pass
    `stage_name` (and optionally `n_points`) to triangulate one detector stage — the
    board path uses `stage_name="charuco"` clamped to `board.n_corners`.
    """
    if not observation_buffers:
        raise ValueError("No observation buffers provided to triangulate.")

    if triangulation_config is None:
        triangulation_config = TriangulationConfig()

    first_buffer = next(iter(observation_buffers.values()))
    frame_numbers = tuple(observation.frame_number for observation in first_buffer.observations)
    if not frame_numbers:
        raise ValueError("Cannot triangulate an empty recording")
    for buffer in observation_buffers.values():
        if tuple(observation.frame_number for observation in buffer.observations) != frame_numbers:
            raise ValueError("Camera observation frame numbers must match exactly")
    first_observation = first_buffer.observations[0]
    if stage_name is not None:
        stage_keypoints = first_observation.stages[stage_name].keypoints
        prefixed_names: tuple[str, ...] = tuple(
            stage_keypoints.names[:n_points]
            if n_points is not None
            else stage_keypoints.names
        )
        data2d_by_camera: dict[CameraIdString, np.ndarray] = {
            camera_id: buffer.to_stage_array(stage_name, n_points)[..., :2]
            for camera_id, buffer in observation_buffers.items()
        }
    else:
        prefixed_names = tuple(dict.fromkeys(
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
    fit_inputs = {
        bundle.model_id: request.fit_inputs(bundle) for bundle in request.bundles
    }
    t0 = time.perf_counter()
    states = build_reconstruction_states(
        bundles=request.bundles,
        scale_source_for=streaming_model_scale_source(
            window_frames=request.frame_count
        ),
    )
    request.timing.record("build_states", time.perf_counter() - t0)
    t0 = time.perf_counter()
    for frame in request.keypoints_3d:
        points = {
            name: frame[index]
            for index, name in enumerate(request.keypoint_names)
            if np.all(np.isfinite(frame[index]))
        }
        for bundle in request.bundles:
            mapped = bundle.landmark_mapping.apply(tracker_positions=points)
            if not mapped:
                continue
            pose = hydrate_skeleton(
                skeleton=bundle.skeleton,
                observed={
                    name: Point.from_array(values=position)
                    for name, position in mapped.items()
                },
                require_all=False,
            )
            states[bundle.model_id].scale_source.observe_pose(pose=pose)
    fits = {
        bundle.model_id: FittedRecordingScale(
            inputs=fit_inputs[bundle.model_id],
            fit=states[bundle.model_id].scale_source.current_fit()
            if states[bundle.model_id].scale_source.has_model_scale
            else None,
        )
        for bundle in request.bundles
    }
    request.timing.record("fit_recording_scale", time.perf_counter() - t0)
    return reconstruct_skeletons_with_fits(request=request, fits=fits)


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
    frames: dict[str, list[SkeletonReconstruction | None]] = {
        bundle.model_id: [] for bundle in request.bundles
    }
    t0 = time.perf_counter()
    for frame in request.keypoints_3d:
        points = {
            name: frame[index]
            for index, name in enumerate(request.keypoint_names)
            if np.all(np.isfinite(frame[index]))
        }
        for bundle in request.bundles:
            frames[bundle.model_id].append(
                reconstruct_skeleton(
                    bundle=bundle,
                    state=states[bundle.model_id],
                    filtered_keypoints=points,
                    compute_center_of_mass=request.compute_center_of_mass,
                )
            )
    request.timing.record(
        "reconstruct_frames",
        time.perf_counter() - t0,
        call_count=request.frame_count * len(request.bundles),
        note=f"{request.frame_count} frames x {len(request.bundles)} model(s)",
    )
    return {
        model_id: ModelRecordingReconstruction(
            fit_inputs=fits[model_id].inputs,
            compute_center_of_mass=request.compute_center_of_mass,
            frames=tuple(values),
            scale_fit=fits[model_id].fit,
        )
        for model_id, values in frames.items()
    }
