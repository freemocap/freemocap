import logging
from typing import Any

import numpy as np
from skellyforge.data_models.trajectory_3d import Trajectory3d
from skellyforge.data_models.type_overloads import CameraIdString

from freemocap.core.tasks.triangulation.helpers.triangulation_config import TriangulationConfig
from freemocap.core.tasks.triangulation.triangulator import Triangulator

logger = logging.getLogger(__name__)


def triangulate_dict(
        data2d_fr_mar_xy_by_camera: dict[CameraIdString, np.ndarray],
        triangulator: Triangulator,
        config: TriangulationConfig | None = None,
        start_frame: int | None = None,
        end_frame: int | None = None,
) -> Trajectory3d:
    """Triangulate pre-stacked 2D arrays (one per camera) into a 3D trajectory.

    Camera matching is fuzzy: each triangulator camera is matched to the data
    dict key that contains it as a substring (e.g. data key "video_synchronized_cam_0"
    matches triangulator camera "cam_0").
    """
    if config is None:
        config = TriangulationConfig()

    triangulator = _subset_triangulator_to_data(
        triangulator=triangulator, data_dict=data2d_fr_mar_xy_by_camera,
    )
    ordered_by_camera_name = _reorder_data_to_triangulator(
        triangulator=triangulator, data_by_camera=data2d_fr_mar_xy_by_camera,
    )

    for cam_name, data in ordered_by_camera_name.items():
        if data.ndim != 3 or data.shape[2] != 2:
            raise ValueError(
                f"Input data arrays must have shape (frames, markers, 2); "
                f"got shape {data.shape} for camera {cam_name}"
            )

    logger.info(
        f"Triangulating {triangulator.n_cameras} cameras, "
        f"{next(iter(ordered_by_camera_name.values())).shape[0]} frames, "
        f"use_outlier_rejection={config.use_outlier_rejection}"
    )

    result = triangulator.triangulate(data2d=ordered_by_camera_name, config=config)

    n_frames = result.points_3d.shape[0]
    if start_frame is None:
        start_frame = 0
    if end_frame is None:
        end_frame = n_frames

    rep_err_per_camera = result.reprojection_error  # (n_cameras, n_frames, n_points)
    rep_err_mean = np.nanmean(rep_err_per_camera, axis=0)  # (n_frames, n_points)

    return Trajectory3d(
        start_frame=start_frame,
        end_frame=end_frame,
        triangulated_data=result.points_3d,
        reprojection_error=rep_err_mean,
        reprojection_error_by_camera=rep_err_per_camera,
    )


def _subset_triangulatocalibration r_to_data(
        *,
        triangulator: Triangulator,
        data_dict: dict[str, Any],
) -> Triangulator:
    """Return a Triangulator whose cameras match the data_dict keys (substring match).

    Mirrors the legacy fuzzy-match behavior: triangulator camera 'cam_0' matches
    data dict key 'video_synchronized_cam_0'.
    """
    valid_camera_ids: list[CameraIdString] = []
    for camera_id in triangulator.camera_ids:
        for key in data_dict.keys():
            if camera_id in key:
                valid_camera_ids.append(camera_id)
                break

    if len(valid_camera_ids) != len(data_dict):
        raise ValueError(
            f"Camera names in data do not match triangulator. "
            f"Make sure calibration matches input data. "
            f"Triangulator: {triangulator.camera_ids}, data: {list(data_dict.keys())}"
        )

    if len(valid_camera_ids) == triangulator.n_cameras:
        return triangulator
    logger.warning(
        f"Data is missing cameras from triangulator, "
        f"triangulating with only cameras present in data: {valid_camera_ids}"
    )
    return triangulator.subset(camera_ids=valid_camera_ids)


def _reorder_data_to_triangulator(
        *,
        triangulator: Triangulator,
        data_by_camera: dict[str, np.ndarray],
) -> dict[str, np.ndarray]:
    """Reorder the data dict to match the triangulator's camera order, keyed by triangulator camera names.

    Returns a dict whose keys are triangulator camera names (not the original data keys).
    """
    ordered: dict[str, np.ndarray] = {}
    for camera_name in triangulator.camera_ids:
        for camera_id, data in data_by_camera.items():
            if camera_name in camera_id:
                ordered[camera_name] = data
                break
    return ordered
