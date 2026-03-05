# Adapted (with permission) from the original `aniposelib` package
# (https://github.com/lambdaloop/aniposelib).
# More info on Anipose: https://anipose.readthedocs.io/en/latest/

import logging
import multiprocessing
from collections import defaultdict
from copy import copy
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import toml
from aniposelib.boards import extract_points, extract_rtvecs, merge_rows, CharucoBoard
from numba import jit
from scipy import optimize
from scipy.sparse import dok_matrix
from tqdm import trange

from freemocap.core.calibration.shared.transform_math import build_maximum_spanning_tree, make_M, \
    robust_average_transforms, find_spanning_tree_pairs, get_rtvec

numba_logger = logging.getLogger("numba")
numba_logger.setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

ARUCO_DICTS = {
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


# =============================================================================
# TRIANGULATION & REPROJECTION HELPERS
# =============================================================================


def triangulate_simple(points: np.ndarray, camera_mats: np.ndarray) -> np.ndarray:
    """Triangulate a single 3D point from 2D observations via DLT."""
    num_cams = len(camera_mats)
    A = np.zeros((num_cams * 2, 4))
    for i in range(num_cams):
        x, y = points[i]
        mat = camera_mats[i]
        A[(i * 2): (i * 2 + 1)] = x * mat[2] - mat[0]
        A[(i * 2 + 1): (i * 2 + 2)] = y * mat[2] - mat[1]
    u, s, vh = np.linalg.svd(A, full_matrices=True)
    p3d = vh[-1]
    p3d = p3d[:3] / p3d[3]
    return p3d


def get_error_dict(errors_full: np.ndarray, min_points: int = 10) -> dict:
    """Compute pairwise reprojection error statistics across cameras."""
    n_cams = errors_full.shape[0]
    errors_norm = np.linalg.norm(errors_full, axis=2)
    good = ~np.isnan(errors_full[:, :, 0])
    error_dict = dict()

    for i in range(n_cams):
        for j in range(i + 1, n_cams):
            subset = good[i] & good[j]
            err_subset = errors_norm[:, subset][[i, j]]
            err_subset_mean = np.mean(err_subset, axis=0)
            if np.sum(subset) > min_points:
                percents = np.percentile(err_subset_mean, [15, 75])
                error_dict[(i, j)] = (err_subset.shape[1], percents)
    return error_dict


def subset_extra(extra: dict | None, ixs: np.ndarray) -> dict | None:
    """Subset the extra data dict (board IDs, object points, etc.) by indices."""
    if extra is None:
        return None
    return {
        "objp": extra["objp"][ixs],
        "ids": extra["ids"][ixs],
        "rvecs": extra["rvecs"][:, ixs],
        "tvecs": extra["tvecs"][:, ixs],
    }


def resample_points(
    imgp: np.ndarray,
    extra: dict | None = None,
    n_samp: int = 25,
) -> tuple[np.ndarray, dict | None]:
    """Subsample 2D points for bundle adjustment, prioritizing multi-camera coverage."""
    n_cams = imgp.shape[0]
    good = ~np.isnan(imgp[:, :, 0])
    ixs = np.arange(imgp.shape[1])
    num_cams = np.sum(~np.isnan(imgp[:, :, 0]), axis=0)

    include: set[int] = set()

    for i in range(n_cams):
        for j in range(i + 1, n_cams):
            subset = good[i] & good[j]
            n_good = np.sum(subset)
            if n_good > 0:
                arr = np.copy(num_cams[subset]).astype("float64")
                arr += np.random.random(size=arr.shape)
                picked_ix = np.argsort(-arr)[:n_samp]
                picked = ixs[subset][picked_ix]
                include.update(picked)

    final_ixs = sorted(include)
    newp = imgp[:, final_ixs]
    extra = subset_extra(extra, final_ixs)
    return newp, extra


def transform_points(
    points: np.ndarray,
    rvecs: np.ndarray,
    tvecs: np.ndarray,
) -> np.ndarray:
    """Rotate points by Rodrigues vectors and translate."""
    theta = np.linalg.norm(rvecs, axis=1)[:, np.newaxis]
    with np.errstate(invalid="ignore"):
        v = rvecs / theta
        v = np.nan_to_num(v)
    dot = np.sum(points * v, axis=1)[:, np.newaxis]
    cos_theta = np.cos(theta)
    sin_theta = np.sin(theta)

    rotated = cos_theta * points + sin_theta * np.cross(v, points) + dot * (1 - cos_theta) * v
    return rotated + tvecs


def remap_ids(ids: np.ndarray) -> np.ndarray:
    """Remap arbitrary board IDs to contiguous 0-based indices."""
    unique_ids = np.unique(ids)
    ids_out = np.copy(ids)
    for i, num in enumerate(unique_ids):
        ids_out[ids == num] = i
    return ids_out


# =============================================================================
# CAMERA GRAPH & EXTRINSICS INITIALIZATION
# =============================================================================


def get_connections(
    xs: np.ndarray,
    cam_names: list | None = None,
    both: bool = True,
) -> dict[tuple, int]:
    """Count shared observation pairs between cameras."""
    n_cams = xs.shape[0]
    n_points = xs.shape[1]

    if cam_names is None:
        cam_names = [str(i) for i in range(n_cams)]

    connections: dict[tuple, int] = defaultdict(int)

    for rnum in range(n_points):
        ixs = np.where(~np.isnan(xs[:, rnum, 0]))[0]
        keys = [cam_names[ix] for ix in ixs]
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                a = keys[i]
                b = keys[j]
                connections[(a, b)] += 1
                if both:
                    connections[(b, a)] += 1

    return connections


def get_calibration_graph(
    rtvecs: np.ndarray,
    cam_names: np.ndarray | list | None = None,
) -> dict[int, list[int]]:
    """Build a maximum spanning tree of camera connections from shared observations."""
    n_cams = rtvecs.shape[0]
    if cam_names is None:
        cam_names = np.arange(n_cams)

    connections = get_connections(rtvecs, np.arange(n_cams))

    return build_maximum_spanning_tree(
        connection_counts=connections,
        n_nodes=n_cams,
        node_labels=[str(cn) for cn in cam_names],
    )


def _get_pairwise_transform(rtvecs: np.ndarray, left: int, right: int) -> np.ndarray:
    """Compute the robust average transform between two cameras from shared observations.

    For each frame where both cameras observe the board, computes M_left @ inv(M_right)
    and robustly averages the results.
    """
    transforms: list[np.ndarray] = []

    for dix in range(rtvecs.shape[1]):
        d = rtvecs[:, dix]
        good = ~np.isnan(d[:, 0])
        if good[left] and good[right]:
            M_left = make_M(d[left, 0:3], d[left, 3:6])
            M_right = make_M(d[right, 0:3], d[right, 3:6])
            transforms.append(M_left @ np.linalg.inv(M_right))

    if len(transforms) == 0:
        raise ValueError(f"No shared observations between cameras {left} and {right}")

    logger.info(f"Camera pair ({left}, {right}): {len(transforms)} shared frames")
    return robust_average_transforms(transforms)


def compute_camera_matrices(
    rtvecs: np.ndarray,
    pairs: list[tuple[int, int]],
) -> dict[int, np.ndarray]:
    """Compute camera extrinsics by chaining pairwise transforms along spanning tree pairs.

    Camera at pairs[0][0] is the root (identity transform).
    """
    extrinsics: dict[int, np.ndarray] = {}
    source = pairs[0][0]
    extrinsics[source] = np.identity(4)

    for a, b in pairs:
        if a not in extrinsics:
            raise ValueError(f"Camera {a} must be computed before camera {b}")
        ext = _get_pairwise_transform(rtvecs, b, a)
        extrinsics[b] = ext @ extrinsics[a]

    return extrinsics


def get_initial_extrinsics(
    rtvecs: np.ndarray,
    cam_names: list | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute initial camera extrinsics from board pose observations.

    Builds a spanning tree from shared observation counts, computes pairwise
    transforms, and chains them from camera 0 (the root).

    Returns:
        Tuple of (rvecs, tvecs) arrays, each shape (n_cams, 3).
    """
    n_cams = rtvecs.shape[0]
    n_frames = rtvecs.shape[1]
    logger.info(f"Computing initial extrinsics for {n_cams} cameras from {n_frames} frames")

    for cam_idx in range(n_cams):
        valid_obs = np.sum(~np.isnan(rtvecs[cam_idx, :, 0]))
        cam_name = cam_names[cam_idx] if cam_names else str(cam_idx)
        logger.info(f"Camera {cam_name}: {valid_obs}/{n_frames} valid observations ({100 * valid_obs / n_frames:.1f}%)")

    graph = get_calibration_graph(rtvecs, cam_names)
    logger.info(f"Calibration graph: {dict(graph)}")

    pairs = find_spanning_tree_pairs(graph, root=0)
    logger.info(f"Calibration pairs: {pairs}")

    if len(pairs) != n_cams - 1:
        raise ValueError(f"Expected {n_cams - 1} pairs, got {len(pairs)}. Graph may be disconnected!")

    extrinsics = compute_camera_matrices(rtvecs, pairs)

    rvecs = []
    tvecs = []
    for cnum in range(n_cams):
        if cnum not in extrinsics:
            raise ValueError(f"Missing extrinsics for camera {cnum}")
        rvec, tvec = get_rtvec(extrinsics[cnum])
        rvecs.append(rvec)
        tvecs.append(tvec)

    rvecs_arr = np.array(rvecs)
    tvecs_arr = np.array(tvecs)

    logger.info(f"Rotation magnitudes: {np.linalg.norm(rvecs_arr, axis=1)}")
    logger.info(f"Translation magnitudes: {np.linalg.norm(tvecs_arr, axis=1)}")

    return rvecs_arr, tvecs_arr


# =============================================================================
# CAMERA MODEL
# =============================================================================


class AniposeCamera:
    def __init__(
            self,
            matrix=np.eye(3),
            dist=np.zeros(5),
            size=None,
            rvec=np.zeros(3),
            tvec=np.zeros(3),
            world_orientation=np.eye(3),
            world_position=np.zeros(3),
            name=None,
            extra_dist=False,
    ):
        self.set_camera_matrix(matrix)
        self.set_distortions(dist)
        self.set_size(size)
        self.set_rotation(rvec)
        self.set_translation(tvec)
        self.set_world_orientation(world_orientation)
        self.set_world_position(world_position)
        self.set_name(name)
        self.extra_dist = extra_dist

    def get_dict(self) -> dict:
        return {
            "name": self.get_name(),
            "size": list(self.get_size()),
            "matrix": self.get_camera_matrix().tolist(),
            "distortions": self.get_distortions().tolist(),
            "rotation": self.get_rotation().tolist(),
            "translation": self.get_translation().tolist(),
            "world_orientation": self.get_world_orientation().tolist(),
            "world_position": self.get_world_position().tolist(),
        }

    def load_dict(self, d: dict) -> None:
        self.set_camera_matrix(d["matrix"])
        self.set_rotation(d["rotation"])
        self.set_translation(d["translation"])
        self.set_distortions(d["distortions"])
        self.set_name(d["name"])
        self.set_size(d["size"])
        self.set_world_orientation(d.get("world_orientation", np.eye(3)))
        self.set_world_position(d.get("world_position", np.zeros(3)))

    @staticmethod
    def from_dict(d: dict) -> "AniposeCamera":
        cam = AniposeCamera()
        cam.load_dict(d)
        return cam

    def get_camera_matrix(self) -> np.ndarray:
        return self.matrix

    def get_distortions(self) -> np.ndarray:
        return self.dist

    def set_camera_matrix(self, matrix) -> None:
        self.matrix = np.array(matrix, dtype="float64")

    def set_focal_length(self, fx: float, fy: float | None = None) -> None:
        if fy is None:
            fy = fx
        self.matrix[0, 0] = fx
        self.matrix[1, 1] = fy

    def get_focal_length(self, both: bool = False) -> float | tuple[float, float]:
        fx = self.matrix[0, 0]
        fy = self.matrix[1, 1]
        if both:
            return (fx, fy)
        else:
            return (fx + fy) / 2.0

    def set_distortions(self, dist) -> None:
        self.dist = np.array(dist, dtype="float64").ravel()

    def set_rotation(self, rvec) -> None:
        self.rvec = np.array(rvec, dtype="float64").ravel()

    def get_rotation(self) -> np.ndarray:
        return self.rvec

    def set_translation(self, tvec) -> None:
        self.tvec = np.array(tvec, dtype="float64").ravel()

    def get_translation(self) -> np.ndarray:
        return self.tvec

    def set_world_orientation(self, world_orientation) -> None:
        self.world_orientation = np.asarray(world_orientation, dtype="float64").reshape(3, 3)

    def get_world_orientation(self) -> np.ndarray:
        return self.world_orientation

    def set_world_position(self, world_position) -> None:
        self.world_position = np.array(world_position, dtype="float64").ravel()

    def get_world_position(self) -> np.ndarray:
        return self.world_position

    def get_extrinsics_mat(self) -> np.ndarray:
        return make_M(self.rvec, self.tvec)

    def get_name(self) -> str:
        return self.name

    def set_name(self, name) -> None:
        self.name = str(name)

    def set_size(self, size) -> None:
        """Set size as (width, height)."""
        self.size = size

    def get_size(self):
        """Get size as (width, height)."""
        return self.size

    def get_params(self) -> np.ndarray:
        params = np.zeros(8 + self.extra_dist, dtype="float64")
        params[0:3] = self.get_rotation()
        params[3:6] = self.get_translation()
        params[6] = self.get_focal_length()
        dist = self.get_distortions()
        params[7] = dist[0]
        if self.extra_dist:
            params[8] = dist[1]
        return params

    def set_params(self, params: np.ndarray) -> None:
        self.set_rotation(params[0:3])
        self.set_translation(params[3:6])
        self.set_focal_length(params[6])

        dist = np.zeros(5, dtype="float64")
        dist[0] = params[7]
        if self.extra_dist:
            dist[1] = params[8]
        self.set_distortions(dist)

    def distort_points(self, points: np.ndarray) -> np.ndarray:
        shape = points.shape
        points = points.reshape(-1, 1, 2)
        new_points = np.dstack([points, np.ones((points.shape[0], 1, 1))])
        out, _ = cv2.projectPoints(
            new_points, np.zeros(3), np.zeros(3),
            self.matrix.astype("float64"), self.dist.astype("float64"),
        )
        return out.reshape(shape)

    def undistort_points(self, points: np.ndarray) -> np.ndarray:
        shape = points.shape
        points = points.reshape(-1, 1, 2)
        out = cv2.undistortPoints(points, self.matrix.astype("float64"), self.dist.astype("float64"))
        return out.reshape(shape)

    def project(self, points: np.ndarray) -> np.ndarray:
        points = points.reshape(-1, 1, 3)
        out, _ = cv2.projectPoints(
            points, self.rvec, self.tvec,
            self.matrix.astype("float64"), self.dist.astype("float64"),
        )
        return out

    def single_camera_reprojection_error(self, p3d: np.ndarray, p2d: np.ndarray) -> np.ndarray:
        projected = self.project(p3d).reshape(p2d.shape)
        return p2d - projected

    def copy(self) -> "AniposeCamera":
        return AniposeCamera(
            matrix=self.get_camera_matrix().copy(),
            dist=self.get_distortions().copy(),
            size=self.get_size(),
            rvec=self.get_rotation().copy(),
            tvec=self.get_translation().copy(),
            name=self.get_name(),
            extra_dist=self.extra_dist,
            world_orientation=self.get_world_orientation().copy(),
            world_position=self.get_world_position().copy(),
        )


# =============================================================================
# CAMERA GROUP
# =============================================================================


class AniposeCameraGroup:
    def __init__(self, cameras: list[AniposeCamera], metadata: dict | None = None):
        self.cameras = cameras
        self.metadata = metadata if metadata is not None else {}

    def subset_cameras(self, indices: list[int]) -> "AniposeCameraGroup":
        cams = [self.cameras[ix].copy() for ix in indices]
        return AniposeCameraGroup(cams, self.metadata)

    def subset_cameras_names(self, names: list[str]) -> "AniposeCameraGroup":
        cur_names = self.get_names()
        cur_names_dict = dict(zip(cur_names, range(len(cur_names))))
        indices = []
        for name in names:
            if name not in cur_names_dict:
                raise IndexError(f"name {name} not part of camera names: {cur_names}")
            indices.append(cur_names_dict[name])
        return self.subset_cameras(indices)

    def project(self, points: np.ndarray) -> np.ndarray:
        """Given Nx3 points, returns CxNx2 projected 2D points."""
        points = points.reshape(-1, 1, 3)
        n_points = points.shape[0]
        n_cams = len(self.cameras)

        out = np.empty((n_cams, n_points, 2), dtype="float64")
        for cnum, cam in enumerate(self.cameras):
            out[cnum] = cam.project(points).reshape(n_points, 2)
        return out

    def triangulate(
        self,
        points: np.ndarray,
        undistort: bool = True,
        progress: bool = False,
        kill_event: Optional[multiprocessing.Event ] = None,
    ) -> np.ndarray | None:
        """Given CxNx2 points, returns Nx3 triangulated 3D points."""
        assert points.shape[0] == len(self.cameras), (
            f"First dim should equal number of cameras ({len(self.cameras)}), "
            f"but shape is {points.shape}"
        )

        one_point = False
        if len(points.shape) == 2:
            points = points.reshape(-1, 1, 2)
            one_point = True

        if undistort:
            new_points = np.empty(points.shape)
            for cnum, cam in enumerate(self.cameras):
                sub = np.copy(points[cnum])
                new_points[cnum] = cam.undistort_points(sub)
            points = new_points

        n_cams, n_points, _ = points.shape
        out = np.empty((n_points, 3))
        out[:] = np.nan

        cam_mats = np.array([cam.get_extrinsics_mat() for cam in self.cameras])
        iterator = trange(n_points, ncols=70) if progress else range(n_points)

        for ip in iterator:
            subp = points[:, ip, :]
            good = ~np.isnan(subp[:, 0])
            if np.sum(good) >= 2:
                out[ip] = triangulate_simple(subp[good], cam_mats[good])
            if kill_event is not None and kill_event.is_set():
                return None

        if one_point:
            out = out[0]
        return out

    @jit(parallel=True, forceobj=True)
    def reprojection_error(self, points_3d: np.ndarray, points_2d: np.ndarray, mean: bool = False):
        """Compute reprojection error. Returns CxNx2, or Nx1 if mean=True."""
        one_point = False
        if len(points_3d.shape) == 1 and len(points_2d.shape) == 2:
            points_3d = points_3d.reshape(1, 3)
            points_2d = points_2d.reshape(-1, 1, 2)
            one_point = True

        n_cams, n_points, _ = points_2d.shape
        assert points_3d.shape == (n_points, 3), (
            f"2D/3D shape mismatch: 2D={points_2d.shape}, 3D={points_3d.shape}"
        )

        errors = np.empty((n_cams, n_points, 2))
        for camera_number, cam in enumerate(self.cameras):
            errors[camera_number] = cam.single_camera_reprojection_error(points_3d, points_2d[camera_number])

        if mean:
            errors_norm = np.linalg.norm(errors, axis=2)
            good = ~np.isnan(errors_norm)
            errors_norm[~good] = 0
            denom = np.sum(good, axis=0).astype("float64")
            denom[denom < 1.5] = np.nan
            errors = np.sum(errors_norm, axis=0) / denom

        if one_point:
            errors = float(errors[0]) if mean else errors.reshape(-1, 2)
        return errors

    # -----------------------------------------------------------------
    # BUNDLE ADJUSTMENT
    # -----------------------------------------------------------------

    def bundle_adjust_iter(
            self,
            p2ds,
            extra=None,
            n_iters=10,
            start_mu=15,
            end_mu=1,
            max_nfev=200,
            ftol=1e-4,
            n_samp_iter=100,
            n_samp_full=1000,
            error_threshold=0.3,
            verbose=False,
    ) -> float:
        """Iterative bundle adjustment with outlier-reducing weight schedule."""
        error_list = []

        assert p2ds.shape[0] == len(self.cameras), (
            f"First dim should equal number of cameras ({len(self.cameras)}), but shape is {p2ds.shape}"
        )

        p2ds_full = p2ds
        extra_full = extra

        p2ds, extra = resample_points(p2ds_full, extra_full, n_samp=n_samp_full)
        error = self.average_error(p2ds, median=True)

        if verbose:
            print("error: ", error)

        mus = np.exp(np.linspace(np.log(start_mu), np.log(end_mu), num=n_iters))

        for i in range(n_iters):
            p2ds, extra = resample_points(p2ds_full, extra_full, n_samp=n_samp_full)
            p3ds = self.triangulate(p2ds)
            errors_full = self.reprojection_error(p3ds, p2ds, mean=False)
            errors_norm = self.reprojection_error(p3ds, p2ds, mean=True)

            error_dict = get_error_dict(errors_full)
            max_error = 0
            min_error = 0
            for k, v in error_dict.items():
                num, percents = v
                max_error = max(percents[-1], max_error)
                min_error = max(percents[0], min_error)
            mu = max(min(max_error, mus[i]), min_error)

            good = errors_norm < mu
            extra_good = subset_extra(extra, good)
            p2ds_samp, extra_samp = resample_points(p2ds[:, good], extra_good, n_samp=n_samp_iter)

            error = np.median(errors_norm)
            error_list.append(error)

            if error < error_threshold:
                break

            if verbose:
                print(error_dict)
                print("error: {:.2f}, mu: {:.1f}, ratio: {:.3f}".format(error, mu, np.mean(good)))

            self.bundle_adjust(
                p2ds_samp, extra_samp, loss="linear", ftol=ftol, max_nfev=max_nfev, verbose=verbose,
            )

        # Final pass with relaxed threshold
        p2ds, extra = resample_points(p2ds_full, extra_full, n_samp=n_samp_full)
        p3ds = self.triangulate(p2ds)
        errors_full = self.reprojection_error(p3ds, p2ds, mean=False)
        errors_norm = self.reprojection_error(p3ds, p2ds, mean=True)
        error_dict = get_error_dict(errors_full)

        max_error = 0
        min_error = 0
        for k, v in error_dict.items():
            num, percents = v
            max_error = max(percents[-1], max_error)
            min_error = max(percents[0], min_error)
        mu = max(max(max_error, end_mu), min_error)

        good = errors_norm < mu
        extra_good = subset_extra(extra, good)
        self.bundle_adjust(
            p2ds[:, good], extra_good, loss="linear", ftol=ftol,
            max_nfev=max(200, max_nfev), verbose=verbose,
        )

        return self.average_error(p2ds, median=True)

    def bundle_adjust(
            self,
            p2ds,
            extra=None,
            loss="linear",
            threshold=50,
            ftol=1e-4,
            max_nfev=1000,
            weights=None,
            start_params=None,
            verbose=True,
    ) -> float:
        """Fine-tune camera parameters via scipy least_squares bundle adjustment."""
        assert p2ds.shape[0] == len(self.cameras), (
            f"First dim should equal number of cameras ({len(self.cameras)}), but shape is {p2ds.shape}"
        )

        if extra is not None:
            extra["ids_map"] = remap_ids(extra["ids"])

        x0, n_cam_params = self._initialize_params_bundle(p2ds, extra)

        if start_params is not None:
            x0 = start_params
            n_cam_params = len(self.cameras[0].get_params())

        jac_sparse = self._jac_sparsity_bundle(p2ds, n_cam_params, extra)

        opt = optimize.least_squares(
            self._error_fun_bundle,
            x0,
            jac_sparsity=jac_sparse,
            f_scale=threshold,
            x_scale="jac",
            loss=loss,
            ftol=ftol,
            method="trf",
            tr_solver="lsmr",
            verbose=2 * verbose,
            max_nfev=max_nfev,
            args=(p2ds, n_cam_params, extra),
        )

        for i, cam in enumerate(self.cameras):
            a = i * n_cam_params
            b = (i + 1) * n_cam_params
            cam.set_params(opt.x[a:b])

        return self.average_error(p2ds)

    @jit(parallel=True, forceobj=True)
    def _error_fun_bundle(self, params, p2ds, n_cam_params, extra):
        """Error function for bundle adjustment."""
        good = ~np.isnan(p2ds)
        n_cams = len(self.cameras)

        for i in range(n_cams):
            a = i * n_cam_params
            b = (i + 1) * n_cam_params
            self.cameras[i].set_params(params[a:b])

        sub = n_cam_params * n_cams
        n3d = p2ds.shape[1] * 3
        p3ds_test = params[sub: sub + n3d].reshape(-1, 3)
        errors_reproj = self.reprojection_error(p3ds_test, p2ds)[good]

        if extra is not None:
            ids = extra["ids_map"]
            objp = extra["objp"]
            min_scale = np.min(objp[objp > 0])
            n_boards = int(np.max(ids)) + 1
            a = sub + n3d
            rvecs = params[a: a + n_boards * 3].reshape(-1, 3)
            tvecs = params[a + n_boards * 3: a + n_boards * 6].reshape(-1, 3)
            expected = transform_points(objp, rvecs[ids], tvecs[ids])
            errors_obj = 2 * (p3ds_test - expected).ravel() / min_scale
        else:
            errors_obj = np.array([])

        return np.hstack([errors_reproj, errors_obj])

    def _jac_sparsity_bundle(self, p2ds, n_cam_params, extra):
        """Compute the sparsity structure of the Jacobian for bundle adjustment."""
        point_indices = np.zeros(p2ds.shape, dtype="int32")
        cam_indices = np.zeros(p2ds.shape, dtype="int32")

        for i in range(p2ds.shape[1]):
            point_indices[:, i] = i
        for j in range(p2ds.shape[0]):
            cam_indices[j] = j

        good = ~np.isnan(p2ds)

        if extra is not None:
            ids = extra["ids_map"]
            n_boards = int(np.max(ids)) + 1
            total_board_params = n_boards * 6
        else:
            n_boards = 0
            total_board_params = 0

        n_cams = p2ds.shape[0]
        n_points = p2ds.shape[1]
        total_params_reproj = n_cams * n_cam_params + n_points * 3
        n_params = total_params_reproj + total_board_params

        n_good_values = np.sum(good)
        n_errors = n_good_values + (n_points * 3 if extra is not None else 0)

        A_sparse = dok_matrix((n_errors, n_params), dtype="int16")

        cam_indices_good = cam_indices[good]
        point_indices_good = point_indices[good]
        ix = np.arange(n_good_values)

        for i in range(n_cam_params):
            A_sparse[ix, cam_indices_good * n_cam_params + i] = 1
        for i in range(3):
            A_sparse[ix, n_cams * n_cam_params + point_indices_good * 3 + i] = 1

        if extra is not None:
            point_ix = np.arange(n_points)
            for i in range(3):
                for j in range(3):
                    A_sparse[n_good_values + point_ix * 3 + i, total_params_reproj + ids * 3 + j] = 1
                    A_sparse[n_good_values + point_ix * 3 + i, total_params_reproj + n_boards * 3 + ids * 3 + j] = 1
            for i in range(3):
                A_sparse[n_good_values + point_ix * 3 + i, n_cams * n_cam_params + point_ix * 3 + i] = 1

        return A_sparse

    def _initialize_params_bundle(self, p2ds, extra):
        """Initialize parameter vector for bundle adjustment."""
        cam_params = np.hstack([cam.get_params() for cam in self.cameras])
        n_cam_params = len(cam_params) // len(self.cameras)
        total_cam_params = len(cam_params)

        n_cams, n_points, _ = p2ds.shape
        assert n_cams == len(self.cameras), "Camera count mismatch between group and 2D points"

        p3ds = self.triangulate(p2ds)

        if extra is not None:
            ids = extra["ids_map"]
            n_boards = int(np.max(ids[~np.isnan(ids)])) + 1
            total_board_params = n_boards * 6

            rvecs = np.zeros((n_boards, 3), dtype="float64")
            tvecs = np.zeros((n_boards, 3), dtype="float64")

            if "rvecs" in extra and "tvecs" in extra:
                rvecs_all = extra["rvecs"]
                tvecs_all = extra["tvecs"]
                for board_num in range(n_boards):
                    point_id = np.where(ids == board_num)[0][0]
                    cam_ids_possible = np.where(~np.isnan(p2ds[:, point_id, 0]))[0]
                    cam_id = np.random.choice(cam_ids_possible)
                    M_cam = self.cameras[cam_id].get_extrinsics_mat()
                    M_board_cam = make_M(rvecs_all[cam_id, point_id], tvecs_all[cam_id, point_id])
                    M_board = np.linalg.inv(M_cam) @ M_board_cam
                    rvec, tvec = get_rtvec(M_board)
                    rvecs[board_num] = rvec
                    tvecs[board_num] = tvec
        else:
            total_board_params = 0

        x0 = np.zeros(total_cam_params + p3ds.size + total_board_params)
        x0[:total_cam_params] = cam_params
        x0[total_cam_params: total_cam_params + p3ds.size] = p3ds.ravel()

        if extra is not None:
            start_board = total_cam_params + p3ds.size
            x0[start_board: start_board + n_boards * 3] = rvecs.ravel()
            x0[start_board + n_boards * 3: start_board + n_boards * 6] = tvecs.ravel()

        return x0, n_cam_params

    # -----------------------------------------------------------------
    # ACCESSORS & SERIALIZATION
    # -----------------------------------------------------------------

    def average_error(self, p2ds: np.ndarray, median: bool = False) -> float:
        p3ds = self.triangulate(p2ds)
        errors = self.reprojection_error(p3ds, p2ds, mean=True)
        return np.median(errors) if median else np.mean(errors)

    def set_rotations(self, rvecs: np.ndarray) -> None:
        for cam, rvec in zip(self.cameras, rvecs):
            cam.set_rotation(rvec)

    def set_translations(self, tvecs: np.ndarray) -> None:
        for cam, tvec in zip(self.cameras, tvecs):
            cam.set_translation(tvec)

    def set_world_positions(self, positions: list) -> None:
        for cam, position in zip(self.cameras, positions):
            cam.set_world_position(position)

    def set_world_orientations(self, orientations: list) -> None:
        for cam, orientation in zip(self.cameras, orientations):
            cam.set_world_orientation(orientation)

    def get_world_positions(self) -> np.ndarray:
        return np.stack([cam.get_world_position() for cam in self.cameras])

    def get_world_orientations(self) -> np.ndarray:
        return np.stack([cam.get_world_orientation() for cam in self.cameras])

    def get_rotations(self) -> np.ndarray:
        return np.array([cam.get_rotation() for cam in self.cameras])

    def get_translations(self) -> np.ndarray:
        return np.array([cam.get_translation() for cam in self.cameras])

    def get_names(self) -> list[str]:
        return [cam.get_name() for cam in self.cameras]

    def set_names(self, names: list[str]) -> None:
        for cam, name in zip(self.cameras, names):
            cam.set_name(name)

    def copy(self) -> "AniposeCameraGroup":
        cameras = [cam.copy() for cam in self.cameras]
        metadata = copy(self.metadata)
        return AniposeCameraGroup(cameras, metadata)

    def get_dicts(self) -> list[dict]:
        return [cam.get_dict() for cam in self.cameras]

    @staticmethod
    def from_dicts(cameras_dicts: list[dict]) -> "AniposeCameraGroup":
        cameras = [AniposeCamera.from_dict(d) for d in cameras_dicts]
        return AniposeCameraGroup(cameras)

    @staticmethod
    def from_names(names: list[str]) -> "AniposeCameraGroup":
        cameras = [AniposeCamera(name=name) for name in names]
        return AniposeCameraGroup(cameras)

    def load_dicts(self, arr: list[dict]) -> None:
        for cam, d in zip(self.cameras, arr):
            cam.load_dict(d)

    def dump(self, fname: str | Path) -> None:
        dicts = self.get_dicts()
        names = [camera_dict["name"] for camera_dict in dicts]
        master_dict = dict(zip(names, dicts))
        master_dict["metadata"] = self.metadata
        with open(fname, "w") as f:
            toml.dump(master_dict, f)

    @staticmethod
    def load(fname: str | Path) -> "AniposeCameraGroup":
        if not Path(fname).is_file():
            raise FileNotFoundError(f"File {fname} not found.")
        master_dict = toml.load(fname)
        keys = sorted(master_dict.keys())
        items = [master_dict[k] for k in keys if k != "metadata"]
        cgroup = AniposeCameraGroup.from_dicts(items)
        if "metadata" in master_dict:
            cgroup.metadata = master_dict["metadata"]
        return cgroup

    # -----------------------------------------------------------------
    # CALIBRATION
    # -----------------------------------------------------------------

    def calibrate_rows(
            self,
            all_rows: list[list[dict]],
            board,
            init_intrinsics: bool = True,
            init_extrinsics: bool = True,
            verbose: bool = True,
    ) -> tuple[float, list, list]:
        """Calibrate cameras from charuco board observation rows.

        Returns:
            Tuple of (reprojection_error, merged_rows, charuco_frame_numbers).
        """
        n_cameras = len(self.cameras)
        assert len(all_rows) == n_cameras, (
            f"Detection count ({len(all_rows)}) != camera count ({n_cameras})"
        )

        logger.info(f"Calibrating {n_cameras} cameras")
        for cam_idx, (rows, camera) in enumerate(zip(all_rows, self.cameras)):
            logger.info(f"Camera {cam_idx} ({camera.get_name()}): {len(rows)} frames with detections")
            assert camera.get_size() is not None, f"Camera '{camera.get_name()}' has no frame size"

        if init_intrinsics:
            logger.info("Initializing camera intrinsics...")
            for cam_idx, (rows, camera) in enumerate(zip(all_rows, self.cameras)):
                objp, imgp = board.get_all_calibration_points(rows)
                mixed = [(o, i) for (o, i) in zip(objp, imgp) if len(o) >= 7]
                if len(mixed) == 0:
                    raise ValueError(f"No valid calibration points for camera {cam_idx} (need >= 7)")
                logger.info(f"  Camera {cam_idx}: {len(mixed)} usable frames")
                objp, imgp = zip(*mixed)
                matrix = cv2.initCameraMatrix2D(objp, imgp, tuple(camera.get_size()))
                camera.set_camera_matrix(matrix)

        logger.info("Estimating board poses...")
        for i, (row, cam) in enumerate(zip(all_rows, self.cameras)):
            all_rows[i] = board.estimate_pose_rows(cam, row)

        charuco_frames = [f["framenum"][1] for f in all_rows[0]]

        logger.info("Merging observations across cameras...")
        merged = merge_rows(all_rows)

        imgp, extra = extract_points(merged, board, min_cameras=2)
        logger.info(f"Extracted points: shape={imgp.shape}")

        if init_extrinsics:
            logger.info("Initializing camera extrinsics...")
            rtvecs = extract_rtvecs(merged)

            if verbose:
                connections = get_connections(rtvecs, self.get_names())
                for (cam_a, cam_b), count in sorted(connections.items()):
                    if cam_a < cam_b:
                        logger.info(f"  {cam_a} <-> {cam_b}: {count} shared frames")

            rvecs, tvecs = get_initial_extrinsics(rtvecs, cam_names=self.get_names())
            self.set_rotations(rvecs)
            self.set_translations(tvecs)

        logger.info("Starting iterative bundle adjustment...")
        error = self.bundle_adjust_iter(imgp, extra, verbose=verbose, error_threshold=1)
        logger.info(f"Calibration complete — final error: {error:.4f}")

        return error, merged, charuco_frames


# =============================================================================
# CHARUCO BOARD
# =============================================================================


class AniposeCharucoBoard(CharucoBoard):
    def __init__(
            self,
            squaresX: int = 5,
            squaresY: int = 7,
            square_length: float = 1.0,
            marker_length: float = 0.8,
            marker_bits: int = 4,
            dict_size: int = 250,
    ):
        super().__init__(squaresX, squaresY, square_length, marker_length, marker_bits, dict_size)
        self.squaresX = squaresX
        self.squaresY = squaresY
        self.square_length = square_length
        self.marker_length = marker_length
        self.marker_bits = marker_bits
        self.dict_size = dict_size

        dkey = (marker_bits, dict_size)
        self.dictionary = cv2.aruco.getPredefinedDictionary(ARUCO_DICTS[dkey])

        self.board = cv2.aruco.CharucoBoard(
            size=[squaresX, squaresY],
            squareLength=square_length,
            markerLength=marker_length,
            dictionary=self.dictionary,
        )

        total_size = (squaresX - 1) * (squaresY - 1)
        objp = np.zeros((total_size, 3), np.float64)
        objp[:, :2] = np.mgrid[0: (squaresX - 1), 0: (squaresY - 1)].T.reshape(-1, 2)
        objp *= square_length
        self.objPoints = objp
        self.empty_detection = np.zeros((total_size, 1, 2)) * np.nan
        self.total_size = total_size

    def detect_markers(self, image: np.ndarray, camera=None, refine: bool = True):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

        params = cv2.aruco.DetectorParameters()
        params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_CONTOUR
        params.adaptiveThreshWinSizeMin = 100
        params.adaptiveThreshWinSizeMax = 700
        params.adaptiveThreshWinSizeStep = 50
        params.adaptiveThreshConstant = 0

        try:
            corners, ids, rejectedImgPoints = cv2.aruco.detectMarkers(gray, self.dictionary, parameters=params)
        except Exception:
            ids = None

        if ids is None:
            return [], []

        K = D = None
        if camera is not None:
            K = camera.get_camera_matrix()
            D = camera.get_distortions()

        if refine:
            detectedCorners, detectedIds, _, _ = cv2.aruco.refineDetectedMarkers(
                gray, self.board, corners, ids, rejectedImgPoints, K, D, parameters=params
            )
        else:
            detectedCorners, detectedIds = corners, ids

        return detectedCorners, detectedIds

    def detect_image(self, image: np.ndarray, camera=None):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

        corners, ids = self.detect_markers(image, camera, refine=True)
        if len(corners) > 0:
            ret, detectedCorners, detectedIds = cv2.aruco.interpolateCornersCharuco(
                corners, ids, gray, self.board
            )
            if detectedIds is None:
                detectedCorners = detectedIds = np.float64([])
        else:
            detectedCorners = detectedIds = np.float64([])

        return detectedCorners, detectedIds

    def estimate_pose_points(
        self,
        camera: AniposeCamera,
        corners: np.ndarray | None,
        ids: np.ndarray | None,
    ) -> tuple[np.ndarray | None, np.ndarray | None]:
        if corners is None or ids is None or len(corners) < 5:
            return None, None

        n_corners = corners.size // 2
        corners = np.reshape(corners, (n_corners, 1, 2)).astype(np.float32)
        ids = ids.astype(np.int32) if ids.dtype != np.int32 else ids

        K = camera.get_camera_matrix()
        D = camera.get_distortions()
        ret, rvec, tvec = cv2.aruco.estimatePoseCharucoBoard(corners, ids, self.board, K, D, None, None)
        return rvec, tvec
