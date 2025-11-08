# Most of this was copied (with permission) from the original `aniposelib` package (https://github.com/lambdaloop/aniposelib), and we're adapting it to our needs here. M
# ore info on Anipoise: https://anipose.readthedocs.io/en/latest/

import itertools
import logging
import multiprocessing
import queue
import time
from collections import defaultdict, Counter
from copy import copy
from pathlib import Path
from typing import List

import cv2
import numpy as np
import toml
from aniposelib.boards import extract_points, extract_rtvecs, get_video_params, merge_rows, CharucoBoard
from aniposelib.utils import get_rtvec, make_M
from numba import jit
from scipy import optimize
from scipy import signal
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.cluster.vq import whiten
from scipy.linalg import inv as inverse
from scipy.sparse import dok_matrix
# from skellytracker.process_folder_of_videos import process_list_of_videos
# from skellytracker.trackers.charuco_tracker.charuco_model_info import CharucoModelInfo, CharucoTrackingParams
from tqdm import trange

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


# @jit(nopython=True, parallel=False)
def triangulate_simple(points, camera_mats):
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


def get_error_dict(errors_full, min_points=10):
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
                # percents = np.percentile(err_subset, [25, 75])
                error_dict[(i, j)] = (err_subset.shape[1], percents)
    return error_dict


def check_errors(cgroup, imgp):
    p3ds = cgroup.triangulate(imgp)
    errors_full = cgroup.reprojection_error(p3ds, imgp, mean=False)
    return get_error_dict(errors_full)


def subset_extra(extra, ixs):
    if extra is None:
        return None

    new_extra = {
        "objp": extra["objp"][ixs],
        "ids": extra["ids"][ixs],
        "rvecs": extra["rvecs"][:, ixs],
        "tvecs": extra["tvecs"][:, ixs],
    }
    return new_extra


def resample_points_extra(imgp, extra, n_samp=25):
    n_cams, n_points, _ = imgp.shape
    ids = remap_ids(extra["ids"])
    n_ids = np.max(ids) + 1
    good = ~np.isnan(imgp[:, :, 0])
    ixs = np.arange(n_points)

    cam_counts = np.zeros((n_ids, n_cams), dtype="int64")
    for idnum in range(n_ids):
        cam_counts[idnum] = np.sum(good[:, ids == idnum], axis=1)
    cam_counts_random = cam_counts + np.random.random(size=cam_counts.shape)
    best_boards = np.argsort(-cam_counts_random, axis=0)

    cam_totals = np.zeros(n_cams, dtype="int64")

    include = set()
    for cam_num in range(n_cams):
        for board_id in best_boards[:, cam_num]:
            include.update(ixs[ids == board_id])
            cam_totals += cam_counts[board_id]
            if cam_totals[cam_num] >= n_samp or cam_counts_random[board_id, cam_num] < 1:
                break

    final_ixs = sorted(include)
    newp = imgp[:, final_ixs]
    extra = subset_extra(extra, final_ixs)
    return newp, extra


def resample_points(imgp, extra=None, n_samp=25):
    # if extra is not None:
    #     return resample_points_extra(imgp, extra, n_samp)

    n_cams = imgp.shape[0]
    good = ~np.isnan(imgp[:, :, 0])
    ixs = np.arange(imgp.shape[1])

    num_cams = np.sum(~np.isnan(imgp[:, :, 0]), axis=0)

    include = set()

    for i in range(n_cams):
        for j in range(i + 1, n_cams):
            subset = good[i] & good[j]
            n_good = np.sum(subset)
            if n_good > 0:
                ## pick points, prioritizing points seen by more cameras
                arr = np.copy(num_cams[subset]).astype("float64")
                arr += np.random.random(size=arr.shape)
                picked_ix = np.argsort(-arr)[:n_samp]
                picked = ixs[subset][picked_ix]
                include.update(picked)

    final_ixs = sorted(include)
    newp = imgp[:, final_ixs]
    extra = subset_extra(extra, final_ixs)
    return newp, extra


def medfilt_data(values, size=15):
    padsize = size + 5
    vpad = np.pad(values, (padsize, padsize), mode="reflect")
    vpadf = signal.medfilt(vpad, kernel_size=size)
    return vpadf[padsize:-padsize]


def nan_helper(y):
    return np.isnan(y), lambda z: z.nonzero()[0]


def interpolate_data(vals):
    nans, ix = nan_helper(vals)
    out = np.copy(vals)
    try:
        out[nans] = np.interp(ix(nans), ix(~nans), vals[~nans])
    except ValueError:
        out[:] = 0
    return out


def remap_ids(ids):
    unique_ids = np.unique(ids)
    ids_out = np.copy(ids)
    for i, num in enumerate(unique_ids):
        ids_out[ids == num] = i
    return ids_out


def transform_points(points, rvecs, tvecs):
    """Rotate points by given rotation vectors and translate.
    Rodrigues' rotation formula is used.
    """
    theta = np.linalg.norm(rvecs, axis=1)[:, np.newaxis]
    with np.errstate(invalid="ignore"):
        v = rvecs / theta
        v = np.nan_to_num(v)
    dot = np.sum(points * v, axis=1)[:, np.newaxis]
    cos_theta = np.cos(theta)
    sin_theta = np.sin(theta)

    rotated = cos_theta * points + sin_theta * np.cross(v, points) + dot * (1 - cos_theta) * v

    return rotated + tvecs


def get_connections(xs: np.ndarray, cam_names: list | None = None, both: bool = True) -> dict[tuple, int]:
    """Get connection counts between camera pairs."""
    from collections import defaultdict

    n_cams = xs.shape[0]
    n_points = xs.shape[1]

    if cam_names is None:
        cam_names = [str(i) for i in range(n_cams)]

    connections = defaultdict(int)

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


def get_calibration_graph(rtvecs, cam_names=None):
    n_cams = rtvecs.shape[0]
    n_points = rtvecs.shape[1]

    if cam_names is None:
        cam_names = np.arange(n_cams)

    connections = get_connections(rtvecs, np.arange(n_cams))

    components = dict(zip(np.arange(n_cams), range(n_cams)))
    edges = set(connections.items())

    graph = defaultdict(list)

    for edgenum in range(n_cams - 1):
        if len(edges) == 0:
            component_names = dict()
            for k, v in list(components.items()):
                component_names[cam_names[k]] = v
            raise ValueError(
                """
Could not build calibration graph.
Some group of cameras could not be paired by simultaneous calibration board detections.
Check which cameras have different group numbers below to see the missing edges.
{}""".format(
                    component_names
                )
            )

        (a, b), weight = max(edges, key=lambda x: x[1])
        graph[a].append(b)
        graph[b].append(a)

        match = components[a]
        replace = components[b]
        for k, v in components.items():
            if match == v:
                components[k] = replace

        for e in edges.copy():
            (a, b), w = e
            if components[a] == components[b]:
                edges.remove(e)

    return graph


def find_calibration_pairs(graph, source=None):
    pairs = []
    explored = set()

    if source is None:
        source = sorted(graph.keys())[0]

    q = queue.deque()
    q.append(source)

    while len(q) > 0:
        item = q.pop()
        explored.add(item)

        for new in graph[item]:
            if new not in explored:
                q.append(new)
                pairs.append((item, new))
    return pairs


def compute_camera_matrices(rtvecs: np.ndarray, pairs: list[tuple[int, int]]) -> dict[int, np.ndarray]:
    """
    Compute camera extrinsics from calibration pairs.

    Args:
        rtvecs: Rotation/translation vectors
        pairs: List of (source, target) camera pairs

    Returns:
        Dictionary mapping camera index to 4x4 transformation matrix
    """
    logger.debug(f"Computing camera matrices for {len(pairs)} pairs")

    extrinsics = dict()
    source = pairs[0][0]
    extrinsics[source] = np.identity(4)
    logger.debug(f"Camera {source} set as origin (identity transform)")

    for i, (a, b) in enumerate(pairs):
        logger.debug(f"Pair {i + 1}/{len(pairs)}: Computing transform from {a} to {b}")

        if a not in extrinsics:
            logger.error(f"Camera {a} not yet in extrinsics! Pairs may be ordered incorrectly.")
            raise ValueError(f"Camera {a} must be computed before camera {b}")

        try:
            ext = get_transform(rtvecs, b, a)
            extrinsics[b] = np.matmul(ext, extrinsics[a])
            logger.debug(f"Camera {b} extrinsics computed successfully")
        except Exception as e:
            logger.error(f"Failed to compute transform from {a} to {b}: {e}")
            raise

    logger.info(f"Computed extrinsics for {len(extrinsics)} cameras")
    return extrinsics


