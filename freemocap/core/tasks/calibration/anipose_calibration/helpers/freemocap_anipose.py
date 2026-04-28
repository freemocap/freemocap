# Adapted (with permission) from the original `aniposelib` package
# (https://github.com/lambdaloop/aniposelib).
# More info on Anipose: https://anipose.readthedocs.io/en/latest/

import logging
from collections import defaultdict
from typing import Any

import cv2
import numpy as np
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.tasks.calibration.anipose_calibration.helpers.anipose_charuco_board import AniposeCharucoBoard
from freemocap.core.tasks.calibration.shared.transform_math import build_maximum_spanning_tree, make_M, \
    robust_average_transforms, find_spanning_tree_pairs, get_rtvec

numba_logger = logging.getLogger("numba")
numba_logger.setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


# =============================================================================
# SHARED TYPES
# =============================================================================


class _BoardObservationsRequired(dict):
    """Base keys always present in a BoardObservations dict."""


class BoardObservations(_BoardObservationsRequired):
    """Typed dict carrying per-frame charuco board data for bundle adjustment.

    Required keys (always present after ``extract_points``):
        objp    -- (N, 3) float64: 3-D object points in board space
        ids     -- (N,) int32: board frame indices for each point row
        rvecs   -- (num_cameras, N, 3) float64: per-camera rotation vectors
        tvecs   -- (num_cameras, N, 3) float64: per-camera translation vectors

    Optional key (added by ``bundle_adjust`` just before optimisation):
        ids_map -- (N,) int32: contiguous 0-based remapping of ``ids``
    """


# Convenience alias for un-annotated callers that still pass ``None``.
OptionalBoardObservations = BoardObservations | None


# =============================================================================
# TRIANGULATION & REPROJECTION HELPERS
# =============================================================================


def get_error_dict(errors_full: np.ndarray, min_points: int = 10) -> dict[tuple[int, int], tuple[int, np.ndarray]]:
    """Compute pairwise reprojection error statistics across cameras.

    Args:
        errors_full: (num_cameras, N, 2) signed reprojection errors.
        min_points: Minimum shared observations required to include a pair.

    Returns:
        Dict mapping (cam_i, cam_j) → (num_shared_points, percentile_array)
        where percentile_array contains the [15th, 75th] percentiles of the
        mean pairwise error magnitude.
    """
    num_cameras = errors_full.shape[0]
    errors_norm = np.linalg.norm(errors_full, axis=2)
    good = ~np.isnan(errors_full[:, :, 0])
    error_dict: dict[tuple[int, int], tuple[int, np.ndarray]] = {}

    for i in range(num_cameras):
        for j in range(i + 1, num_cameras):
            subset = good[i] & good[j]
            err_subset = errors_norm[:, subset][[i, j]]
            err_subset_mean = np.mean(err_subset, axis=0)
            if np.sum(subset) > min_points:
                percents = np.percentile(err_subset_mean, [15, 75])
                error_dict[(i, j)] = (err_subset.shape[1], percents)
    return error_dict


def subset_extra(board_observations: OptionalBoardObservations, ixs: np.ndarray) -> OptionalBoardObservations:
    """Subset a BoardObservations dict to the given point indices.

    Args:
        board_observations: Board data dict, or ``None``.
        ixs: Boolean or integer index array selecting which points to keep.

    Returns:
        A new BoardObservations with all arrays subsetted, or ``None``.
    """
    if board_observations is None:
        return None
    result = BoardObservations(
        objp=board_observations["objp"][ixs],
        ids=board_observations["ids"][ixs],
        rvecs=board_observations["rvecs"][:, ixs],
        tvecs=board_observations["tvecs"][:, ixs],
    )
    if "ids_map" in board_observations:
        result["ids_map"] = board_observations["ids_map"][ixs]
    return result


