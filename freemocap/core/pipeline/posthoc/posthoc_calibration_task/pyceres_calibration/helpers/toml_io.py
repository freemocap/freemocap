"""Load and save calibration data in the anipose-compatible TOML format.

Maintains backward compatibility with existing freemocap calibration files
so the rest of the pipeline (triangulation, mocap, etc.) continues to work.
"""

import logging
from pathlib import Path

import numpy as np
import toml

from .models import (
    CalibrationResult,
    CameraExtrinsics,
    CameraIntrinsics,
    CameraModel,
)

logger = logging.getLogger(__name__)


def save_calibration_toml(
    *,
    result: CalibrationResult,
    path: Path,
    metadata: dict | None = None,
) -> None:
    """Save calibration result to TOML in the anipose-compatible format.

    Format per camera:
        [camera_name]
        name = "camera_name"
        size = [width, height]
        matrix = [[fx, 0, cx], [0, fy, cy], [0, 0, 1]]
        distortions = [k1, k2, p1, p2, 0.0]
        rotation = [rx, ry, rz]   (Rodrigues vector)
        translation = [tx, ty, tz]
        world_orientation = [[...], [...], [...]]   (3x3 rotation matrix, cam→world)
        world_position = [wx, wy, wz]

    Args:
        result: CalibrationResult to save.
        path: Output file path.
        metadata: Additional metadata dict to include.
    """
    cameras: dict = {}

    for cam in result.cameras:
        K = cam.intrinsics.to_camera_matrix()
        dist = np.zeros(5, dtype=np.float64)
        dist_4 = cam.intrinsics.to_dist_coeffs()
        dist[:4] = dist_4

        rvec = cam.extrinsics.rodrigues_vector
        tvec = cam.extrinsics.translation
        world_pos = cam.extrinsics.world_position
        world_ori = cam.extrinsics.world_orientation

        cam_dict = {
            "name": cam.name,
            "size": list(cam.image_size),
            "matrix": K.tolist(),
            "distortions": dist.tolist(),
            "rotation": rvec.tolist(),
            "translation": tvec.tolist(),
            "world_orientation": world_ori.tolist(),
            "world_position": world_pos.tolist(),
        }
        cameras[cam.name] = cam_dict

    # Metadata
    meta = metadata.copy() if metadata else {}
    meta["reprojection_error_px"] = result.reprojection_error_px
    meta["n_observations_used"] = result.n_observations_used
    meta["n_observations_rejected"] = result.n_observations_rejected
    meta["solver_time_seconds"] = result.time_seconds
    meta["board"] = {
        "squares_x": result.board.squares_x,
        "squares_y": result.board.squares_y,
        "square_length_mm": result.board.square_length_mm,
        "marker_length_mm": result.board.marker_length_mm,
    }
    cameras["metadata"] = meta

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        toml.dump(cameras, f)

    logger.info(f"Saved calibration to: {path}")


def load_calibration_toml(
    *,
    path: Path,
) -> tuple[list[CameraModel], dict]:
    """Load camera models from an anipose-compatible TOML calibration file.

    Args:
        path: Path to the TOML file.

    Returns:
        Tuple of (list of CameraModel, metadata dict).
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Calibration file not found: {path}")

    toml_data = toml.load(path)
    metadata = toml_data.pop("metadata", {})

    cameras: list[CameraModel] = []
    for key in sorted(toml_data.keys()):
        d = toml_data[key]

        if "name" not in d:
            logger.warning(f"Skipping TOML key '{key}' — no 'name' field")
            continue

        # Parse image size
        if "size" in d:
            size = (int(d["size"][0]), int(d["size"][1]))
        elif "image_size" in d:
            size = (int(d["image_size"][0]), int(d["image_size"][1]))
        else:
            raise KeyError(f"Camera '{key}' missing 'size' or 'image_size'")

        # Parse intrinsics
        K = np.array(d["matrix"], dtype=np.float64)
        if K.shape != (3, 3):
            raise ValueError(f"Camera '{key}': matrix shape {K.shape}, expected (3, 3)")

        dist = np.array(d["distortions"], dtype=np.float64).ravel()

        intrinsics = CameraIntrinsics(
            fx=float(K[0, 0]),
            fy=float(K[1, 1]),
            cx=float(K[0, 2]),
            cy=float(K[1, 2]),
            k1=float(dist[0]) if len(dist) > 0 else 0.0,
            k2=float(dist[1]) if len(dist) > 1 else 0.0,
            p1=float(dist[2]) if len(dist) > 2 else 0.0,
            p2=float(dist[3]) if len(dist) > 3 else 0.0,
        )

        # Parse extrinsics
        rvec = np.array(d["rotation"], dtype=np.float64).ravel()
        tvec = np.array(d["translation"], dtype=np.float64).ravel()

        extrinsics = CameraExtrinsics.from_rodrigues(rvec=rvec, tvec=tvec)

        cameras.append(
            CameraModel(
                name=str(d["name"]),
                image_size=size,
                intrinsics=intrinsics,
                extrinsics=extrinsics,
            )
        )

    if len(cameras) == 0:
        raise ValueError(f"No cameras found in {path}")

    logger.info(f"Loaded {len(cameras)} cameras from {path}")
    return cameras, metadata
