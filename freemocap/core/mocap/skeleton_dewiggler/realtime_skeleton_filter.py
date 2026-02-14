"""
Realtime skeleton filter: One Euro + FABRIK with running bone length estimation.

Purpose-built for the realtime pipeline where:
    - Bone lengths are unknown at startup and estimated online
    - Keypoints may be partially missing on any given frame
    - Calibration can change mid-session (requiring a full reset)
    - Timestamps come from real wall-clock time, not uniform FPS

Pipeline (per frame):
    1. Feed raw 3D positions to BoneLengthEstimator (refines bone lengths)
    2. Per-keypoint One Euro filtering (jitter removal)
    3. Tree FABRIK solving with latest bone lengths (constraint enforcement)

Keypoints not in any FABRIK tree are returned filter-only.
Keypoints missing from a frame are skipped entirely (no interpolation).

Usage:
    filt = RealtimeSkeletonFilter.create(
        skeleton=SkeletonDefinition.mediapipe_body(),
        prior=AnthropometricPrior.mediapipe_body(),
        height_meters=1.75,
    )

    for t, raw_3d_points in triangulated_stream:
        clean = filt.process_frame(t=t, positions=raw_3d_points)
"""

import logging
from dataclasses import dataclass, field

import numpy as np
from pydantic import BaseModel

from freemocap.core.mocap.skeleton_dewiggler.dewiggling_methods.bone_length_estimator import EstimatorConfig, \
    BoneLengthEstimator, AnthropometricPrior
from freemocap.core.mocap.skeleton_dewiggler.dewiggling_methods.fabrik_solver import FabrikTree, solve_fabrik_tree
from freemocap.core.mocap.skeleton_dewiggler.dewiggling_methods.mediapipe_skeleton_config import SkeletonDefinition
from freemocap.core.mocap.skeleton_dewiggler.dewiggling_methods.one_euro_filter import OneEuroFilter3D

logger = logging.getLogger(__name__)


class RealtimeFilterConfig(BaseModel):
    """Tunable parameters for the realtime filtering pipeline."""

    # One Euro Filter params
    # min_cutoff: minimum cutoff frequency (Hz). Lower = more smoothing, higher = more responsive.
    min_cutoff: float = 0.01
    # beta: speed coefficient. Higher = less lag during fast motion, but more jitter at rest.
    beta: float = 0.5
    # d_cutoff: cutoff frequency for the derivative (speed estimate) filter.
    d_cutoff: float = 1.0

    # FABRIK params
    fabrik_tolerance: float = 1e-4
    fabrik_max_iterations: int = 20

    # Bone length estimation params
    # height_meters: assumed subject height, used to scale anthropometric bone length priors.
    height_meters: float = 1.75
    # noise_sigma: expected measurement noise (meters). Higher = trust raw measurements less.
    noise_sigma: float = 0.015
    estimator_config: EstimatorConfig = EstimatorConfig()

    # Reprojection error gate: reject triangulated points whose mean
    # reprojection error across cameras exceeds this threshold (pixels).
    # Higher = more permissive (keeps noisier triangulations).
    max_reprojection_error_px: float = 60.0

    # Velocity gate: reject points that jump faster than this (meters/second).
    # Human body parts rarely exceed ~15 m/s even during fast movements,
    # but noisy triangulation can produce brief spikes. Keep generous to
    # avoid rejecting real fast motions.
    max_velocity_m_per_s: float = 50.0

    # Velocity gate: after this many consecutive rejections, accept
    # unconditionally to prevent permanent lockout. Lower = recover faster.
    max_rejected_streak: int = 3