def get_transform(rtvecs: np.ndarray, left: int, right: int) -> np.ndarray:
    """
    Calculate transform between two cameras with improved convergence.
    """
    logger.debug(f"Computing transform between camera {left} and camera {right}")

    L = []
    valid_frames = 0

    for dix in range(rtvecs.shape[1]):
        d = rtvecs[:, dix]
        good = ~np.isnan(d[:, 0])

        if good[left] and good[right]:
            valid_frames += 1
            M_left = make_M(d[left, 0:3], d[left, 3:6])
            M_right = make_M(d[right, 0:3], d[right, 3:6])
            M = np.matmul(M_left, inverse(M_right))
            L.append(M)

    logger.info(f"Camera pair ({left}, {right}): Found {valid_frames} frames with valid observations")

    if len(L) == 0:
        raise ValueError(f"No valid transformation matrices found between cameras {left} and {right}")

    logger.debug(f"Selecting best matrices from {len(L)} candidates")
    L_best = select_matrices(L)
    logger.info(f"Selected {len(L_best)} matrices after clustering (removed {len(L) - len(L_best)} outliers)")

    logger.debug("Computing initial mean transform")
    M_mean = mean_transform(L_best)

    # Progressive refinement with decreasing thresholds
    # Start more permissive and gradually tighten
    thresholds = [0.5, 0.3, 0.15, 0.1]

    for i, error_threshold in enumerate(thresholds):
        logger.debug(f"Robust refinement {i + 1}/{len(thresholds)} with error threshold {error_threshold}")

        M_mean_new = mean_transform_robust(
            L,
            M_mean,
            error=error_threshold,
            max_iterations=3,
            convergence_threshold=0.001
        )

        # Check if transform changed significantly
        diff = np.max(np.abs(M_mean_new - M_mean))
        logger.debug(f"Transform difference after refinement: {diff:.6f}")

        # If change is too large, refinement may be unstable - use previous result
        if diff > 10.0:  # ~10 radians or 10mm is likely unstable
            logger.warning(f"Large transform change ({diff:.2f}) detected, refinement may be unstable")
            logger.warning(f"Stopping refinement and using previous result")
            break

        M_mean = M_mean_new

    logger.info(f"Final transform computed for camera pair ({left}, {right})")
    return M_mean


def get_most_common(vals):
    Z = linkage(whiten(vals), "ward")
    n_clust = max(len(vals) / 10, 3)
    clusts = fcluster(Z, t=n_clust, criterion="maxclust")
    cc = Counter(clusts[clusts >= 0])
    most = cc.most_common(n=1)
    top = most[0][0]
    good = clusts == top
    return good


def select_matrices(Ms):
    Ms = np.array(Ms)
    rvecs = [cv2.Rodrigues(M[:3, :3])[0][:, 0] for M in Ms]
    tvecs = np.array([M[:3, 3] for M in Ms])
    best = get_most_common(np.hstack([rvecs, tvecs]))
    Ms_best = Ms[best]
    return Ms_best


def mean_transform(M_list: list[np.ndarray]) -> np.ndarray:
    """
    Compute mean transformation from list of transformation matrices.

    Args:
        M_list: List of 4x4 transformation matrices

    Returns:
        Mean transformation matrix
    """
    if len(M_list) == 0:
        raise ValueError("Cannot compute mean transform from empty matrix list")

    logger.debug(f"Computing mean of {len(M_list)} transformation matrices")

    rvecs = []
    tvecs = []

    for i, M in enumerate(M_list):
        try:
            rvec = cv2.Rodrigues(M[:3, :3])[0][:, 0]
            tvec = M[:3, 3]

            # Validate shapes
            if rvec.shape != (3,):
                logger.error(f"Matrix {i}: Invalid rvec shape {rvec.shape}, expected (3,)")
                continue
            if tvec.shape != (3,):
                logger.error(f"Matrix {i}: Invalid tvec shape {tvec.shape}, expected (3,)")
                continue

            rvecs.append(rvec)
            tvecs.append(tvec)

        except Exception as e:
            logger.warning(f"Matrix {i}: Failed to extract rvec/tvec - {e}")
            continue

    if len(rvecs) == 0:
        raise ValueError("No valid rvecs could be extracted from transformation matrices")

    rvec = np.mean(rvecs, axis=0)
    tvec = np.mean(tvecs, axis=0)

    # Final validation
    if rvec.shape != (3,):
        raise ValueError(f"Invalid mean rvec shape {rvec.shape}, expected (3,). Input had {len(rvecs)} valid vectors")
    if tvec.shape != (3,):
        raise ValueError(f"Invalid mean tvec shape {tvec.shape}, expected (3,). Input had {len(tvecs)} valid vectors")

    # Check for NaN
    if np.any(np.isnan(rvec)):
        logger.error(f"NaN in mean rvec: {rvec}")
        raise ValueError("Mean rvec contains NaN values")
    if np.any(np.isnan(tvec)):
        logger.error(f"NaN in mean tvec: {tvec}")
        raise ValueError("Mean tvec contains NaN values")

    logger.debug(f"Mean rvec: {rvec}, mean tvec: {tvec}")

    return make_M(rvec, tvec)