def resample_points(
        image_points: np.ndarray,
        board_observations: OptionalBoardObservations = None,
        num_samples: int = 25,
) -> tuple[np.ndarray, OptionalBoardObservations]:
    """Subsample 2-D image points for bundle adjustment, prioritising multi-camera coverage.

    For each pair of cameras that share observations, picks up to ``num_samples``
    points weighted toward those seen by more cameras.

    Args:
        image_points: (num_cameras, N, 2) array; NaN where a camera has no observation.
        board_observations: Optional board data to subset in parallel with points.
        num_samples: Maximum points to sample per camera pair.

    Returns:
        Tuple of (subsetted image_points, subsetted board_observations).
    """
    num_cameras = image_points.shape[0]
    good = ~np.isnan(image_points[:, :, 0])
    ixs = np.arange(image_points.shape[1])
    num_cams_per_point = np.sum(~np.isnan(image_points[:, :, 0]), axis=0)

    include: set[int] = set()

    for i in range(num_cameras):
        for j in range(i + 1, num_cameras):
            subset = good[i] & good[j]
            n_good = np.sum(subset)
            if n_good > 0:
                arr = np.copy(num_cams_per_point[subset]).astype("float64")
                arr += np.random.random(size=arr.shape)
                picked_ix = np.argsort(-arr)[:num_samples]
                picked = ixs[subset][picked_ix]
                include.update(picked)

    final_ixs = sorted(include)
    newp = image_points[:, final_ixs]
    board_observations = subset_extra(board_observations, np.asarray(final_ixs))
    return newp, board_observations


def transform_points(
        points: np.ndarray,
        rotation_vectors: np.ndarray,
        translation_vectors: np.ndarray,
) -> np.ndarray:
    """Rotate points by Rodrigues vectors and translate.

    Args:
        points: (N, 3) array of 3-D points.
        rotation_vectors: (N, 3) Rodrigues rotation vectors, one per point.
        translation_vectors: (N, 3) translation vectors, one per point.

    Returns:
        (N, 3) rotated and translated points.
    """
    theta = np.linalg.norm(rotation_vectors, axis=1)[:, np.newaxis]
    with np.errstate(invalid="ignore"):
        v = rotation_vectors / theta
        v = np.nan_to_num(v)
    dot = np.sum(points * v, axis=1)[:, np.newaxis]
    cos_theta = np.cos(theta)
    sin_theta = np.sin(theta)

    rotated = cos_theta * points + sin_theta * np.cross(v, points) + dot * (1 - cos_theta) * v
    return rotated + translation_vectors


def remap_ids(ids: np.ndarray) -> np.ndarray:
    """Remap arbitrary board IDs to contiguous 0-based indices.

    Args:
        ids: (N,) integer array of board frame indices.

    Returns:
        (N,) integer array with values remapped to [0, num_unique).
    """
    unique_ids = np.unique(ids)
    ids_out = np.copy(ids)
    for i, num in enumerate(unique_ids):
        ids_out[ids == num] = i
    return ids_out


# =============================================================================
# CAMERA GRAPH & EXTRINSICS INITIALIZATION
# =============================================================================


def get_connections(
        rotation_translation_vectors: np.ndarray,
        camera_ids: list[CameraIdString],
        both: bool = True,
) -> dict[tuple[CameraIdString, CameraIdString], int]:
    """Count shared observation pairs between cameras.

    Args:
        rotation_translation_vectors: (num_cameras, N, 6) array; NaN rows indicate no observation.
        camera_ids: Ordered list of camera ID strings.
        both: If True, populate (a, b) and (b, a); otherwise only (a, b).

    Returns:
        Dict mapping (camera_id_a, camera_id_b) → shared frame count.
    """
    num_points = rotation_translation_vectors.shape[1]
    connections: dict[tuple[CameraIdString, CameraIdString], int] = {}

    for point_index in range(num_points):
        ixs = np.where(~np.isnan(rotation_translation_vectors[:, point_index, 0]))[0]
        keys = [camera_ids[ix] for ix in ixs]
        for i in range(len(keys)):
            a = CameraIdString(keys[i])
            for j in range(i + 1, len(keys)):
                b = CameraIdString(keys[j])
                connections[(a, b)] = connections.get((a, b), 0) + 1
                if both:
                    connections[(b, a)] = connections.get((b, a), 0) + 1
    return connections


def get_calibration_graph(
        rotation_translation_vectors: np.ndarray,
        camera_ids: list[CameraIdString],
) -> dict[CameraIdString, list[CameraIdString]]:
    """Build a maximum spanning tree of camera connections from shared observations.

    Args:
        rotation_translation_vectors: (num_cameras, N, 6) board pose array.
        camera_ids: Ordered list of camera ID strings.

    Returns:
        Adjacency dict representing the maximum spanning tree.
    """
    num_cameras = rotation_translation_vectors.shape[0]
    connections = get_connections(rotation_translation_vectors, camera_ids)
    return build_maximum_spanning_tree(
        connection_counts=connections,
        n_nodes=num_cameras,
        node_ids=camera_ids,
    )


