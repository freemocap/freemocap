"""Shared rigid-transform math for camera calibration.

Contains format-agnostic functions for working with 4x4 rigid transforms:
robust averaging via clustering, spanning tree construction, etc.

Used by both the anipose and pyceres calibration paths.
"""

import logging
import queue
from collections import Counter, defaultdict

import cv2
import numpy as np
from numpy.typing import NDArray
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.cluster.vq import whiten

logger = logging.getLogger(__name__)


def make_M(rvec: NDArray[np.float64], tvec: NDArray[np.float64]) -> NDArray[np.float64]:
    """Build a 4x4 rigid transformation matrix from a Rodrigues rotation vector and translation.

    Args:
        rvec: (3,) Rodrigues rotation vector.
        tvec: (3,) translation vector.

    Returns:
        (4, 4) homogeneous transformation matrix.
    """
    rvec = np.asarray(rvec, dtype=np.float64).ravel()
    tvec = np.asarray(tvec, dtype=np.float64).ravel()
    R, _ = cv2.Rodrigues(rvec)
    M = np.eye(4, dtype=np.float64)
    M[:3, :3] = R
    M[:3, 3] = tvec
    return M


def get_rtvec(M: NDArray[np.float64]) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Extract Rodrigues rotation vector and translation from a 4x4 transform.

    Args:
        M: (4, 4) homogeneous transformation matrix.

    Returns:
        Tuple of (rvec, tvec), each shape (3,).
    """
    rvec, _ = cv2.Rodrigues(M[:3, :3])
    tvec = M[:3, 3]
    return rvec.ravel(), tvec.ravel()


def select_matrices_robust(matrices: list[NDArray[np.float64]]) -> list[NDArray[np.float64]]:
    """Cluster 4x4 transformation matrices and return those in the largest cluster.

    Uses Ward hierarchical clustering on concatenated (rvec, tvec) features.
    Filters outlier transforms that don't belong to the dominant mode.

    Args:
        matrices: List of 4x4 transformation matrices.

    Returns:
        Subset of matrices belonging to the largest cluster.
    """
    if len(matrices) <= 3:
        return list(matrices)

    Ms = np.array(matrices)
    rvecs = [cv2.Rodrigues(M[:3, :3])[0].ravel() for M in Ms]
    tvecs = [M[:3, 3] for M in Ms]
    features = np.hstack([np.array(rvecs), np.array(tvecs)])

    whitened = whiten(features)
    Z = linkage(whitened, method="ward")
    n_clust = max(len(matrices) // 10, 3)
    clusters = fcluster(Z, t=n_clust, criterion="maxclust")

    cc = Counter(clusters[clusters >= 0])
    top = cc.most_common(n=1)[0][0]
    mask = clusters == top

    return [matrices[i] for i in range(len(matrices)) if mask[i]]


def mean_transform(matrices: list[NDArray[np.float64]]) -> NDArray[np.float64]:
    """Compute mean 4x4 transformation from a list of transforms.

    Averages Rodrigues vectors and translation vectors independently,
    then reconstructs the transformation matrix.

    Args:
        matrices: Non-empty list of 4x4 transformation matrices.

    Returns:
        Mean 4x4 transformation matrix.

    Raises:
        ValueError: If the list is empty or produces NaN results.
    """
    if len(matrices) == 0:
        raise ValueError("Cannot compute mean transform from empty list")

    rvecs: list[NDArray[np.float64]] = []
    tvecs: list[NDArray[np.float64]] = []

    for i, M in enumerate(matrices):
        rvec = cv2.Rodrigues(M[:3, :3])[0].ravel()
        tvec = M[:3, 3]

        if rvec.shape != (3,) or tvec.shape != (3,):
            raise ValueError(f"Matrix {i}: invalid rvec shape {rvec.shape} or tvec shape {tvec.shape}")

        rvecs.append(rvec)
        tvecs.append(tvec)

    mean_rvec = np.mean(rvecs, axis=0)
    mean_tvec = np.mean(tvecs, axis=0)

    if np.any(np.isnan(mean_rvec)):
        raise ValueError(f"NaN in mean rvec: {mean_rvec}")
    if np.any(np.isnan(mean_tvec)):
        raise ValueError(f"NaN in mean tvec: {mean_tvec}")

    return make_M(mean_rvec, mean_tvec)


def mean_transform_robust(
    matrices: list[NDArray[np.float64]],
    initial_estimate: NDArray[np.float64],
    error_threshold: float = 0.3,
    max_iterations: int = 5,
    convergence_threshold: float = 0.001,
) -> NDArray[np.float64]:
    """Iteratively filter outlier transforms and recompute the mean.

    At each iteration, transforms whose rotation block differs from the
    current estimate by more than ``error_threshold`` are discarded.
    If all are discarded, the best 50% by error are kept as a fallback.

    Args:
        matrices: List of 4x4 transformation matrices.
        initial_estimate: Starting approximation for comparison.
        error_threshold: Max acceptable rotation-block deviation.
        max_iterations: Maximum refinement iterations.
        convergence_threshold: Stop if change falls below this.

    Returns:
        Robustly averaged 4x4 transformation matrix.

    Raises:
        ValueError: If the input list is empty.
    """
    if len(matrices) == 0:
        raise ValueError("Cannot compute robust mean from empty list")

    current = initial_estimate

    for iteration in range(max_iterations):
        kept: list[NDArray[np.float64]] = []
        errors: list[float] = []

        for M in matrices:
            rot_error = np.max(np.abs((M - current)[:3, :3]))
            errors.append(rot_error)
            if rot_error < error_threshold:
                kept.append(M)

        if len(kept) == 0:
            sorted_indices = np.argsort(errors)
            n_keep = max(len(matrices) // 2, 3)
            kept = [matrices[i] for i in sorted_indices[:n_keep]]
            logger.warning(
                f"All matrices filtered at threshold {error_threshold}. "
                f"Using {len(kept)} best matrices as fallback."
            )

        new_mean = mean_transform(kept)
        diff = np.max(np.abs(new_mean - current))
        current = new_mean

        if diff < convergence_threshold:
            break

    return current


def robust_average_transforms(transforms: list[NDArray[np.float64]]) -> NDArray[np.float64]:
    """Full robust averaging pipeline for a list of 4x4 transforms.

    Clusters to remove outliers, computes initial mean, then progressively
    refines with decreasing error thresholds.

    Args:
        transforms: List of 4x4 transformation matrices.

    Returns:
        Robustly averaged 4x4 transformation matrix.

    Raises:
        ValueError: If the input list is empty.
    """
    if len(transforms) == 0:
        raise ValueError("No transforms to average")

    selected = select_matrices_robust(transforms)
    current = mean_transform(selected)

    for threshold in [0.5, 0.3, 0.15, 0.1]:
        refined = mean_transform_robust(
            matrices=transforms,
            initial_estimate=current,
            error_threshold=threshold,
            max_iterations=3,
            convergence_threshold=0.001,
        )

        diff = np.max(np.abs(refined - current))
        if diff > 10.0:
            logger.warning(f"Large transform change ({diff:.2f}) at threshold {threshold}, stopping refinement")
            break

        current = refined

    return current


def build_maximum_spanning_tree(
    connection_counts: dict[tuple[int, int], int],
    n_nodes: int,
    node_labels: list[str] | None = None,
) -> dict[int, list[int]]:
    """Build a maximum spanning tree from weighted edges via greedy Kruskal.

    Args:
        connection_counts: Mapping of (node_a, node_b) → weight for all pairs
            (both directions, i.e. (a,b) and (b,a)).
        n_nodes: Total number of nodes.
        node_labels: Human-readable labels for error messages.

    Returns:
        Adjacency list representation of the spanning tree.

    Raises:
        ValueError: If the graph cannot be connected.
    """
    if node_labels is None:
        node_labels = [str(i) for i in range(n_nodes)]

    components = {i: i for i in range(n_nodes)}
    edges = set(connection_counts.items())
    graph: dict[int, list[int]] = defaultdict(list)

    for _ in range(n_nodes - 1):
        if len(edges) == 0:
            comp_map = {node_labels[k]: v for k, v in components.items()}
            raise ValueError(
                f"Cannot build connected calibration graph. "
                f"Some cameras have no shared board observations. "
                f"Component map: {comp_map}"
            )

        (a, b), weight = max(edges, key=lambda x: x[1])
        graph[a].append(b)
        graph[b].append(a)

        match_comp = components[a]
        replace_comp = components[b]
        for k in components:
            if components[k] == match_comp:
                components[k] = replace_comp

        for e in list(edges):
            (ea, eb), _ = e
            if components[ea] == components[eb]:
                edges.discard(e)

    return dict(graph)


def find_spanning_tree_pairs(
    graph: dict[int, list[int]],
    root: int = 0,
) -> list[tuple[int, int]]:
    """BFS from root to produce (parent, child) pairs for the spanning tree.

    Args:
        graph: Adjacency list (from ``build_maximum_spanning_tree``).
        root: Root node index.

    Returns:
        List of (parent, child) tuples in BFS order.
    """
    pairs: list[tuple[int, int]] = []
    visited: set[int] = set()
    q: queue.Queue[int] = queue.Queue()
    q.put(root)
    visited.add(root)

    while not q.empty():
        node = q.get()
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                visited.add(neighbor)
                q.put(neighbor)
                pairs.append((node, neighbor))

    return pairs