@dataclass
class RealtimeSkeletonFilter:
    """
    Frame-by-frame realtime skeleton filter with online bone length estimation.

    Handles partial keypoint data gracefully: keypoints missing from a frame
    are skipped (no filtering, no FABRIK). Keypoints appearing for the first
    time get a new One Euro filter initialized at that frame's timestamp.

    Bone lengths are estimated online from observed inter-keypoint distances
    and blended with an anthropometric prior. The FABRIK solver uses the
    latest blended bone lengths each frame.

    FABRIK only runs when all joints in the tree are present. If any tree
    joint is missing, FABRIK is skipped and only One Euro filtering is applied.
    """

    skeleton: SkeletonDefinition
    config: RealtimeFilterConfig
    bone_estimator: BoneLengthEstimator
    fabrik_tree: FabrikTree = field(repr=False)
    _filters: dict[str, OneEuroFilter3D] = field(
        default_factory=dict, init=False, repr=False,
    )

    @classmethod
    def create(
        cls,
        *,
        skeleton: SkeletonDefinition,
        prior: AnthropometricPrior,
        config: RealtimeFilterConfig,
    ) -> "RealtimeSkeletonFilter":
        estimator = BoneLengthEstimator.create(
            skeleton=skeleton,
            prior=prior,
            height_meters=config.height_meters,
            noise_sigma=config.noise_sigma,
            config=config.estimator_config,
        )
        fabrik_tree = FabrikTree.from_skeleton(skeleton=skeleton)
        return cls(
            skeleton=skeleton,
            config=config,
            bone_estimator=estimator,
            fabrik_tree=fabrik_tree,
        )

    def reset(self) -> None:
        """Reset all filter state. Call when calibration changes."""
        self._filters.clear()
        # Re-create the estimator to clear observation history
        # (prior lengths are preserved via the estimator's create path)
        self.bone_estimator = BoneLengthEstimator.create(
            skeleton=self.skeleton,
            prior=AnthropometricPrior(
                ratios={
                    bone_key: length / self.config.height_meters
                    for bone_key, length in self.bone_estimator.prior_lengths.items()
                },
            ),
            height_meters=self.config.height_meters,
            noise_sigma=self.config.noise_sigma,
            config=self.config.estimator_config,
        )

    def process_frame(
        self,
        *,
        t: float,
        positions: dict[str, np.ndarray],
    ) -> dict[str, np.ndarray]:
        """
        Process one frame of triangulated 3D keypoint positions.

        Args:
            t: timestamp in seconds (must be strictly increasing across calls).
            positions: raw triangulated positions, mapping name → (3,) array.
                       May be a subset of skeleton keypoints.

        Returns:
            Filtered + bone-length-constrained positions for all input keypoints.
        """
        if not positions:
            return {}

        # --- Step 0: Feed the bone length estimator ---
        self.bone_estimator.observe(positions=positions)

        # --- Step 1: One Euro filter each keypoint ---
        filtered: dict[str, np.ndarray] = {}
        for name, pos in positions.items():
            pos_f64 = np.asarray(pos, dtype=np.float64)
            if pos_f64.shape != (3,):
                raise ValueError(
                    f"Expected shape (3,) for keypoint '{name}', got {pos_f64.shape}"
                )

            if name not in self._filters:
                # First time seeing this keypoint — initialize filter, return raw
                self._filters[name] = OneEuroFilter3D(
                    t0=t,
                    x0=pos_f64,
                    min_cutoff=self.config.min_cutoff,
                    beta=self.config.beta,
                    d_cutoff=self.config.d_cutoff,
                )
                filtered[name] = pos_f64
            else:
                filtered[name] = self._filters[name](t=t, x=pos_f64)

        # --- Step 2: Tree FABRIK with latest bone lengths ---
        if not self.fabrik_tree.nodes:
            return filtered

        # Check if all FABRIK tree joints are present
        all_tree_joints_present = all(
            name in filtered for name in self.fabrik_tree.topo_order
        )

        if not all_tree_joints_present:
            # Can't run FABRIK with missing joints — return filter-only
            return filtered

        bone_lengths = self.bone_estimator.current_lengths

        fabrik_targets: dict[str, np.ndarray] = {
            name: filtered[name]
            for name in self.fabrik_tree.topo_order
        }

        solved = solve_fabrik_tree(
            targets=fabrik_targets,
            tree=self.fabrik_tree,
            bone_lengths=bone_lengths,
            tolerance=self.config.fabrik_tolerance,
            max_iterations=self.config.fabrik_max_iterations,
        )

        # Merge: FABRIK-solved joints override, non-tree joints keep filter-only
        result: dict[str, np.ndarray] = {}
        for name, pos in filtered.items():
            if name in solved:
                result[name] = solved[name]
            else:
                result[name] = pos

        return result

    @property
    def current_bone_lengths(self) -> dict[str, float]:
        """Current blended bone length estimates."""
        return self.bone_estimator.current_lengths

    @property
    def current_confidence(self) -> dict[str, float]:
        """Current bone length estimation confidence (0→1) per bone."""
        return self.bone_estimator.current_confidence