def _get_pairwise_transform(rotation_translation_vectors: np.ndarray, left: int, right: int) -> np.ndarray:
    """Compute the robust average transform between two cameras from shared observations.

    For each frame where both cameras observe the board, computes
    ``M_left @ inv(M_right)`` and robustly averages the results.

    Args:
        rotation_translation_vectors: (num_cameras, N, 6) board pose array.
        left: Index of the left (source) camera.
        right: Index of the right (target) camera.

    Returns:
        (4, 4) average extrinsics transform from right to left.
    """
    transforms: list[np.ndarray] = []

    for detection_index in range(rotation_translation_vectors.shape[1]):
        d = rotation_translation_vectors[:, detection_index]
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
        rotation_translation_vectors: np.ndarray,
        pairs: list[tuple[CameraIdString, CameraIdString]],
        camera_ids: list[CameraIdString],
) -> dict[CameraIdString, np.ndarray]:
    """Compute camera extrinsics by chaining pairwise transforms along spanning tree pairs.

    Camera at pairs[0][0] is the root (identity transform).

    Args:
        rotation_translation_vectors: (num_cameras, N, 6) board pose array.
        pairs: Ordered list of (parent, child) camera ID pairs from the spanning tree.
        camera_ids: Ordered list of all camera ID strings.

    Returns:
        Dict mapping each camera ID to its (4, 4) extrinsics matrix.
    """
    extrinsics: dict[CameraIdString, np.ndarray] = {}
    source = pairs[0][0]
    extrinsics[source] = np.identity(4)

    id_to_index: dict[CameraIdString, int] = {camera_id: idx for idx, camera_id in enumerate(camera_ids)}

    for a, b in pairs:
        if a not in extrinsics:
            raise ValueError(f"Camera {a} must be computed before camera {b}")
        ext = _get_pairwise_transform(rotation_translation_vectors, id_to_index[b], id_to_index[a])
        extrinsics[b] = ext @ extrinsics[a]

    return extrinsics


def get_initial_extrinsics(
        rotation_translation_vectors: np.ndarray,
        camera_ids: list[CameraIdString],
) -> tuple[np.ndarray, np.ndarray]:
    """Compute initial camera extrinsics from board pose observations.

    Builds a maximum spanning tree from shared observation counts, computes
    pairwise transforms along the tree, and chains them from camera 0 (root).

    Args:
        rotation_translation_vectors: (num_cameras, N, 6) array of [rvec | tvec] board poses; NaN where unobserved.
        camera_ids: Ordered list of camera ID strings matching the first axis of ``rtvecs``.

    Returns:
        Tuple of (rvecs_array, tvecs_array), each shape (num_cameras, 3).
    """
    num_cameras = rotation_translation_vectors.shape[0]
    num_frames = rotation_translation_vectors.shape[1]
    logger.info(f"Computing initial extrinsics for {num_cameras} cameras from {num_frames} frames")

    for camera_index, camera_id in enumerate(camera_ids):
        valid_obs = np.sum(~np.isnan(rotation_translation_vectors[camera_index, :, 0]))
        logger.info(
            f"Camera {camera_id}: {valid_obs}/{num_frames} valid observations "
            f"({100 * valid_obs / num_frames:.1f}%)"
        )

    graph = get_calibration_graph(rotation_translation_vectors, camera_ids)
    logger.info(f"Calibration graph: {dict(graph)}")

    pairs = find_spanning_tree_pairs(graph)
    logger.info(f"Calibration pairs: {pairs}")

    if len(pairs) != num_cameras - 1:
        raise ValueError(f"Expected {num_cameras - 1} pairs, got {len(pairs)}. Graph may be disconnected!")

    extrinsics = compute_camera_matrices(rotation_translation_vectors=rotation_translation_vectors, pairs=pairs, camera_ids=camera_ids)

    rvecs_list: list[np.ndarray] = []
    tvecs_list: list[np.ndarray] = []
    for camera_index, camera_id in enumerate(camera_ids):
        if camera_id not in extrinsics:
            raise ValueError(f"Missing extrinsics for camera#{camera_index}, id: {camera_id}")
        rvec, tvec = get_rtvec(extrinsics[camera_id])
        rvecs_list.append(rvec)
        tvecs_list.append(tvec)

    rvecs_arr = np.array(rvecs_list)
    tvecs_arr = np.array(tvecs_list)

    logger.info(f"Rotation magnitudes: {np.linalg.norm(rvecs_arr, axis=1)}")
    logger.info(f"Translation magnitudes: {np.linalg.norm(tvecs_arr, axis=1)}")

    return rvecs_arr, tvecs_arr


