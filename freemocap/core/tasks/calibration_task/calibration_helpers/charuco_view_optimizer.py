import logging
from typing import Protocol

import numpy as np
from pydantic import BaseModel, Field
from scipy.spatial.distance import cdist
from sklearn.cluster import KMeans

logger = logging.getLogger(__name__)


class ObservationProtocol(Protocol):
    """Protocol for observations that can be optimized."""
    detected_charuco_corners_image_coordinates: np.ndarray
    frame_number: int


class CharucoViewSelectionConfig(BaseModel):
    """Configuration for view selection optimization."""
    target_view_count: int = Field(default=30, ge=1, le=200)
    initial_view_count: int = Field(default=15, ge=5, le=50)
    grid_size: tuple[int, int] = Field(default=(3,3))
    min_coverage_per_cell: float = Field(default=0.5, ge=0.0, le=1.0)
    coverage_weight: float = Field(default=0.6, ge=0.0, le=1.0)
    diversity_weight: float = Field(default=0.4, ge=0.0, le=1.0)


class CharucoViewOptimizer:
    """
    Two-stage view optimizer for camera calibration:

    Stage 1: Select initial subset using coverage + spatial diversity (no pose info needed)
    Stage 2: Select optimal subset using coverage + pose diversity (requires pose estimates)

    Workflow:
    1. Call select_initial_views() -> get indices for quick calibration
    2. Calibrate camera using initial views (external)
    3. Estimate poses for ALL views using calibration (external)
    4. Call select_final_views() with pose data -> get optimal subset
    5. Perform final calibration on optimal subset (external)

    References:
    - OpenCV recommends 20-40 images for calibration
    - Above 100 images provides diminishing returns with exponential computation cost
    """

    def __init__(
            self,
            image_size: tuple[int, int],
            config: CharucoViewSelectionConfig = CharucoViewSelectionConfig()
    ):
        self.image_size = image_size
        self.config = config
        self.width = image_size[0]
        self.height = image_size[1]

    def select_initial_views(
            self,
            observations: list[ObservationProtocol]
    ) -> list[int]:
        """
        Stage 1: Select initial subset for bootstrapping calibration.

        Uses only coverage and spatial diversity (no pose information required).
        This subset should be used for a quick initial calibration to obtain
        camera parameters for pose estimation.

        Args:
            observations: All available observations

        Returns:
            Indices of observations for initial calibration

        Raises:
            ValueError: If no observations provided
        """
        if len(observations) == 0:
            raise ValueError("No observations provided")

        target = self.config.initial_view_count

        if len(observations) <= target:
            logger.info(f"Using all {len(observations)} views for initial calibration")
            return list(range(len(observations)))

        logger.info(f"Selecting {target} initial views from {len(observations)} for bootstrapping")

        coverage_scores = self._compute_coverage_scores(observations=observations)
        diversity_scores = self._compute_spatial_diversity_scores(observations=observations)

        combined_scores = (
                self.config.coverage_weight * coverage_scores +
                self.config.diversity_weight * diversity_scores
        )

        selected_indices = np.argsort(combined_scores)[-target:]
        selected_indices = sorted(selected_indices.tolist())

        logger.info(f"Selected {len(selected_indices)} initial views")
        return selected_indices

    def select_final_views(
            self,
            observations: list[ObservationProtocol],
            rotation_vectors: list[np.ndarray],
            translation_vectors: list[np.ndarray]
    ) -> list[int]:
        """
        Stage 2: Select optimal final subset using pose information.

        Uses coverage + pose-based diversity for optimal view selection.
        Requires pose estimates for ALL observations (from initial calibration).

        Args:
            observations: All available observations
            rotation_vectors: Rotation vectors for all observations (from pose estimation)
            translation_vectors: Translation vectors for all observations (from pose estimation)

        Returns:
            Indices of observations for final calibration

        Raises:
            ValueError: If inputs are invalid or mismatched lengths
        """
        if len(observations) == 0:
            raise ValueError("No observations provided")

        if len(rotation_vectors) != len(observations):
            raise ValueError(
                f"Rotation vectors length ({len(rotation_vectors)}) "
                f"must match observations length ({len(observations)})"
            )

        if len(translation_vectors) != len(observations):
            raise ValueError(
                f"Translation vectors length ({len(translation_vectors)}) "
                f"must match observations length ({len(observations)})"
            )

        target = self.config.target_view_count

        if len(observations) <= target:
            logger.info(f"Using all {len(observations)} views for final calibration")
            return list(range(len(observations)))

        logger.info(f"Selecting {target} optimal views from {len(observations)}")

        coverage_scores = self._compute_coverage_scores(observations=observations)
        diversity_scores = self._compute_pose_diversity_scores(
            rotation_vectors=rotation_vectors,
            translation_vectors=translation_vectors
        )

        combined_scores = (
                self.config.coverage_weight * coverage_scores +
                self.config.diversity_weight * diversity_scores
        )

        selected_indices = np.argsort(combined_scores)[-target:]
        selected_indices = sorted(selected_indices.tolist())

        logger.info(
            f"Selected {len(selected_indices)} final views - "
            f"mean coverage: {coverage_scores[selected_indices].mean():.3f}, "
            f"mean diversity: {diversity_scores[selected_indices].mean():.3f}"
        )

        return selected_indices

    def _compute_coverage_scores(
            self,
            observations: list[ObservationProtocol]
    ) -> np.ndarray:
        """
        Compute spatial coverage score for each observation.

        Score based on:
        1. Number of grid cells covered
        2. Uniformity of coverage across cells
        3. Edge/corner coverage bonus
        """
        grid_rows, grid_cols = self.config.grid_size
        cell_height = self.height / grid_rows
        cell_width = self.width / grid_cols

        scores = np.zeros(len(observations))

        for idx, obs in enumerate(observations):
            points = obs.detected_charuco_corners_image_coordinates
            if len(points) == 0:
                scores[idx] = 0.0
                continue

            grid_coverage = np.zeros((grid_rows, grid_cols), dtype=bool)

            for point in points:
                x, y = point[0], point[1]
                grid_row = int(min(y / cell_height, grid_rows - 1))
                grid_col = int(min(x / cell_width, grid_cols - 1))
                grid_coverage[grid_row, grid_col] = True

            coverage_ratio = grid_coverage.sum() / (grid_rows * grid_cols)

            edge_bonus = self._compute_edge_coverage_bonus(
                points=points,
                grid_coverage=grid_coverage,
                grid_rows=grid_rows,
                grid_cols=grid_cols
            )

            density_bonus = min(len(points) / 50.0, 1.0) * 0.2

            scores[idx] = coverage_ratio + edge_bonus + density_bonus

        if scores.max() > 0:
            scores = scores / scores.max()

        return scores

    def _compute_edge_coverage_bonus(
            self,
            points: np.ndarray,
            grid_coverage: np.ndarray,
            grid_rows: int,
            grid_cols: int
    ) -> float:
        """Compute bonus for covering edge and corner regions."""
        top_edge = grid_coverage[0, :].any()
        bottom_edge = grid_coverage[-1, :].any()
        left_edge = grid_coverage[:, 0].any()
        right_edge = grid_coverage[:, -1].any()

        edge_coverage_count = sum([top_edge, bottom_edge, left_edge, right_edge])

        corners_covered = 0
        corner_regions = [
            (0, 0), (0, grid_cols - 1),
            (grid_rows - 1, 0), (grid_rows - 1, grid_cols - 1)
        ]
        for row, col in corner_regions:
            if grid_coverage[row, col]:
                corners_covered += 1

        edge_bonus = (edge_coverage_count / 4.0) * 0.15
        corner_bonus = (corners_covered / 4.0) * 0.15

        return edge_bonus + corner_bonus

    def _compute_pose_diversity_scores(
            self,
            rotation_vectors: list[np.ndarray],
            translation_vectors: list[np.ndarray]
    ) -> np.ndarray:
        """
        Compute diversity scores based on pose clustering.

        Views with unique poses get higher scores.
        """
        if len(rotation_vectors) == 0:
            raise ValueError("No rotation vectors provided")

        pose_features = []
        for rvec, tvec in zip(rotation_vectors, translation_vectors):
            rvec_norm = rvec.flatten() / (np.linalg.norm(rvec) + 1e-8)
            tvec_norm = tvec.flatten() / (np.linalg.norm(tvec) + 1e-8)
            pose_features.append(np.concatenate([rvec_norm, tvec_norm]))

        pose_features_array = np.array(pose_features)

        n_clusters = min(self.config.target_view_count, len(pose_features_array))
        if n_clusters < 2:
            return np.ones(len(pose_features_array))

        try:
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            cluster_labels = kmeans.fit_predict(pose_features_array)
        except Exception as e:
            logger.warning(f"Pose clustering failed: {e}, using uniform scores")
            return np.ones(len(pose_features_array))

        scores = np.zeros(len(pose_features_array))

        for cluster_id in range(n_clusters):
            cluster_mask = cluster_labels == cluster_id
            cluster_size = cluster_mask.sum()

            if cluster_size == 0:
                continue

            cluster_center = kmeans.cluster_centers_[cluster_id]
            cluster_points = pose_features_array[cluster_mask]

            distances = cdist(cluster_points, cluster_center.reshape(1, -1)).flatten()

            if distances.max() > 0:
                normalized_distances = 1.0 - (distances / distances.max())
            else:
                normalized_distances = np.ones(len(distances))

            cluster_weight = 1.0 / np.sqrt(cluster_size)

            scores[cluster_mask] = normalized_distances * cluster_weight

        if scores.max() > 0:
            scores = scores / scores.max()

        return scores

    def _compute_spatial_diversity_scores(
            self,
            observations: list[ObservationProtocol]
    ) -> np.ndarray:
        """
        Compute diversity based on spatial distribution of points.

        Used in stage 1 when pose information is not available.
        """
        scores = np.zeros(len(observations))

        for idx, obs in enumerate(observations):
            points = obs.detected_charuco_corners_image_coordinates
            if len(points) < 2:
                scores[idx] = 0.0
                continue

            x_coords = points[:, 0]
            y_coords = points[:, 1]

            x_spread = np.std(x_coords) / self.width
            y_spread = np.std(y_coords) / self.height

            scores[idx] = (x_spread + y_spread) / 2.0

        if scores.max() > 0:
            scores = scores / scores.max()

        return scores

    def compute_coverage_heatmap(
            self,
            observations: list[ObservationProtocol],
            selected_indices: list[int] | None = None
    ) -> np.ndarray:
        """
        Compute a heatmap showing coverage across the image.

        Args:
            observations: All observations
            selected_indices: Indices to visualize (if None, uses all observations)

        Returns:
            Heatmap array of shape (grid_rows, grid_cols)
        """
        grid_rows, grid_cols = self.config.grid_size
        cell_height = self.height / grid_rows
        cell_width = self.width / grid_cols

        heatmap = np.zeros((grid_rows, grid_cols))

        indices_to_use = selected_indices if selected_indices is not None else range(len(observations))

        for idx in indices_to_use:
            obs = observations[idx]
            points = obs.detected_charuco_corners_image_coordinates

            for point in points:
                x, y = point[0], point[1]
                grid_row = int(min(y / cell_height, grid_rows - 1))
                grid_col = int(min(x / cell_width, grid_cols - 1))
                heatmap[grid_row, grid_col] += 1

        return heatmap