def mean_transform_robust(
        M_list: list[np.ndarray],
        approx: np.ndarray | None = None,
        error: float = 0.3,
        max_iterations: int = 5,
        convergence_threshold: float = 0.01
) -> np.ndarray:
    """
    Compute robust mean by iteratively filtering outliers.

    Args:
        M_list: List of transformation matrices
        approx: Initial approximation for comparison
        error: Maximum acceptable rotation error
        max_iterations: Maximum refinement iterations
        convergence_threshold: Stop if change is below this threshold

    Returns:
        Robust mean transformation
    """
    if len(M_list) == 0:
        raise ValueError("Cannot compute robust mean from empty matrix list")

    if approx is None:
        logger.debug("No approximation provided, using all matrices")
        return mean_transform(M_list)

    logger.debug(f"Filtering matrices with error threshold {error}")
    M_current = approx

    for iteration in range(max_iterations):
        M_list_robust = []
        errors = []

        for i, M in enumerate(M_list):
            rot_error = (M - M_current)[:3, :3]
            m = np.max(np.abs(rot_error))
            errors.append(m)

            if m < error:
                M_list_robust.append(M)

        logger.info(f"Iteration {iteration + 1}: Kept {len(M_list_robust)}/{len(M_list)} matrices")

        if len(errors) > 0:
            logger.debug(f"Error statistics: min={min(errors):.6f}, max={max(errors):.6f}, mean={np.mean(errors):.6f}")

        # CRITICAL: If all matrices filtered out, use relaxed threshold
        if len(M_list_robust) == 0:
            logger.warning(f"All matrices filtered with threshold {error}. Relaxing to use best 50%")
            # Use top 50% of matrices by error
            sorted_indices = np.argsort(errors)
            n_keep = max(len(M_list) // 2, 3)  # Keep at least 3 or 50%
            M_list_robust = [M_list[i] for i in sorted_indices[:n_keep]]
            logger.info(f"Using {len(M_list_robust)} best matrices after relaxation")

        # Compute new mean
        M_new = mean_transform(M_list_robust)

        # Check convergence
        diff = np.max(np.abs(M_new - M_current))
        logger.debug(f"Transform difference: {diff:.6f}")

        if diff < convergence_threshold or iteration == max_iterations - 1:
            logger.info(f"Converged after {iteration + 1} iterations (diff={diff:.6f})")
            return M_new

        M_current = M_new

    logger.warning(f"Did not converge after {max_iterations} iterations. Using last result.")
    return M_current


def get_initial_extrinsics(rtvecs: np.ndarray, cam_names: list | None = None) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute initial camera extrinsics from pose observations.

    Args:
        rtvecs: Array of rotation/translation vectors (n_cams, n_frames, 6)
        cam_names: Optional camera names for logging

    Returns:
        Tuple of (rvecs, tvecs) for all cameras
    """
    n_cams = rtvecs.shape[0]
    n_frames = rtvecs.shape[1]

    logger.info(f"Computing initial extrinsics for {n_cams} cameras from {n_frames} frames")

    # Log observation statistics
    for cam_idx in range(n_cams):
        valid_obs = np.sum(~np.isnan(rtvecs[cam_idx, :, 0]))
        cam_name = cam_names[cam_idx] if cam_names else str(cam_idx)
        logger.info(f"Camera {cam_name}: {valid_obs}/{n_frames} valid observations ({100 * valid_obs / n_frames:.1f}%)")

    logger.debug("Building calibration graph from camera connections")
    graph = get_calibration_graph(rtvecs, cam_names)
    logger.info(f"Calibration graph: {dict(graph)}")

    logger.debug("Finding calibration pairs")
    pairs = find_calibration_pairs(graph, source=0)
    logger.info(f"Calibration pairs: {pairs}")

    if len(pairs) != n_cams - 1:
        logger.error(f"Expected {n_cams - 1} pairs, got {len(pairs)}. Graph may be disconnected!")

    logger.debug("Computing camera transformation matrices")
    extrinsics = compute_camera_matrices(rtvecs, pairs)

    # Extract rvecs and tvecs
    rvecs = []
    tvecs = []
    for cnum in range(n_cams):
        cam_name = cam_names[cnum] if cam_names else str(cnum)

        if cnum not in extrinsics:
            logger.error(f"Camera {cam_name} (index {cnum}) not in extrinsics dict!")
            raise ValueError(f"Missing extrinsics for camera {cnum}")

        try:
            rvec, tvec = get_rtvec(extrinsics[cnum])
            logger.debug(f"Camera {cam_name}: rvec={rvec}, tvec={tvec}")
            rvecs.append(rvec)
            tvecs.append(tvec)
        except Exception as e:
            logger.error(f"Camera {cam_name}: Failed to extract rvec/tvec - {e}")
            raise

    rvecs = np.array(rvecs)
    tvecs = np.array(tvecs)

    logger.info(f"Successfully computed extrinsics: rvecs shape={rvecs.shape}, tvecs shape={tvecs.shape}")

    # Log summary statistics
    rvec_norms = np.linalg.norm(rvecs, axis=1)
    tvec_norms = np.linalg.norm(tvecs, axis=1)
    logger.info(f"Rotation magnitudes: {rvec_norms}")
    logger.info(f"Translation magnitudes: {tvec_norms}")

    return rvecs, tvecs


class Camera:
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

    def get_dict(self):
        return {
            "name": self.get_name(),
            "size": list(self.get_size()),
            "matrix": self.get_camera_matrix().tolist(),
            "distortions": self.get_distortions().tolist(),
            "rotation": self.get_rotation().tolist(),
            "translation": self.get_translation().tolist(),
            "world_orientation": self.get_world_orientation().tolist(),
            "world_position": self.get_world_position().tolist()
        }

    def load_dict(self, d):
        self.set_camera_matrix(d["matrix"])
        self.set_rotation(d["rotation"])
        self.set_translation(d["translation"])
        self.set_distortions(d["distortions"])
        self.set_name(d["name"])
        self.set_size(d["size"])

        self.set_world_orientation(d.get("world_orientation", np.eye(3)))
        self.set_world_position(d.get("world_position", np.zeros(3)))

    def from_dict(d):
        cam = Camera()
        cam.load_dict(d)
        return cam

    def get_camera_matrix(self):
        return self.matrix

    def get_distortions(self):
        return self.dist

    def set_camera_matrix(self, matrix):
        self.matrix = np.array(matrix, dtype="float64")

    def set_focal_length(self, fx, fy=None):
        if fy is None:
            fy = fx
        self.matrix[0, 0] = fx
        self.matrix[1, 1] = fy

    def get_focal_length(self, both=False):
        fx = self.matrix[0, 0]
        fy = self.matrix[1, 1]
        if both:
            return (fx, fy)
        else:
            return (fx + fy) / 2.0

    def set_distortions(self, dist):
        self.dist = np.array(dist, dtype="float64").ravel()

    def set_rotation(self, rvec):
        self.rvec = np.array(rvec, dtype="float64").ravel()

    def get_rotation(self):
        return self.rvec

    def set_translation(self, tvec):
        self.tvec = np.array(tvec, dtype="float64").ravel()

    def get_translation(self):
        return self.tvec

    def set_world_orientation(self, world_orientation):
        self.world_orientation = np.asarray(world_orientation, dtype="float64").reshape(3, 3)

    def get_world_orientation(self):
        return self.world_orientation

    def set_world_position(self, world_position):
        self.world_position = np.array(world_position, dtype="float64").ravel()

    def get_world_position(self):
        return self.world_position

    def get_extrinsics_mat(self):
        return make_M(self.rvec, self.tvec)

    def get_name(self):
        return self.name

    def set_name(self, name):
        self.name = str(name)

    def set_size(self, size):
        """set size as (width, height)"""
        self.size = size

    def get_size(self):
        """get size as (width, height)"""
        return self.size

    def resize_camera(self, scale):
        """resize the camera by scale factor, updating intrinsics to match"""
        size = self.get_size()
        new_size = size[0] * scale, size[1] * scale
        matrix = self.get_camera_matrix()
        new_matrix = matrix * scale
        new_matrix[2, 2] = 1
        self.set_size(new_size)
        self.set_camera_matrix(new_matrix)

    def get_params(self):
        params = np.zeros(8 + self.extra_dist, dtype="float64")
        params[0:3] = self.get_rotation()
        params[3:6] = self.get_translation()
        params[6] = self.get_focal_length()
        dist = self.get_distortions()
        params[7] = dist[0]
        if self.extra_dist:
            params[8] = dist[1]
        return params

    def set_params(self, params):
        self.set_rotation(params[0:3])
        self.set_translation(params[3:6])
        self.set_focal_length(params[6])

        dist = np.zeros(5, dtype="float64")
        dist[0] = params[7]
        if self.extra_dist:
            dist[1] = params[8]
        self.set_distortions(dist)

    def distort_points(self, points):
        shape = points.shape
        points = points.reshape(-1, 1, 2)
        new_points = np.dstack([points, np.ones((points.shape[0], 1, 1))])
        out, _ = cv2.projectPoints(
            new_points,
            np.zeros(3),
            np.zeros(3),
            self.matrix.astype("float64"),
            self.dist.astype("float64"),
        )
        return out.reshape(shape)

    def undistort_points(self, points):
        shape = points.shape
        points = points.reshape(-1, 1, 2)
        out = cv2.undistortPoints(points, self.matrix.astype("float64"), self.dist.astype("float64"))
        return out.reshape(shape)

    def project(self, points):
        points = points.reshape(-1, 1, 3)
        out, _ = cv2.projectPoints(
            points,
            self.rvec,
            self.tvec,
            self.matrix.astype("float64"),
            self.dist.astype("float64"),
        )
        return out

    def single_camera_reprojection_error(self, p3d, p2d):
        projecting_3d_points_onto_2d_image_plane_og = self.project(p3d)
        projecting_3d_points_onto_2d_image_plane = projecting_3d_points_onto_2d_image_plane_og.reshape(p2d.shape)
        return p2d - projecting_3d_points_onto_2d_image_plane

    def copy(self):
        return Camera(
            matrix=self.get_camera_matrix().copy(),
            dist=self.get_distortions().copy(),
            size=self.get_size(),
            rvec=self.get_rotation().copy(),
            tvec=self.get_translation().copy(),
            name=self.get_name(),
            extra_dist=self.extra_dist,
            world_orientation=self.get_world_orientation().copy(),
            world_position=self.get_world_position().copy()
        )


class FisheyeCamera(Camera):
    def __init__(
            self,
            matrix=np.eye(3),
            dist=np.zeros(4),
            size=None,
            rvec=np.zeros(3),
            tvec=np.zeros(3),
            name=None,
            extra_dist=False,
    ):
        self.set_camera_matrix(matrix)
        self.set_distortions(dist)
        self.set_size(size)
        self.set_rotation(rvec)
        self.set_translation(tvec)
        self.set_name(name)
        self.extra_dist = extra_dist

    def from_dict(d):
        cam = FisheyeCamera()
        cam.load_dict(d)
        return cam

    def get_dict(self):
        d = super().get_dict()
        d["fisheye"] = True
        return d

    def distort_points(self, points):
        shape = points.shape
        points = points.reshape(-1, 1, 2)
        new_points = np.dstack([points, np.ones((points.shape[0], 1, 1))])
        out, _ = cv2.fisheye.projectPoints(
            new_points,
            np.zeros(3),
            np.zeros(3),
            self.matrix.astype("float64"),
            self.dist.astype("float64"),
        )
        return out.reshape(shape)

    def undistort_points(self, points):
        shape = points.shape
        points = points.reshape(-1, 1, 2)
        out = cv2.fisheye.undistortPoints(
            points.astype("float64"),
            self.matrix.astype("float64"),
            self.dist.astype("float64"),
        )
        return out.reshape(shape)

    def project(self, points):
        points = points.reshape(-1, 1, 3)
        out, _ = cv2.fisheye.projectPoints(
            points,
            self.rvec,
            self.tvec,
            self.matrix.astype("float64"),
            self.dist.astype("float64"),
        )
        return out

    def set_params(self, params):
        self.set_rotation(params[0:3])
        self.set_translation(params[3:6])
        self.set_focal_length(params[6])

        dist = np.zeros(4, dtype="float64")
        dist[0] = params[7]
        if self.extra_dist:
            dist[1] = params[8]
        # dist[2] = params[9]
        # dist[3] = params[10]
        self.set_distortions(dist)

    def get_params(self):
        params = np.zeros(8 + self.extra_dist, dtype="float64")
        params[0:3] = self.get_rotation()
        params[3:6] = self.get_translation()
        params[6] = self.get_focal_length()
        dist = self.get_distortions()
        params[7] = dist[0]
        if self.extra_dist:
            params[8] = dist[1]
        # params[9] = dist[2]
        # params[10] = dist[3]
        return params

    def copy(self):
        return FisheyeCamera(
            matrix=self.get_camera_matrix().copy(),
            dist=self.get_distortions().copy(),
            size=self.get_size(),
            rvec=self.get_rotation().copy(),
            tvec=self.get_translation().copy(),
            name=self.get_name(),
            extra_dist=self.extra_dist,
        )


class AniposeCameraGroup:
    def __init__(self, cameras, metadata={}):
        self.cameras = cameras
        self.metadata = metadata
        self.charuco_2d_data = None

    def subset_cameras(self, indices):
        cams = [self.cameras[ix].copy() for ix in indices]
        return AniposeCameraGroup(cams, self.metadata)

    def subset_cameras_names(self, names):
        cur_names = self.get_names()
        cur_names_dict = dict(zip(cur_names, range(len(cur_names))))
        indices = []
        for name in names:
            if name not in cur_names_dict:
                raise IndexError("name {} not part of camera names: {}".format(name, cur_names))
            indices.append(cur_names_dict[name])
        return self.subset_cameras(indices)

    def project(self, points):
        """Given an Nx3 array of points, this returns an CxNx2 array of 2D points,
        where C is the number of cameras"""
        points = points.reshape(-1, 1, 3)
        n_points = points.shape[0]
        n_cams = len(self.cameras)

        out = np.empty((n_cams, n_points, 2), dtype="float64")
        for cnum, cam in enumerate(self.cameras):
            out[cnum] = cam.project(points).reshape(n_points, 2)

        return out

    def triangulate(self, points, undistort=True, progress=False, kill_event: multiprocessing.Event = None):
        """Given an CxNx2 array, this returns an Nx3 array of points,
        where N is the number of points and C is the number of cameras"""

        assert points.shape[0] == len(
            self.cameras
        ), "Invalid points shape, first dim should be equal to" " number of cameras ({}), but shape is {}".format(
            len(self.cameras), points.shape
        )

        one_point = False
        if len(points.shape) == 2:
            points = points.reshape(-1, 1, 2)
            one_point = True

        if undistort:
            new_points = np.empty(points.shape)
            for cnum, cam in enumerate(self.cameras):
                # must copy in order to satisfy opencv underneath
                sub = np.copy(points[cnum])
                new_points[cnum] = cam.undistort_points(sub)
            points = new_points

        n_cams, n_points, _ = points.shape

        out = np.empty((n_points, 3))
        out[:] = np.nan

        cam_mats = np.array([cam.get_extrinsics_mat() for cam in self.cameras])

        if progress:
            iterator = trange(n_points, ncols=70)
        else:
            iterator = range(n_points)

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

    def triangulate_possible(
            self,
            points,
            undistort=True,
            min_cams=2,
            progress=False,
            threshold=0.5,
            kill_event: multiprocessing.Event = None,
    ):
        """Given an CxNxPx2 array, this returns an Nx3 array of points
        by triangulating all possible points and picking the ones with
        best reprojection error
        where:
        C: number of cameras
        N: number of points
        P: number of possible options per point
        """

        assert points.shape[0] == len(
            self.cameras
        ), "Invalid points shape, first dim should be equal to" " number of cameras ({}), but shape is {}".format(
            len(self.cameras), points.shape
        )

        n_cams, n_points, n_possible, _ = points.shape

        cam_nums, point_nums, possible_nums = np.where(~np.isnan(points[:, :, :, 0]))

        all_iters = defaultdict(dict)

        for cam_num, point_num, possible_num in zip(cam_nums, point_nums, possible_nums):
            if cam_num not in all_iters[point_num]:
                all_iters[point_num][cam_num] = []
            all_iters[point_num][cam_num].append((cam_num, possible_num))

        for point_num in all_iters.keys():
            for cam_num in all_iters[point_num].keys():
                all_iters[point_num][cam_num].append(None)

        out = np.full((n_points, 3), np.nan, dtype="float64")
        picked_vals = np.zeros((n_cams, n_points, n_possible), dtype="bool")
        errors = np.zeros(n_points, dtype="float64")
        points_2d = np.full((n_cams, n_points, 2), np.nan, dtype="float64")

        if progress:
            iterator = trange(n_points, ncols=70)
        else:
            iterator = range(n_points)

        for point_ix in iterator:
            best_point = None
            best_error = 200

            n_cams_max = len(all_iters[point_ix])

            for picked in itertools.product(*all_iters[point_ix].values()):
                picked = [p for p in picked if p is not None]
                if len(picked) < min_cams and len(picked) != n_cams_max:
                    continue

                if kill_event is not None and kill_event.is_set():
                    return None

                cnums = [p[0] for p in picked]
                xnums = [p[1] for p in picked]

                pts = points[cnums, point_ix, xnums]
                cc = self.subset_cameras(cnums)

                p3d = cc.triangulate(pts, undistort=undistort)
                err = cc.reprojection_error(p3d, pts, mean=True)

                if err < best_error:
                    best_point = {
                        "error": err,
                        "point": p3d[:3],
                        "points": pts,
                        "picked": picked,
                        "joint_ix": point_ix,
                    }
                    best_error = err
                    if best_error < threshold:
                        break

            if best_point is not None:
                out[point_ix] = best_point["point"]
                picked = best_point["picked"]
                cnums = [p[0] for p in picked]
                xnums = [p[1] for p in picked]
                picked_vals[cnums, point_ix, xnums] = True
                errors[point_ix] = best_point["error"]
                points_2d[cnums, point_ix] = best_point["points"]

        # return out, picked_vals, points_2d, errors #original code from OG anipose
        return out  # simplify output so that `triangulate_ransac` can be used exactly the same way as `triangulate`

    def triangulate_ransac(
            self, points, undistort=True, min_cams=2, progress=False, kill_event: multiprocessing.Event = None
    ):
        """Given an CxNx2 array, this returns an Nx3 array of points,
        where N is the number of points and C is the number of cameras"""

        assert points.shape[0] == len(
            self.cameras
        ), "Invalid points shape, first dim should be equal to" " number of cameras ({}), but shape is {}".format(
            len(self.cameras), points.shape
        )

        n_cams, n_points, _ = points.shape

        points_ransac = points.reshape(n_cams, n_points, 1, 2)

        return self.triangulate_possible(
            points_ransac, undistort=undistort, min_cams=min_cams, progress=progress, kill_event=kill_event
        )

    @jit(parallel=True, forceobj=True)
    def reprojection_error(self, points_3d, points_2d, mean=False):
        """Given an Nx3 array of 3D points and an CxNx2 array of 2D points,
        where N is the number of points and C is the number of cameras,
        this returns an CxNx2 array of errors.
        Optionally mean=True, this averages the errors and returns array of length N of errors"""

        one_point = False
        if len(points_3d.shape) == 1 and len(points_2d.shape) == 2:
            points_3d = points_3d.reshape(1, 3)
            points_2d = points_2d.reshape(-1, 1, 2)
            one_point = True

        n_cams, n_points, _ = points_2d.shape
        assert points_3d.shape == (
            n_points,
            3,
        ), "shapes of 2D and 3D points are not consistent: " "2D={}, 3D={}".format(points_2d.shape, points_3d.shape)

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
            if mean:
                errors = float(errors[0])
            else:
                errors = errors.reshape(-1, 2)

        return errors

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
    ):
        """Given an CxNx2 array of 2D points,
        where N is the number of points and C is the number of cameras,
        this performs iterative bundle adjustsment to fine-tune the parameters of the cameras.
        That is, it performs bundle adjustment multiple times, adjusting the weights given to points
        to reduce the influence of outliers.
        This is inspired by the algorithm for Fast Global Registration by Zhou, Park, and Koltun
        """
        error_list = []

        assert p2ds.shape[0] == len(
            self.cameras
        ), "Invalid points shape, first dim should be equal to" " number of cameras ({}), but shape is {}".format(
            len(self.cameras), p2ds.shape
        )

        p2ds_full = p2ds
        extra_full = extra

        p2ds, extra = resample_points(p2ds_full, extra_full, n_samp=n_samp_full)
        error = self.average_error(p2ds, median=True)

        if verbose:
            print("error: ", error)

        mus = np.exp(np.linspace(np.log(start_mu), np.log(end_mu), num=n_iters))

        if verbose:
            print("n_samples: {}".format(n_samp_iter))

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
                print(f"previous error scores: [magenta] {error_list}[/magenta]")

            self.bundle_adjust(
                p2ds_samp,
                extra_samp,
                loss="linear",
                ftol=ftol,
                max_nfev=max_nfev,
                verbose=verbose,
            )

        p2ds, extra = resample_points(p2ds_full, extra_full, n_samp=n_samp_full)
        p3ds = self.triangulate(p2ds)
        errors_full = self.reprojection_error(p3ds, p2ds, mean=False)
        errors_norm = self.reprojection_error(p3ds, p2ds, mean=True)
        error_dict = get_error_dict(errors_full)
        if verbose:
            print(error_dict)

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
            p2ds[:, good],
            extra_good,
            loss="linear",
            ftol=ftol,
            max_nfev=max(200, max_nfev),
            verbose=verbose,
        )

        error = self.average_error(p2ds, median=True)

        p3ds = self.triangulate(p2ds)
        errors_full = self.reprojection_error(p3ds, p2ds, mean=False)
        error_dict = get_error_dict(errors_full)
        if verbose:
            print(error_dict)

        if verbose:
            print("error: ", error)

        return error

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
    ):
        """Given an CxNx2 array of 2D points,
        where N is the number of points and C is the number of cameras,
        this performs bundle adjustsment to fine-tune the parameters of the cameras"""

        assert p2ds.shape[0] == len(
            self.cameras
        ), "Invalid points shape, first dim should be equal to" " number of cameras ({}), but shape is {}".format(
            len(self.cameras), p2ds.shape
        )

        if extra is not None:
            extra["ids_map"] = remap_ids(extra["ids"])

        x0, n_cam_params = self._initialize_params_bundle(p2ds, extra)

        if start_params is not None:
            x0 = start_params
            n_cam_params = len(self.cameras[0].get_params())

        error_fun = self._error_fun_bundle

        jac_sparse = self._jac_sparsity_bundle(p2ds, n_cam_params, extra)

        f_scale = threshold
        opt = optimize.least_squares(
            error_fun,
            x0,
            jac_sparsity=jac_sparse,
            f_scale=f_scale,
            x_scale="jac",
            loss=loss,
            ftol=ftol,
            method="trf",
            tr_solver="lsmr",
            verbose=2 * verbose,
            max_nfev=max_nfev,
            args=(p2ds, n_cam_params, extra),
        )
        best_params = opt.x

        for i, cam in enumerate(self.cameras):
            a = i * n_cam_params
            b = (i + 1) * n_cam_params
            cam.set_params(best_params[a:b])

        error = self.average_error(p2ds)
        return error

    @jit(parallel=True, forceobj=True)
    def _error_fun_bundle(self, params, p2ds, n_cam_params, extra):
        """Error function for bundle adjustment"""
        good = ~np.isnan(p2ds)
        n_cams = len(self.cameras)

        for i in range(n_cams):
            cam = self.cameras[i]
            a = i * n_cam_params
            b = (i + 1) * n_cam_params
            cam.set_params(params[a:b])

        n_cams = len(self.cameras)
        sub = n_cam_params * n_cams
        n3d = p2ds.shape[1] * 3
        p3ds_test = params[sub: sub + n3d].reshape(-1, 3)
        errors = self.reprojection_error(p3ds_test, p2ds)
        errors_reproj = errors[good]

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
        """Given an CxNx2 array of 2D points,
        where N is the number of points and C is the number of cameras,
        compute the sparsity structure of the jacobian for bundle adjustment"""

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
            total_board_params = n_boards * (3 + 3)  # rvecs + tvecs
        else:
            n_boards = 0
            total_board_params = 0

        n_cams = p2ds.shape[0]
        n_points = p2ds.shape[1]
        total_params_reproj = n_cams * n_cam_params + n_points * 3
        n_params = total_params_reproj + total_board_params

        n_good_values = np.sum(good)
        if extra is not None:
            n_errors = n_good_values + n_points * 3
        else:
            n_errors = n_good_values

        A_sparse = dok_matrix((n_errors, n_params), dtype="int16")

        cam_indices_good = cam_indices[good]
        point_indices_good = point_indices[good]

        # -- reprojection error --
        ix = np.arange(n_good_values)

        ## update camera params based on point error
        for i in range(n_cam_params):
            A_sparse[ix, cam_indices_good * n_cam_params + i] = 1

        ## update point position based on point error
        for i in range(3):
            A_sparse[ix, n_cams * n_cam_params + point_indices_good * 3 + i] = 1

        # -- match for the object points--
        if extra is not None:
            point_ix = np.arange(n_points)

            ## update all the camera parameters
            # A_sparse[n_good_values:n_good_values+n_points*3,
            #          0:n_cams*n_cam_params] = 1

            ## update board rotation and translation based on error from expected
            for i in range(3):
                for j in range(3):
                    A_sparse[
                        n_good_values + point_ix * 3 + i,
                        total_params_reproj + ids * 3 + j,
                    ] = 1
                    A_sparse[
                        n_good_values + point_ix * 3 + i,
                        total_params_reproj + n_boards * 3 + ids * 3 + j,
                    ] = 1

            ## update point position based on error from expected
            for i in range(3):
                A_sparse[
                    n_good_values + point_ix * 3 + i,
                    n_cams * n_cam_params + point_ix * 3 + i,
                ] = 1

        return A_sparse

    def _initialize_params_bundle(self, p2ds, extra):
        """Given an CxNx2 array of 2D points,
        where N is the number of points and C is the number of cameras,
        initializes the parameters for bundle adjustment"""

        cam_params = np.hstack([cam.get_params() for cam in self.cameras])
        n_cam_params = len(cam_params) // len(self.cameras)

        total_cam_params = len(cam_params)

        n_cams, n_points, _ = p2ds.shape
        assert n_cams == len(self.cameras), (
            "number of cameras in CameraGroup does not " "match number of cameras in 2D points given"
        )

        p3ds = self.triangulate(p2ds)

        if extra is not None:
            ids = extra["ids_map"]
            n_boards = int(np.max(ids[~np.isnan(ids)])) + 1
            total_board_params = n_boards * (3 + 3)  # rvecs + tvecs

            # initialize to 0
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
                    M_board = np.matmul(inverse(M_cam), M_board_cam)
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

    def optim_points(
            self,
            points,
            p3ds,
            constraints=[],
            constraints_weak=[],
            scale_smooth=4,
            scale_length=2,
            scale_length_weak=0.5,
            reproj_error_threshold=15,
            reproj_loss="soft_l1",
            n_deriv_smooth=1,
            scores=None,
            verbose=False,
    ):
        """
        Take in an array of 2D points of shape CxNxJx2,
        an array of 3D points of shape NxJx3,
        and an array of constraints of shape Kx2, where
        C: number of camera
        N: number of frames
        J: number of joints
        K: number of constraints

        This function creates an optimized array of 3D points of shape NxJx3.

        Example constraints:
        constraints = [[0, 1], [1, 2], [2, 3]]
        (meaning that lengths of segments 0->1, 1->2, 2->3 are all constant)

        """
        assert points.shape[0] == len(
            self.cameras
        ), "Invalid points shape, first dim should be equal to" " number of cameras ({}), but shape is {}".format(
            len(self.cameras), points.shape
        )

        n_cams, n_frames, n_joints, _ = points.shape
        constraints = np.array(constraints)
        constraints_weak = np.array(constraints_weak)

        p3ds_intp = np.apply_along_axis(interpolate_data, 0, p3ds)

        p3ds_med = np.apply_along_axis(medfilt_data, 0, p3ds_intp, size=7)

        default_smooth = 1.0 / np.mean(np.abs(np.diff(p3ds_med, axis=0)))
        scale_smooth_full = scale_smooth * default_smooth

        t1 = time.time()

        x0 = self._initialize_params_triangulation(p3ds_intp, constraints, constraints_weak)

        x0[~np.isfinite(x0)] = 0

        jac = self._jac_sparsity_triangulation(points, constraints, constraints_weak, n_deriv_smooth)

        opt2 = optimize.least_squares(
            self._error_fun_triangulation,
            x0=x0,
            jac_sparsity=jac,
            loss="linear",
            ftol=1e-3,
            verbose=2 * verbose,
            args=(
                points,
                constraints,
                constraints_weak,
                scores,
                scale_smooth_full,
                scale_length,
                scale_length_weak,
                reproj_error_threshold,
                reproj_loss,
                n_deriv_smooth,
            ),
        )

        p3ds_new2 = opt2.x[: p3ds.size].reshape(p3ds.shape)

        t2 = time.time()

        if verbose:
            print("optimization took {:.2f} seconds".format(t2 - t1))

        return p3ds_new2

    def optim_points_possible(
            self,
            points,
            p3ds,
            constraints=[],
            constraints_weak=[],
            scale_smooth=4,
            scale_length=2,
            scale_length_weak=0.5,
            reproj_error_threshold=15,
            reproj_loss="soft_l1",
            n_deriv_smooth=1,
            scores=None,
            verbose=False,
    ):
        """
        Take in an array of 2D points of shape CxNxJxPx2,
        an array of 3D points of shape NxJx3,
        and an array of constraints of shape Kx2, where
        C: number of camera
        N: number of frames
        J: number of joints
        P: number of possible options per point
        K: number of constraints

        This function creates an optimized array of 3D points of shape NxJx3.

        Example constraints:
        constraints = [[0, 1], [1, 2], [2, 3]]
        (meaning that lengths of segments 0->1, 1->2, 2->3 are all constant)

        """
        assert points.shape[0] == len(
            self.cameras
        ), "Invalid points shape, first dim should be equal to" " number of cameras ({}), but shape is {}".format(
            len(self.cameras), points.shape
        )

        n_cams, n_frames, n_joints, n_possible, _ = points.shape
        constraints = np.array(constraints)
        constraints_weak = np.array(constraints_weak)

        p3ds_intp = np.apply_along_axis(interpolate_data, 0, p3ds)

        p3ds_med = np.apply_along_axis(medfilt_data, 0, p3ds_intp, size=7)

        default_smooth = 1.0 / np.mean(np.abs(np.diff(p3ds_med, axis=0)))
        scale_smooth_full = scale_smooth * default_smooth

        t1 = time.time()

        x0 = self._initialize_params_triangulation_possible(
            p3ds_intp,
            points,
            constraints=constraints,
            constraints_weak=constraints_weak,
        )

        print("getting jacobian...")
        jac = self._jac_sparsity_triangulation_possible(
            points,
            constraints=constraints,
            constraints_weak=constraints_weak,
            n_deriv_smooth=n_deriv_smooth,
        )

        beta = 5

        print("starting optimization...")
        opt2 = optimize.least_squares(
            self._error_fun_triangulation_possible,
            x0=x0,
            jac_sparsity=jac,
            loss="linear",
            ftol=1e-3,
            verbose=2 * verbose,
            args=(
                points,
                beta,
                constraints,
                constraints_weak,
                scores,
                scale_smooth_full,
                scale_length,
                scale_length_weak,
                reproj_error_threshold,
                reproj_loss,
                n_deriv_smooth,
            ),
        )
        params = opt2.x

        p3ds_new2 = params[: p3ds.size].reshape(p3ds.shape)

        bad = np.isnan(points[:, :, :, :, 0])
        all_bad = np.all(bad, axis=3)

        n_params_norm = p3ds.size + len(constraints) + len(constraints_weak)

        alphas = np.zeros((n_cams, n_frames, n_joints, n_possible), dtype="float64")
        alphas[~bad] = params[n_params_norm:]

        alphas_exp = np.exp(beta * alphas)
        alphas_exp[bad] = 0
        alphas_sum = np.sum(alphas_exp, axis=3)
        alphas_sum[all_bad] = 1
        alphas_norm = alphas_exp / alphas_sum[:, :, :, None]
        alphas_norm[bad] = np.nan

        t2 = time.time()

        if verbose:
            print("optimization took {:.2f} seconds".format(t2 - t1))

        return p3ds_new2, alphas_norm

    def triangulate_optim(self, points, init_ransac=False, init_progress=False, **kwargs):
        """
        Take in an array of 2D points of shape CxNxJx2, and an array of constraints of shape Kx2, where
        C: number of camera
        N: number of frames
        J: number of joints
        K: number of constraints

        This function creates an optimized array of 3D points of shape NxJx3.

        Example constraints:
        constraints = [[0, 1], [1, 2], [2, 3]]
        (meaning that lengths of segments 0->1, 1->2, 2->3 are all constant)

        """

        assert points.shape[0] == len(
            self.cameras
        ), "Invalid points shape, first dim should be equal to" " number of cameras ({}), but shape is {}".format(
            len(self.cameras), points.shape
        )

        n_cams, n_frames, n_joints, _ = points.shape
        # constraints = np.array(constraints)
        # constraints_weak = np.array(constraints_weak)

        points_shaped = points.reshape(n_cams, n_frames * n_joints, 2)
        if init_ransac:
            p3ds, picked, p2ds, errors = self.triangulate_ransac(points_shaped, progress=init_progress)
            points = p2ds.reshape(points.shape)
        else:
            p3ds = self.triangulate(points_shaped, progress=init_progress)
        p3ds = p3ds.reshape((n_frames, n_joints, 3))

        c = np.isfinite(p3ds[:, :, 0])
        if np.sum(c) < 20:
            print("warning: not enough 3D points to calculate_center_of_mass optimization")
            return p3ds

        return self.optim_points(points, p3ds, **kwargs)

    @jit(forceobj=True, parallel=True)
    def _error_fun_triangulation(
            self,
            params,
            p2ds,
            constraints=[],
            constraints_weak=[],
            scores=None,
            scale_smooth=10000,
            scale_length=1,
            scale_length_weak=0.2,
            reproj_error_threshold=100,
            reproj_loss="soft_l1",
            n_deriv_smooth=1,
    ):
        n_cams, n_frames, n_joints, _ = p2ds.shape

        n_3d = n_frames * n_joints * 3
        n_constraints = len(constraints)
        n_constraints_weak = len(constraints_weak)

        # load params
        p3ds = params[:n_3d].reshape((n_frames, n_joints, 3))
        joint_lengths = np.array(params[n_3d: n_3d + n_constraints])
        joint_lengths_weak = np.array(params[n_3d + n_constraints:])

        # reprojection errors
        p3ds_flat = p3ds.reshape(-1, 3)
        p2ds_flat = p2ds.reshape((n_cams, -1, 2))
        errors = self.reprojection_error(p3ds_flat, p2ds_flat)
        if scores is not None:
            scores_flat = scores.reshape((n_cams, -1))
            errors = errors * scores_flat[:, :, None]
        errors_reproj = errors[~np.isnan(p2ds_flat)]

        rp = reproj_error_threshold
        errors_reproj = np.abs(errors_reproj)
        if reproj_loss == "huber":
            bad = errors_reproj > rp
            errors_reproj[bad] = rp * (2 * np.sqrt(errors_reproj[bad] / rp) - 1)
        elif reproj_loss == "linear":
            pass
        elif reproj_loss == "soft_l1":
            errors_reproj = rp * 2 * (np.sqrt(1 + errors_reproj / rp) - 1)

        # temporal constraint
        errors_smooth = np.diff(p3ds, n=n_deriv_smooth, axis=0).ravel() * scale_smooth

        # joint length constraint
        errors_lengths = np.empty((n_constraints, n_frames), dtype="float64")
        for cix, (a, b) in enumerate(constraints):
            lengths = np.linalg.norm(p3ds[:, a] - p3ds[:, b], axis=1)
            expected = joint_lengths[cix]
            errors_lengths[cix] = 100 * (lengths - expected) / expected
        errors_lengths = errors_lengths.ravel() * scale_length

        errors_lengths_weak = np.empty((n_constraints_weak, n_frames), dtype="float64")
        for cix, (a, b) in enumerate(constraints_weak):
            lengths = np.linalg.norm(p3ds[:, a] - p3ds[:, b], axis=1)
            expected = joint_lengths_weak[cix]
            errors_lengths_weak[cix] = 100 * (lengths - expected) / expected
        errors_lengths_weak = errors_lengths_weak.ravel() * scale_length_weak

        return np.hstack([errors_reproj, errors_smooth, errors_lengths, errors_lengths_weak])

    def _error_fun_triangulation_possible(self, params, p2ds, beta=2, constraints=[], constraints_weak=[], *args):
        # extract alphas from end of params
        # soft argmax for picking the appropriate points from p2ds
        # pass the points to error_fun_triangulate_possible for residuals
        # add errors to keep the alphas in check
        # return all the errors

        n_cams, n_frames, n_joints, n_possible, _ = p2ds.shape

        n_3d = n_frames * n_joints * 3
        n_constraints = len(constraints)
        n_constraints_weak = len(constraints_weak)
        n_params_norm = n_3d + n_constraints + n_constraints_weak

        # load params
        bad = np.isnan(p2ds[:, :, :, :, 0])
        all_bad = np.all(bad, axis=3)

        alphas = np.zeros((n_cams, n_frames, n_joints, n_possible), dtype="float64")
        alphas[~bad] = params[n_params_norm:]
        params_rest = np.array(params[:n_params_norm])

        # get normalized alphas
        alphas_exp = np.exp(beta * alphas)
        alphas_exp[bad] = 0
        alphas_sum = np.sum(alphas_exp, axis=3)
        alphas_sum[all_bad] = 1
        alphas_norm = alphas_exp / alphas_sum[:, :, :, None]

        # extract the 2D points using soft argmax
        p2ds_test = np.copy(p2ds)
        p2ds_test[bad] = 0
        p2ds_adj = np.sum(alphas_norm[:, :, :, :, None] * p2ds_test, axis=3)
        p2ds_adj[all_bad] = np.nan

        errors = self._error_fun_triangulation(params_rest, p2ds_adj, constraints, constraints_weak, *args)

        alphas_test = alphas_norm[~all_bad]
        errors_alphas = (1 - np.std(alphas_test, axis=1)) * 10

        return np.hstack([errors, errors_alphas])

    def _initialize_params_triangulation(self, p3ds, constraints=[], constraints_weak=[]):
        joint_lengths = np.empty(len(constraints), dtype="float64")
        joint_lengths_weak = np.empty(len(constraints_weak), dtype="float64")

        for cix, (a, b) in enumerate(constraints):
            lengths = np.linalg.norm(p3ds[:, a] - p3ds[:, b], axis=1)
            joint_lengths[cix] = np.median(lengths)

        for cix, (a, b) in enumerate(constraints_weak):
            lengths = np.linalg.norm(p3ds[:, a] - p3ds[:, b], axis=1)
            joint_lengths_weak[cix] = np.median(lengths)

        all_lengths = np.hstack([joint_lengths, joint_lengths_weak])
        med = np.median(all_lengths)
        if med == 0:
            med = 1e-3

        mad = np.median(np.abs(all_lengths - med))

        joint_lengths[joint_lengths == 0] = med
        joint_lengths_weak[joint_lengths_weak == 0] = med
        joint_lengths[joint_lengths > med + mad * 5] = med
        joint_lengths_weak[joint_lengths_weak > med + mad * 5] = med

        return np.hstack([p3ds.ravel(), joint_lengths, joint_lengths_weak])

    def _initialize_params_triangulation_possible(self, p3ds, p2ds, **kwargs):
        # initialize params using above function
        # initialize alphas to 1 for first one and 0 for other possible

        n_cams, n_frames, n_joints, n_possible, _ = p2ds.shape
        good = ~np.isnan(p2ds[:, :, :, :, 0])

        alphas = np.zeros((n_cams, n_frames, n_joints, n_possible), dtype="float64")
        alphas[:, :, :, 0] = 0

        params = self._initialize_params_triangulation(p3ds, **kwargs)
        params_full = np.hstack([params, alphas[good]])

        return params_full

    def _jac_sparsity_triangulation(self, p2ds, constraints=[], constraints_weak=[], n_deriv_smooth=1):
        n_cams, n_frames, n_joints, _ = p2ds.shape
        n_constraints = len(constraints)
        n_constraints_weak = len(constraints_weak)

        p2ds_flat = p2ds.reshape((n_cams, -1, 2))

        point_indices = np.zeros(p2ds_flat.shape, dtype="int32")
        for i in range(p2ds_flat.shape[1]):
            point_indices[:, i] = i

        point_indices_3d = np.arange(n_frames * n_joints).reshape((n_frames, n_joints))

        good = ~np.isnan(p2ds_flat)
        n_errors_reproj = np.sum(good)
        n_errors_smooth = (n_frames - n_deriv_smooth) * n_joints * 3
        n_errors_lengths = n_constraints * n_frames
        n_errors_lengths_weak = n_constraints_weak * n_frames

        n_errors = n_errors_reproj + n_errors_smooth + n_errors_lengths + n_errors_lengths_weak

        n_3d = n_frames * n_joints * 3
        n_params = n_3d + n_constraints + n_constraints_weak

        point_indices_good = point_indices[good]

        A_sparse = dok_matrix((n_errors, n_params), dtype="int16")

        # constraints for reprojection errors
        ix_reproj = np.arange(n_errors_reproj)
        for k in range(3):
            A_sparse[ix_reproj, point_indices_good * 3 + k] = 1

        # sparse constraints for smoothness in time
        frames = np.arange(n_frames - n_deriv_smooth)
        for j in range(n_joints):
            for n in range(n_deriv_smooth + 1):
                pa = point_indices_3d[frames, j]
                pb = point_indices_3d[frames + n, j]
                for k in range(3):
                    A_sparse[n_errors_reproj + pa * 3 + k, pb * 3 + k] = 1

        ## -- strong constraints --
        # joint lengths should change with joint lengths errors
        start = n_errors_reproj + n_errors_smooth
        frames = np.arange(n_frames)
        for cix, (a, b) in enumerate(constraints):
            A_sparse[start + cix * n_frames + frames, n_3d + cix] = 1

        # points should change accordingly to match joint lengths too
        frames = np.arange(n_frames)
        for cix, (a, b) in enumerate(constraints):
            pa = point_indices_3d[frames, a]
            pb = point_indices_3d[frames, b]
            for k in range(3):
                A_sparse[start + cix * n_frames + frames, pa * 3 + k] = 1
                A_sparse[start + cix * n_frames + frames, pb * 3 + k] = 1

        ## -- weak constraints --
        # joint lengths should change with joint lengths errors
        start = n_errors_reproj + n_errors_smooth + n_errors_lengths
        frames = np.arange(n_frames)
        for cix, (a, b) in enumerate(constraints_weak):
            A_sparse[start + cix * n_frames + frames, n_3d + n_constraints + cix] = 1

        # points should change accordingly to match joint lengths too
        frames = np.arange(n_frames)
        for cix, (a, b) in enumerate(constraints_weak):
            pa = point_indices_3d[frames, a]
            pb = point_indices_3d[frames, b]
            for k in range(3):
                A_sparse[start + cix * n_frames + frames, pa * 3 + k] = 1
                A_sparse[start + cix * n_frames + frames, pb * 3 + k] = 1

        return A_sparse

    def _jac_sparsity_triangulation_possible(self, p2ds_full, **kwargs):
        # initialize sparse jacobian using above function
        # extend to include alphas from parameters
        ## TODO: this initialization is really slow for some reason

        n_cams, n_frames, n_joints, n_possible, _ = p2ds_full.shape
        good_full = ~np.isnan(p2ds_full[:, :, :, :, 0])
        any_good = np.any(good_full, axis=3)

        n_alphas = np.sum(good_full)
        n_errors_alphas = np.sum(any_good)

        p2ds = p2ds_full[:, :, :, 0]
        A_sparse = self._jac_sparsity_triangulation(p2ds, **kwargs)

        n_errors, n_params = A_sparse.shape

        B_sparse = dok_matrix((n_errors + n_errors_alphas, n_params + n_alphas), dtype="int16")
        for r, c in zip(*A_sparse.nonzero()):
            B_sparse[r, c] = A_sparse[r, c]

        point_indices_2d = np.arange(n_cams * n_frames * n_joints).reshape(n_cams, n_frames, n_joints)
        point_indices_2d_rep = np.repeat(point_indices_2d[:, :, :, None], 2, axis=3)
        point_indices_2d_good = point_indices_2d_rep[~np.isnan(p2ds)]
        point_indices_good = point_indices_2d[any_good]

        alpha_indices = np.zeros((n_cams, n_frames, n_joints, n_possible), dtype="int64")
        for pnum in range(n_possible):
            alpha_indices[:, :, :, pnum] = point_indices_2d

        alpha_indices_good = alpha_indices[good_full]

        # alphas should change according to the reprojection error for each corresponding point
        point_indices_2d_good_find = defaultdict(list)
        for ix, p in enumerate(point_indices_2d_good):
            point_indices_2d_good_find[p].append(ix)

        for ix, alpha_index in enumerate(alpha_indices_good):
            B_sparse[point_indices_2d_good_find[alpha_index], n_params + ix] = 1

        # alphas should change according to the alpha errors
        point_indices_good_find = dict()
        for ix, p in enumerate(point_indices_good):
            point_indices_good_find[p] = ix

        for ix, alpha_index in enumerate(alpha_indices_good):
            if alpha_index in point_indices_good_find:
                err_ix = n_errors + point_indices_good_find[alpha_index]
                B_sparse[err_ix, n_params + ix] = 1

        return B_sparse

    def copy(self):
        cameras = [cam.copy() for cam in self.cameras]
        metadata = copy(self.metadata)
        return AniposeCameraGroup(cameras, metadata)

    def set_rotations(self, rvecs):
        for cam, rvec in zip(self.cameras, rvecs):
            cam.set_rotation(rvec)

    def set_translations(self, tvecs):
        for cam, tvec in zip(self.cameras, tvecs):
            cam.set_translation(tvec)

    def set_world_positions(self, positions):
        for cam, position, in zip(self.cameras, positions):
            cam.set_world_position(position)

    def set_world_orientations(self, orientations):
        for cam, orientation in zip(self.cameras, orientations):
            cam.set_world_orientation(orientation)

    def get_world_positions(self):
        return np.stack([cam.get_world_position() for cam in self.cameras])

    def get_world_orientations(self):
        return np.stack([cam.get_world_orientation() for cam in self.cameras])

    def get_rotations(self):
        rvecs = []
        for cam in self.cameras:
            rvec = cam.get_rotation()
            rvecs.append(rvec)
        return np.array(rvecs)

    def get_translations(self):
        tvecs = []
        for cam in self.cameras:
            tvec = cam.get_translation()
            tvecs.append(tvec)
        return np.array(tvecs)

    def get_names(self):
        return [cam.get_name() for cam in self.cameras]

    def set_names(self, names):
        for cam, name in zip(self.cameras, names):
            cam.set_name(name)

    def average_error(self, p2ds, median=False):
        p3ds = self.triangulate(p2ds)
        errors = self.reprojection_error(p3ds, p2ds, mean=True)
        if median:
            return np.median(errors)
        else:
            return np.mean(errors)

    def calibrate_rows(
            self,
            all_rows: list[list[dict]],
            board,
            init_intrinsics: bool = True,
            init_extrinsics: bool = True,
            verbose: bool = True,
    ) -> tuple[float, list, list]:
        """
        Calibrate cameras from charuco board observations.

        Args:
            all_rows: List of observation rows per camera
            board: Charuco board definition
            init_intrinsics: Whether to initialize camera intrinsics
            init_extrinsics: Whether to initialize camera extrinsics
            verbose: Enable verbose logging

        Returns:
            Tuple of (error, merged_rows, charuco_frame_numbers)
        """
        n_cameras = len(self.cameras)
        n_rows_list = len(all_rows)

        logger.info("=" * 80)
        logger.info("STARTING CAMERA CALIBRATION")
        logger.info("=" * 80)

        assert n_rows_list == n_cameras, \
            f"Number of camera detections ({n_rows_list}) does not match number of cameras ({n_cameras})"

        # Log observation statistics per camera
        logger.info(f"Calibrating {n_cameras} cameras")
        for cam_idx, (rows, camera) in enumerate(zip(all_rows, self.cameras)):
            logger.info(f"Camera {cam_idx} ({camera.get_name()}): {len(rows)} frames with detections")

            size = camera.get_size()
            assert size is not None, \
                f"Camera with name {camera.get_name()} has no specified frame size"
            logger.debug(f"  Camera size: {size}")

        # Initialize intrinsics
        if init_intrinsics:
            logger.info("Initializing camera intrinsics...")
            for cam_idx, (rows, camera) in enumerate(zip(all_rows, self.cameras)):
                logger.debug(f"  Camera {cam_idx}: Extracting calibration points")
                objp, imgp = board.get_all_calibration_points(rows)

                logger.debug(f"    Found {len(objp)} object point sets and {len(imgp)} image point sets")

                mixed = [(o, i) for (o, i) in zip(objp, imgp) if len(o) >= 7]

                if len(mixed) == 0:
                    logger.error(f"    Camera {cam_idx}: No valid calibration points (need at least 7 points)")
                    raise ValueError(f"No valid calibration points for camera {cam_idx}")

                logger.info(f"    Camera {cam_idx}: Using {len(mixed)} frames for intrinsics (min 7 points each)")

                objp, imgp = zip(*mixed)

                try:
                    matrix = cv2.initCameraMatrix2D(objp, imgp, tuple(camera.get_size()))
                    camera.set_camera_matrix(matrix)
                    logger.debug(f"    Camera {cam_idx}: Initialized camera matrix:\n{matrix}")
                except Exception as e:
                    logger.error(f"    Camera {cam_idx}: Failed to initialize camera matrix - {e}")
                    raise

            logger.info("✓ Camera intrinsics initialized successfully")

        # Estimate poses
        logger.info("Estimating board poses for all cameras...")
        for i, (row, cam) in enumerate(zip(all_rows, self.cameras)):
            logger.debug(f"  Camera {i}: Estimating poses for {len(row)} frames")
            all_rows[i] = board.estimate_pose_rows(cam, row)
        logger.info("✓ Board poses estimated")

        # Extract frame numbers
        charuco_frames = [f["framenum"][1] for f in all_rows[0]]
        logger.debug(f"Frame numbers from camera 0: {charuco_frames[:10]}..." if len(
            charuco_frames) > 10 else f"Frame numbers: {charuco_frames}")

        # Merge observations across cameras
        logger.info("Merging observations across cameras...")
        merged = merge_rows(all_rows)
        logger.info(f"✓ Merged {len(merged)} multi-camera observations")

        # Extract points for calibration
        logger.info("Extracting calibration points (minimum 2 cameras per point)...")
        imgp, extra = extract_points(merged, board, min_cameras=2)
        logger.info(f"✓ Extracted points: shape={imgp.shape}")
        logger.debug(f"  Extra data keys: {extra.keys() if extra else 'None'}")

        # Initialize extrinsics
        if init_extrinsics:
            logger.info("Initializing camera extrinsics...")

            logger.debug("Extracting rotation/translation vectors from observations")
            rtvecs = extract_rtvecs(merged)
            logger.info(f"  Extracted rtvecs: shape={rtvecs.shape}")

            # Log connections between cameras
            if verbose:
                logger.info("Camera pair connections (shared observations):")
                connections = get_connections(rtvecs, self.get_names())

                # Sort by camera pair for readable output
                for (cam_a, cam_b), count in sorted(connections.items()):
                    if cam_a < cam_b:  # Only show each pair once
                        logger.info(f"    {cam_a} <-> {cam_b}: {count} frames")

            logger.debug("Computing initial extrinsics from observations")
            try:
                rvecs, tvecs = get_initial_extrinsics(rtvecs, cam_names=self.get_names())
                self.set_rotations(rvecs)
                self.set_translations(tvecs)
                logger.info("✓ Initial extrinsics computed successfully")
            except Exception as e:
                logger.error(f"Failed to compute initial extrinsics: {e}")
                logger.error("This usually means insufficient shared observations between cameras")
                raise

        # Bundle adjustment
        logger.info("Starting iterative bundle adjustment...")
        logger.info(f"  Input points shape: {imgp.shape}")
        logger.info(f"  Error threshold: 1.0")

        try:
            error = self.bundle_adjust_iter(imgp, extra, verbose=verbose, error_threshold=1)
            logger.info(f"✓ Bundle adjustment completed successfully")
            logger.info(f"  Final reprojection error: {error:.4f}")
        except Exception as e:
            logger.error(f"Bundle adjustment failed: {e}")
            raise

        logger.info("=" * 80)
        logger.info(f"CALIBRATION COMPLETE - Final error: {error:.4f}")
        logger.info("=" * 80)

        return error, merged, charuco_frames

    def get_rows_videos(self, videos: List[List[str]], board: "AniposeCharucoBoard", verbose: bool = True):
        num_corners = board.total_size
        self._get_charuco_2d_data(videos=videos, board=board)

        if self.charuco_2d_data is None:
            raise ValueError(
                "Charuco 2D data has not been initialized. Call _get_charuco_2d_data() first, or check for errors in the video processing.")

        all_rows = []

        num_cameras, num_frames, _, _ = self.charuco_2d_data.shape
        for camera_number in range(num_cameras):
            camera_rows = []
            for frame in range(num_frames):
                filled = self.charuco_2d_data[camera_number, frame, :, :]
                filled = filled.astype(np.float32)
                filled = np.reshape(filled, (num_corners, 1, 2))  # Add empty column anipose expects
                mask = (~np.isnan(filled[:, :, 0])) & (~np.isnan(filled[:, :, 1]))
                non_empty_ids = np.where(mask)[0]
                corners = filled[non_empty_ids, :, :]
                non_empty_ids = non_empty_ids.reshape(-1, 1)  # Add empty column anipose expects
                if corners.shape[0] != 0:
                    row = {
                        "framenum": (0, frame),
                        "corners": corners,
                        "ids": non_empty_ids,
                        "filled": filled,
                    }
                    camera_rows.append(row)
            all_rows.append(camera_rows)
        if verbose:
            print(f"Charuco detection results:")
            for i, rows in enumerate(all_rows):
                print(f"\tCamera {i} has {len(rows)} frames with detected corners.")

        return all_rows

    def _get_charuco_2d_data(self, videos: List[List[str]], board: "AniposeCharucoBoard"):
        """
        Processes a list of a list of videos to extract Charuco 2D data.

        Should be called once during the initial calibration, and then referenced with self.charuco_2d_data
        """
        # video_paths = [Path(video[0]) for video in videos]
        # charuco_2d_data = process_list_of_videos(
        #     model_info=CharucoModelInfo(),
        #     tracking_params=CharucoTrackingParams(
        #         charuco_squares_x_in=board.squaresX,
        #         charuco_squares_y_in=board.squaresY,
        #         charuco_dict_id=ARUCO_DICTS[(board.marker_bits, board.dict_size)]
        #     ),
        #     video_paths=video_paths,
        #     num_processes=min(len(videos), multiprocessing.cpu_count() - 1),
        # )
        #
        # self.charuco_2d_data = charuco_2d_data
        pass

    def set_camera_sizes_videos(self, videos):
        for cix, (cam, cam_videos) in enumerate(zip(self.cameras, videos)):
            rows_cam = []
            for vnum, vidname in enumerate(cam_videos):
                params = get_video_params(vidname)
                size = (params["width"], params["height"])
                cam.set_size(size)

    def calibrate_videos(
            self,
            videos,
            board: "AniposeCharucoBoard",
            init_intrinsics=True,
            init_extrinsics=True,
            verbose=True,
            **kwargs,
    ):
        """Takes as input a list of list of video filenames, one list of each camera.
        Also takes a board which specifies what should be detected in the videos"""

        all_rows = self.get_rows_videos(videos, board, verbose=verbose)
        if init_extrinsics:
            self.set_camera_sizes_videos(videos)

        error, merged, charuco_frames = self.calibrate_rows(
            all_rows,
            board,
            init_intrinsics=init_intrinsics,
            init_extrinsics=init_extrinsics,
            verbose=verbose,
        )
        return error, merged, charuco_frames

    def get_dicts(self):
        out = []
        for cam in self.cameras:
            out.append(cam.get_dict())
        return out

    @staticmethod
    def from_dicts(cameras_dicts):
        cameras = []
        for d in cameras_dicts:
            if "fisheye" in d and d["fisheye"]:
                cam = FisheyeCamera.from_dict(d)
            else:
                cam = Camera.from_dict(d)
            cameras.append(cam)
        return AniposeCameraGroup(cameras)

    @staticmethod
    def from_names(names, fisheye=False):
        cameras = []
        for name in names:
            if fisheye:
                cam = FisheyeCamera(name=name)
            else:
                cam = Camera(name=name)
            cameras.append(cam)
        return AniposeCameraGroup(cameras)

    def load_dicts(self, arr):
        for cam, d in zip(self.cameras, arr):
            cam.load_dict(d)

    def dump(self, fname):
        dicts = self.get_dicts()
        names = ["cam_{}".format(i) for i in range(len(dicts))]
        master_dict = dict(zip(names, dicts))
        master_dict["metadata"] = self.metadata
        with open(fname, "w") as f:
            toml.dump(master_dict, f)

    @staticmethod
    def load(fname: str):
        if not Path(fname).is_file():
            raise FileNotFoundError(f"File {fname} not found.")
        master_dict = toml.load(fname)
        keys = sorted(master_dict.keys())
        items = [master_dict[k] for k in keys if k != "metadata"]
        cgroup = AniposeCameraGroup.from_dicts(items)
        if "metadata" in master_dict:
            cgroup.metadata = master_dict["metadata"]
        return cgroup

    def resize_cameras(self, scale):
        for cam in self.cameras:
            cam.resize_camera(scale)


class AniposeCharucoBoard(CharucoBoard):
    def __init__(
            self,
            squaresX: int = 5,
            squaresY: int = 7,
            square_length: float = 58.0,
            marker_length: float = (58.0 * 0.8),
            marker_bits=4,
            dict_size=250,
    ):
        super().__init__(
            squaresX,
            squaresY,
            square_length,
            marker_length,
            marker_bits,
            dict_size,
        )
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

    def detect_markers(self, image, camera=None, refine=True):
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

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

        if camera is None:
            K = D = None
        else:
            K = camera.get_camera_matrix()
            D = camera.get_distortions()

        if refine:
            detectedCorners, detectedIds, rejectedCorners, recoveredIdxs = cv2.aruco.refineDetectedMarkers(
                gray, self.board, corners, ids, rejectedImgPoints, K, D, parameters=params
            )
        else:
            detectedCorners, detectedIds = corners, ids

        return detectedCorners, detectedIds

    def detect_image(self, image, camera=None):
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        corners, ids = self.detect_markers(image, camera, refine=True)
        if len(corners) > 0:
            ret, detectedCorners, detectedIds = cv2.aruco.interpolateCornersCharuco(corners, ids, gray, self.board)
            if detectedIds is None:
                detectedCorners = detectedIds = np.float64([])
        else:
            detectedCorners = detectedIds = np.float64([])

        return detectedCorners, detectedIds

    def estimate_pose_points(self, camera, corners, ids):
        if corners is None or ids is None or len(corners) < 5:
            return None, None

        n_corners = corners.size // 2
        corners = np.reshape(corners, (n_corners, 1, 2))

        K = camera.get_camera_matrix()
        D = camera.get_distortions()

        ret, rvec, tvec = cv2.aruco.estimatePoseCharucoBoard(corners, ids, self.board, K, D, None, None)

        return rvec, tvec