def extract_roration_translation_vectors(
        merged: list[dict[CameraIdString, dict[str, Any]]],
        camera_ids: list[CameraIdString] | None = None,
        min_cameras: int = 1,
        board=None,
        cameras: list | None = None,
) -> np.ndarray:
    """Extract per-camera board pose vectors from merged detection rows.

    ``board.estimate_pose_rows`` should have been called on each camera's rows
    before merging. If not, pass ``board`` and ``cameras`` so poses can be
    estimated on the fly.

    Args:
        merged: List of per-frame dicts mapping camera_id → detection dict
            (keys: ``corners``, ``ids``, ``rvec``, ``tvec``, ``framenum``).
        camera_ids: Ordered camera IDs determining axis order of the output.
            If ``None``, inferred from the union of row keys (sorted).
        min_cameras: Drop frames seen by fewer than this many cameras.
        board: Calibration board object; required if poses are not pre-estimated.
        cameras: List of cameras; required alongside ``board`` if poses are not pre-estimated.

    Returns:
        (num_cameras, num_detections, 6) float64 array of [rvec | tvec] concatenated.
        Entries are NaN where a camera did not observe the board in that frame.
    """
    if camera_ids is None:
        s = set.union(*[set(r.keys()) for r in merged])
        camera_ids = sorted(s)

    num_cameras = len(camera_ids)
    num_detections = len(merged)

    rtvecs = np.empty((num_cameras, num_detections, 6), dtype="float64")
    rtvecs[:] = np.nan

    for row_index, row in enumerate(merged):
        for camera_index, camera_id in enumerate(camera_ids):
            if camera_id in row:
                r = row[camera_id]
                if "rvec" not in r or "tvec" not in r:
                    if board is None:
                        raise ValueError(
                            "rvec or tvec not found in rows. "
                            "board.estimate_pose_rows should have been run before merging, "
                            "or pass board and cameras as arguments."
                        )
                    rvec, tvec = board.estimate_pose_points(cameras[camera_index], r["corners"], r["ids"])
                    r["rvec"] = rvec
                    r["tvec"] = tvec

                if r["rvec"] is None or r["tvec"] is None:
                    continue

                rtvec = np.hstack([r["rvec"].ravel(), r["tvec"].ravel()])
                rtvecs[camera_index, row_index] = rtvec

    num_good = np.sum(~np.isnan(rtvecs), axis=0)[:, 0]
    rtvecs = rtvecs[:, num_good >= min_cameras]

    return rtvecs


def merge_rows(
        all_rows: list[list[dict[str, Any]]],
        camera_ids: list[CameraIdString] | None = None,
) -> list[dict[CameraIdString, dict[str, Any]]]:
    """Merge per-camera detection rows by frame number.

    Args:
        all_rows: One list of detection dicts per camera. Each dict must have
            a ``framenum`` key used to align frames across cameras.
        camera_ids: IDs to assign to each entry in ``all_rows``. If ``None``,
            uses integer indices (0, 1, 2, ...).

    Returns:
        List of dicts, one per unique frame number, mapping camera_id →
        that camera's detection dict for that frame (absent if not detected).
    """
    assert camera_ids is None or len(all_rows) == len(camera_ids), \
        "number of rows does not match the number of camera IDs"

    if camera_ids is None:
        camera_ids = list(range(len(all_rows)))

    rows_dict: dict[Any, dict[Any, dict[str, Any]]] = defaultdict(dict)
    framenums: set = set()

    for camera_id, rows in zip(camera_ids, all_rows):
        for r in rows:
            num = r["framenum"]
            rows_dict[camera_id][num] = r
            framenums.add(num)

    merged = []
    for num in sorted(framenums):
        d = {}
        for camera_id in camera_ids:
            if num in rows_dict[camera_id]:
                d[camera_id] = rows_dict[camera_id][num]
        merged.append(d)

    return merged


