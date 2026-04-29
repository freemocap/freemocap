"""Solver-only operations on CameraModel for bundle adjustment.

These were previously methods on AniposeCamera/AniposeCameraGroup. Free
functions here keep the shared CameraModel free of solver concerns.
"""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from freemocap.core.tasks.calibration.shared.calibration_models import (
    CameraExtrinsics,
    CameraModel,
)


# Parameter layout per camera: [rvec(3), tvec(3), focal(1), dist0(1)] = 8 floats.
# Matches the original AniposeCamera.get_params/set_params layout (extra_dist=False).
PARAMS_PER_CAMERA = 8


def pack_camera_params(camera: CameraModel) -> NDArray[np.float64]:
    """Pack a camera's optimisable parameters into an 8-element array.

    Layout: [rvec(3), tvec(3), focal(1), dist0(1)].
    Focal is the average of fx/fy.
    """
    intr = camera.intrinsics
    extr = camera.extrinsics
    focal = 0.5 * (intr.fx + intr.fy)
    params = np.zeros(PARAMS_PER_CAMERA, dtype=np.float64)
    params[0:3] = extr.rodrigues_vector
    params[3:6] = extr.translation
    params[6] = focal
    params[7] = intr.k1
    return params


def apply_camera_params(camera: CameraModel, params: NDArray[np.float64]) -> None:
    """Mutate a CameraModel in place from an 8-element parameter array.

    fx/fy are both set to the focal value. cx/cy are preserved. k1 is set
    from params[7]; k2/p1/p2 are zeroed (matches the original AniposeCamera
    behavior, which only optimised k1).
    """
    focal = float(params[6])
    camera.intrinsics.fx = focal
    camera.intrinsics.fy = focal
    camera.intrinsics.k1 = float(params[7])
    camera.intrinsics.k2 = 0.0
    camera.intrinsics.p1 = 0.0
    camera.intrinsics.p2 = 0.0
    camera.extrinsics = CameraExtrinsics.from_rodrigues(
        rvec=np.asarray(params[0:3], dtype=np.float64),
        tvec=np.asarray(params[3:6], dtype=np.float64),
    )


# ----- Bulk accessors (replace AniposeCameraGroup.rotations / .translations) -----


def stack_rodrigues(cameras: list[CameraModel]) -> NDArray[np.float64]:
    """(num_cameras, 3) Rodrigues rotation vectors."""
    return np.array([cam.extrinsics.rodrigues_vector for cam in cameras], dtype=np.float64)


def stack_translations(cameras: list[CameraModel]) -> NDArray[np.float64]:
    """(num_cameras, 3) translation vectors."""
    return np.array([cam.extrinsics.translation for cam in cameras], dtype=np.float64)


def apply_extrinsics(
    cameras: list[CameraModel],
    rvecs: NDArray[np.float64],
    tvecs: NDArray[np.float64],
) -> None:
    """Replace each camera's extrinsics in place from Rodrigues + translation arrays."""
    if len(rvecs) != len(cameras) or len(tvecs) != len(cameras):
        raise ValueError(
            f"extrinsics length mismatch: cameras={len(cameras)}, "
            f"rvecs={len(rvecs)}, tvecs={len(tvecs)}"
        )
    for cam, rvec, tvec in zip(cameras, rvecs, tvecs):
        cam.extrinsics = CameraExtrinsics.from_rodrigues(
            rvec=np.asarray(rvec, dtype=np.float64),
            tvec=np.asarray(tvec, dtype=np.float64),
        )
