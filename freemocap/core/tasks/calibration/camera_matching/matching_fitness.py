"""Spot-check a fixed camera assignment using shared triangulation and projection."""

import itertools

import cv2
import numpy as np
from numpy.typing import NDArray

from freemocap.core.tasks.calibration.camera_matching.matching_models import (
    CameraFitness,
    GeometryFitness,
    GeometryFitnessRequest,
    GeometryFitnessStatus,
)
from freemocap.core.tasks.triangulation.helpers.triangulation_config import TriangulationConfig
from freemocap.core.tasks.triangulation.triangulator import Triangulator


def _conditioned_points(request: GeometryFitnessRequest) -> NDArray[np.bool_]:
    rays = np.full((*request.pixels.shape[:-1], 3), np.nan, dtype=np.float64)
    for index, camera in enumerate(request.cameras):
        present = np.isfinite(request.pixels[index]).all(axis=-1)
        if not present.any():
            continue
        normalized = cv2.undistortPoints(
            request.pixels[index][present].reshape(-1, 1, 2),
            camera.intrinsics.to_camera_matrix(), camera.intrinsics.to_dist_coeffs(),
        ).reshape(-1, 2)
        camera_rays = np.column_stack((normalized, np.ones(len(normalized))))
        world_rays = camera_rays @ camera.extrinsics.rotation_matrix
        rays[index][present] = world_rays / np.linalg.norm(world_rays, axis=-1, keepdims=True)
    conditioned = np.zeros(request.pixels.shape[1:3], dtype=np.bool_)
    minimum_sine = np.sin(np.deg2rad(request.config.minimum_ray_angle_degrees))
    for left, right in itertools.combinations(range(len(request.cameras)), 2):
        separation = np.linalg.norm(np.cross(rays[left], rays[right]), axis=-1)
        conditioned |= separation >= minimum_sine
    return conditioned


def evaluate_geometry_fitness(*, request: GeometryFitnessRequest) -> GeometryFitness:
    """Never drop a poorly fitting camera to make an assignment pass.

    Errors are expressed in pixels at a 1000-pixel image diagonal. Invalid geometry
    counts against valid_fraction; absent input does not. The caller owns sampling,
    instance association, detector validity and the policy for continuing processing.
    """
    present = np.isfinite(request.pixels).all(axis=-1)
    shared = present.sum(axis=0) >= 2
    eligible = present & shared[None, ...]
    qualifying_frames = (eligible.sum(axis=-1) >= request.config.minimum_points_per_frame).sum(axis=-1)
    if np.any(qualifying_frames < request.config.minimum_frames):
        return GeometryFitness(status=GeometryFitnessStatus.INSUFFICIENT, cameras=())

    pixels = request.pixels.copy()
    pixels[:, ~_conditioned_points(request)] = np.nan
    triangulator = Triangulator(cameras=list(request.cameras))
    # Homogeneous points at infinity are invalid evidence, not finite reconstructions.
    with np.errstate(divide="ignore", invalid="ignore"):
        reconstruction = triangulator.triangulate(
            data2d=pixels,
            config=TriangulationConfig(use_outlier_rejection=False),
            camera_order=triangulator.camera_ids,
        )
    finite = np.isfinite(reconstruction.points_3d).all(axis=-1)
    diagnostics: list[CameraFitness] = []
    squared_errors = np.zeros(shared.shape, dtype=np.float64)
    for index, camera in enumerate(request.cameras):
        depths = (reconstruction.points_3d @ camera.extrinsics.rotation_matrix.T)[..., 2]
        depths += camera.extrinsics.translation[2]
        valid = finite & (depths > 0) & np.isfinite(reconstruction.reprojection_error[index])
        observed = int(eligible[index].sum())
        errors = np.full(shared.shape, np.inf, dtype=np.float64)
        errors[valid] = reconstruction.reprojection_error[index][valid] * 1000.0 / np.hypot(*camera.image_size)
        selected = errors[eligible[index]]
        squared_errors += np.where(eligible[index], errors ** 2, 0.0)
        diagnostics.append(CameraFitness(
            camera_id=camera.id,
            observed_points=observed,
            qualifying_frames=int(qualifying_frames[index]),
            valid_fraction=float((valid & eligible[index]).sum() / observed),
            median_error=float(np.quantile(selected, 0.5, method="higher")),
            p90_error=float(np.quantile(selected, 0.9, method="higher")),
        ))
    acceptable = all(
        item.valid_fraction >= request.config.minimum_valid_fraction
        and item.median_error <= request.config.maximum_median_error
        and item.p90_error <= request.config.maximum_p90_error
        for item in diagnostics
    )
    point_costs = np.minimum(
        squared_errors[:, :] / np.maximum(eligible.sum(axis=0), 1) / request.config.maximum_p90_error ** 2,
        1.0,
    )
    frame_counts = shared.sum(axis=-1)
    frame_costs = (point_costs * shared).sum(axis=-1) / np.maximum(frame_counts, 1)
    return GeometryFitness(
        status=GeometryFitnessStatus.ACCEPTABLE if acceptable else GeometryFitnessStatus.POOR,
        cameras=tuple(diagnostics),
        mean_cost=float(frame_costs[frame_counts > 0].mean()),
    )