def extract_points(
        merged: list[dict[CameraIdString, dict[str, Any]]],
        board:AniposeCharucoBoard,
        camera_ids: list[CameraIdString] | None = None,
        min_cameras: int = 1,
        min_points: int = 4,
        check_rtvecs: bool = True,
) -> tuple[np.ndarray, BoardObservations]:
    """Extract 2-D image points and board metadata from merged detection rows.

    Args:
        merged: Output of ``merge_rows`` — list of per-frame dicts mapping
            camera_id → detection dict.
        board: Calibration board object providing ``get_empty_detection`` and
            ``get_object_points``.
        camera_ids: Ordered camera IDs. If ``None``, inferred from row keys (sorted).
        min_cameras: Drop points seen by fewer than this many cameras.
        min_points: Minimum valid corners required in a single camera-frame.
        check_rtvecs: If True, skip frames where ``rvec``/``tvec`` are missing.

    Returns:
        Tuple of:
            image_points -- (num_cameras, N, 2) float64; NaN where unobserved.
            board_observations -- BoardObservations dict with keys:
                ``objp``  (N, 3): object points in board space,
                ``ids``   (N,):   board frame indices,
                ``rvecs`` (num_cameras, N, 3): per-camera rotation vectors,
                ``tvecs`` (num_cameras, N, 3): per-camera translation vectors.
    """
    if camera_ids is None:
        s = set.union(*[set(r.keys()) for r in merged])
        camera_ids = sorted(s)

    test = board.get_empty_detection().reshape(-1, 2)
    num_cameras = len(camera_ids)
    num_points_per_detection = test.shape[0]
    num_detections = len(merged)

    objp_template = board.get_object_points().reshape(-1, 3)

    image_points = np.full(
        (num_cameras, num_detections, num_points_per_detection, 2), np.nan, dtype="float64"
    )
    rvecs = np.full(
        (num_cameras, num_detections, num_points_per_detection, 3), np.nan, dtype="float64"
    )
    tvecs = np.full(
        (num_cameras, num_detections, num_points_per_detection, 3), np.nan, dtype="float64"
    )
    objp = np.empty((num_detections, num_points_per_detection, 3), dtype="float64")
    board_ids = np.empty((num_detections, num_points_per_detection), dtype="int32")

    for row_index, row in enumerate(merged):
        objp[row_index] = np.copy(objp_template)
        board_ids[row_index] = row_index

        for camera_index, camera_id in enumerate(camera_ids):
            if camera_id in row:
                filled = row[camera_id]["filled"].reshape(-1, 2)
                bad = np.any(np.isnan(filled), axis=1)
                num_good = np.sum(~bad)
                if num_good < min_points:
                    continue

                if row[camera_id].get("rvec") is None or row[camera_id].get("tvec") is None:
                    if check_rtvecs:
                        continue
                    row[camera_id]["rvec"] = np.full(3, np.nan, dtype="float64")
                    row[camera_id]["tvec"] = np.full(3, np.nan, dtype="float64")

                image_points[camera_index, row_index] = filled
                rvecs[camera_index, row_index, ~bad] = row[camera_id]["rvec"].ravel()
                tvecs[camera_index, row_index, ~bad] = row[camera_id]["tvec"].ravel()

    image_points = np.reshape(image_points, (num_cameras, -1, 2))
    rvecs = np.reshape(rvecs, (num_cameras, -1, 3))
    tvecs = np.reshape(tvecs, (num_cameras, -1, 3))
    objp = np.reshape(objp, (-1, 3))
    board_ids = np.reshape(board_ids, (-1,))

    num_good = np.sum(~np.isnan(image_points), axis=0)[:, 0]
    good = num_good >= min_cameras

    image_points = image_points[:, good]
    rvecs = rvecs[:, good]
    tvecs = tvecs[:, good]
    objp = objp[good]
    board_ids = board_ids[good]

    board_observations = BoardObservations(
        objp=objp,
        ids=board_ids,
        rvecs=rvecs,
        tvecs=tvecs,
    )

    return image_points, board_observations
