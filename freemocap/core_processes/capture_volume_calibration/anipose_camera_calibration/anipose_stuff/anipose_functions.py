import queue
from collections import defaultdict, Counter
from typing import Any

import cv2
import numpy as np
from scipy import signal
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.cluster.vq import whiten
from scipy.linalg import inv as inverse

def make_M(rvec, tvec):
    out = np.zeros((4,4))
    rotmat, _ = cv2.Rodrigues(rvec)
    out[:3,:3] = rotmat
    out[:3, 3] = tvec.flatten()
    out[3, 3] = 1
    return out

def get_rtvec(M):
    rvec = cv2.Rodrigues(M[:3, :3])[0].flatten()
    tvec = M[:3, 3].flatten()
    return rvec, tvec

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
    errors_full = cgroup.calculate_reprojection_error(p3ds, imgp, mean=False)
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


def resample_points_based_on_shared_views(points2d: np.ndarray,
                                          extra_data: dict[str, Any] |None = None,
                                          number_of_samples_to_return: int = 25) -> tuple[np.ndarray, dict[str, Any] | None]:
    """
    Resample 2D points to prioritize those seen by multiple cameras.

    :param points2d: A 3D array of shape (N_cams, N_points, 2) containing 2D points for each camera.
                     NaN values represent missing data for a camera.
    :param extra_data: Optional dictionary containing additional data (like {'objp', 'ids', 'rvecs', 'tvecs'})
                  that should be resampled in the same way as points2d.
    :param number_of_samples_to_return: The maximum number of points to sample, prioritizing those visible in more cameras.
    :return: A tuple containing the resampled points2d and the resampled extra dictionary.
    """

    n_cams = points2d.shape[0]
    points2d_valid = ~np.isnan(points2d[:, :, 0])  # Boolean array indicating valid (non-NaN) points
    point_indices = np.arange(points2d.shape[1])
    num_cams = np.sum(points2d_valid, axis=0)  # Number of cameras observing each point

    included_points = set()

    # Iterate over each unique pair of cameras
    for first_cam in range(n_cams):
        for second_cam in range(first_cam + 1, n_cams):
            # Determine which points are visible in both selected cameras
            visible_in_both = points2d_valid[first_cam] & points2d_valid[second_cam]
            n_good = np.sum(visible_in_both)

            if n_good > 0:
                # Select points seen by the most cameras, adding a small random value for tie-breaking
                visibility_scores = num_cams[visible_in_both].astype(np.float64)
                visibility_scores += np.random.random(size=visibility_scores.shape)

                # Pick the top n_samp points based on visibility scores
                picked_indices = np.argsort(-visibility_scores)[:number_of_samples_to_return]
                selected_points = point_indices[visible_in_both][picked_indices]

                # Add selected points to the set of included points
                included_points.update(selected_points)

    # Sort the final indices of included points for consistent ordering
    final_indices = sorted(included_points)
    resampled_ponts = points2d[:, final_indices]

    # Subset the extra data if provided
    if extra_data is not None:
        extra_data = subset_extra_data(extra_data, final_indices)

    return resampled_ponts, extra_data


def subset_extra_data(extra_data: dict[str, Any], indices: np.ndarray) -> dict[str, Any]:
    """
    Subset the extra data dictionary based on the selected indices.

    :param extra_data: The dictionary containing extra data.
    :param indices: The indices to subset the data.
    :return: A new dictionary with data subset according to the provided indices.
    """
    if not extra_data:
        return extra_data
    return {key: value[indices] for key, value in extra_data.items() if key in extra_data}


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


def get_connections(xs, cam_names=None, both=True):
    n_cams = xs.shape[0]
    n_points = xs.shape[1]

    if cam_names is None:
        cam_names = np.arange(n_cams)

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


def compute_camera_matrices(rtvecs, pairs):
    extrinsics = dict()
    source = pairs[0][0]
    extrinsics[source] = np.identity(4)
    for a, b in pairs:
        ext = get_transform(rtvecs, b, a)
        extrinsics[b] = np.matmul(ext, extrinsics[a])
    return extrinsics


def get_transform(rtvecs, left, right):
    L = []
    for dix in range(rtvecs.shape[1]):
        d = rtvecs[:, dix]
        good = ~np.isnan(d[:, 0])

        if good[left] and good[right]:
            M_left = make_M(d[left, 0:3], d[left, 3:6])
            M_right = make_M(d[right, 0:3], d[right, 3:6])
            M = np.matmul(M_left, inverse(M_right))
            L.append(M)
    L_best = select_matrices(L)
    M_mean = mean_transform(L_best)
    # M_mean = mean_transform_robust(L, M_mean, error=0.5)
    # M_mean = mean_transform_robust(L, M_mean, error=0.2)
    M_mean = mean_transform_robust(L, M_mean, error=0.1)
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


def mean_transform(M_list):
    rvecs = [cv2.Rodrigues(M[:3, :3])[0][:, 0] for M in M_list]
    tvecs = [M[:3, 3] for M in M_list]

    rvec = np.mean(rvecs, axis=0)
    tvec = np.mean(tvecs, axis=0)

    return make_M(rvec, tvec)


def mean_transform_robust(M_list, approx=None, error=0.3):
    if approx is None:
        M_list_robust = M_list
    else:
        M_list_robust = []
        for M in M_list:
            rot_error = (M - approx)[:3, :3]
            m = np.max(np.abs(rot_error))
            if m < error:
                M_list_robust.append(M)
    return mean_transform(M_list_robust)


def get_initial_extrinsics(rtvecs, cam_names=None):
    graph = get_calibration_graph(rtvecs, cam_names)
    pairs = find_calibration_pairs(graph, source=0)
    extrinsics = compute_camera_matrices(rtvecs, pairs)

    n_cams = rtvecs.shape[0]
    rvecs = []
    tvecs = []
    for cnum in range(n_cams):
        rvec, tvec = get_rtvec(extrinsics[cnum])
        rvecs.append(rvec)
        tvecs.append(tvec)
    rvecs = np.array(rvecs)
    tvecs = np.array(tvecs)
    return rvecs, tvecs


def calculate_error_bounds(error_dict: dict[tuple[int, int], tuple[int, np.ndarray]]) -> tuple[float, float]:
    """Calculate the maximum and minimum error bounds from an error dictionary.

    Args:
        error_dict (Dict[Tuple[int, int], Tuple[int, np.ndarray]]): Dictionary containing error statistics
            for camera pairs, where the key is a tuple of camera indices and the value is a tuple of
            (number of observations, percentiles).

    Returns:
        Tuple[float, float]: A tuple of (max_error, min_error) based on the percentiles of error means.
    """
    max_error = 0.0
    min_error = float('inf')
    for _, (_, percents) in error_dict.items():
        max_error = max(percents[-1], max_error)
        min_error = min(percents[0], min_error)
    return max_error, min_error
