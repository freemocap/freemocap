"""Charuco board operations driven by CharucoBoardDefinition.

These were previously methods on AniposeCharucoBoard. Free functions here
let the bundle-adjustment solver operate directly on the shared board
definition without a parallel board class.

Detection (`detect_image` / `detect_markers` from the old AniposeCharucoBoard)
is intentionally not ported: charuco detection is performed upstream by
skellytracker, and the calibration solver only needs the geometry +
solvePnP pose-estimation half.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

# Integer array — ids may arrive as int32 or int64; use plain np.ndarray to
# avoid beartype rejecting a valid but narrower dtype.
IntArray = np.ndarray

from freemocap.core.tasks.calibration.shared.calibration_models import (
    CameraModel,
    CharucoBoardDefinition,
)


_ARUCO_DICTS = {
    (4, 50): cv2.aruco.DICT_4X4_50,
    (5, 50): cv2.aruco.DICT_5X5_50,
    (6, 50): cv2.aruco.DICT_6X6_50,
    (7, 50): cv2.aruco.DICT_7X7_50,
    (4, 100): cv2.aruco.DICT_4X4_100,
    (5, 100): cv2.aruco.DICT_5X5_100,
    (6, 100): cv2.aruco.DICT_6X6_100,
    (7, 100): cv2.aruco.DICT_7X7_100,
    (4, 250): cv2.aruco.DICT_4X4_250,
    (5, 250): cv2.aruco.DICT_5X5_250,
    (6, 250): cv2.aruco.DICT_6X6_250,
    (7, 250): cv2.aruco.DICT_7X7_250,
    (4, 1000): cv2.aruco.DICT_4X4_1000,
    (5, 1000): cv2.aruco.DICT_5X5_1000,
    (6, 1000): cv2.aruco.DICT_6X6_1000,
    (7, 1000): cv2.aruco.DICT_7X7_1000,
}


@dataclass(frozen=True)
class _BoardCv2State:
    object_points: NDArray[np.float64]
    empty_detection: NDArray[np.float64]
    n_corners: int


@lru_cache(maxsize=8)
def _build_state(
    squares_x: int,
    squares_y: int,
    square_length_mm: float,
) -> _BoardCv2State:
    cols = squares_x - 1
    rows = squares_y - 1
    n_corners = cols * rows
    objp = np.zeros((n_corners, 3), dtype=np.float64)
    objp[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2)
    objp *= square_length_mm
    empty = np.full((n_corners, 1, 2), np.nan, dtype=np.float64)
    return _BoardCv2State(object_points=objp, empty_detection=empty, n_corners=n_corners)


def _state(board: CharucoBoardDefinition) -> _BoardCv2State:
    return _build_state(board.squares_x, board.squares_y, board.square_length_mm)


def get_object_points(board: CharucoBoardDefinition) -> NDArray[np.float64]:
    """(n_corners, 3) board-frame corner positions, Z=0 plane."""
    return _state(board).object_points


def get_empty_detection(board: CharucoBoardDefinition) -> NDArray[np.float64]:
    """(n_corners, 1, 2) NaN-filled detection template."""
    return np.copy(_state(board).empty_detection)


def fill_points(
    board: CharucoBoardDefinition,
    corners: NDArray[np.float64] | None,
    ids: IntArray | None,
) -> NDArray[np.float64]:
    """Scatter detected corners into a (n_corners, 1, 2) array indexed by corner id."""
    out = get_empty_detection(board)
    if corners is None or len(corners) == 0 or ids is None:
        return out
    flat_ids = ids.ravel()
    for i, cxs in zip(flat_ids, corners):
        out[i] = cxs
    return out


def estimate_pose_points(
    board: CharucoBoardDefinition,
    camera: CameraModel,
    corners: NDArray[np.float64] | None,
    ids: IntArray | None,
) -> tuple[NDArray[np.float64] | None, NDArray[np.float64] | None]:
    """solvePnP-based board pose estimate. Returns (rvec, tvec) or (None, None).

    Requires >= 6 charuco corner correspondences (cv2.solvePnP DLT minimum).
    """
    if corners is None or ids is None or len(corners) < 6:
        return None, None

    flat_ids = ids.flatten()
    obj_points = get_object_points(board)[flat_ids].astype(np.float64)
    img_points = corners.reshape(-1, 1, 2).astype(np.float64)

    K = camera.intrinsics.to_camera_matrix()
    D = camera.intrinsics.to_dist_coeffs_5()

    ret, rvec, tvec = cv2.solvePnP(
        objectPoints=obj_points,
        imagePoints=img_points,
        cameraMatrix=K,
        distCoeffs=D,
    )
    if not ret:
        return None, None
    return rvec, tvec


def estimate_pose_rows(
    board: CharucoBoardDefinition,
    camera: CameraModel,
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Annotate each detection row with rvec/tvec from solvePnP."""
    for row in rows:
        rvec, tvec = estimate_pose_points(board, camera, row["corners"], row["ids"])
        row["rvec"] = rvec
        row["tvec"] = tvec
    return rows


def fill_points_rows(
    board: CharucoBoardDefinition,
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Annotate each detection row with a 'filled' (n_corners, 1, 2) array."""
    for row in rows:
        row["filled"] = fill_points(board, row["corners"], row["ids"])
    return rows


def get_all_calibration_points(
    board: CharucoBoardDefinition,
    rows: list[dict[str, Any]],
    min_points: int = 5,
) -> tuple[list[NDArray[np.float32]], list[NDArray[np.float32]]]:
    """Return (object_points_per_frame, image_points_per_frame) for cv2.initCameraMatrix2D."""
    rows = fill_points_rows(board, rows)

    objpoints = get_object_points(board).reshape(-1, 3)

    all_obj: list[NDArray[np.float32]] = []
    all_img: list[NDArray[np.float32]] = []

    for row in rows:
        filled = row["filled"].reshape(-1, 2)
        good = np.all(~np.isnan(filled), axis=1)
        if np.sum(good) >= min_points:
            all_obj.append(np.float32(objpoints[good]))
            all_img.append(np.float32(filled[good]))

    return all_obj, all_img
