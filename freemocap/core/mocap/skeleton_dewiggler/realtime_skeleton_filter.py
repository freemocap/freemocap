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
       - Present keypoints: normal filter update
       - Missing keypoints: extrapolate via filter's stored velocity
         (decaying each frame so prediction slows to a stop)
    3. Tree FABRIK solving with latest bone lengths (constraint enforcement)

Keypoints not in any FABRIK tree are returned filter-only.
Missing keypoints are predicted for up to `max_prediction_frames` consecutive
frames, keeping the skeleton complete and FABRIK running during brief dropouts.

Usage:
    filt = RealtimeSkeletonFilter.create(
        skeleton=SkeletonDefinition.mediapipe_body(),
        prior=AnthropometricPrior.mediapipe_body(),
        config=RealtimeFilterConfig(),
    )

    for t, raw_3d_points in triangulated_stream:
        result = filt.process_frame(t=t, positions=raw_3d_points)
        # result.positions: all keypoints (observed + predicted)
        # result.predicted_names: which ones are extrapolated
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


@dataclass(frozen=True)
class FilterResult:
    """Result from the skeleton filter: positions plus prediction metadata."""

    # All keypoint positions — both freshly filtered and predicted from previous frames.
    positions: dict[str, np.ndarray]

    # Names of keypoints whose positions are predicted (not observed this frame).
    predicted_names: frozenset[str]


class RealtimeFilterConfig(BaseModel):
    """Tunable parameters for the realtime filtering pipeline."""

    # One Euro Filter params
    # min_cutoff: minimum cutoff frequency (Hz). Lower = more smoothing, higher = more responsive.
    min_cutoff: float = 0.005
    # beta: speed coefficient. Higher = less lag during fast motion, but more jitter at rest.
    beta: float = 0.3
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
    max_rejected_streak: int = 5

    # Prediction: how many consecutive frames to extrapolate a missing keypoint
    # using the One Euro filter's stored velocity before dropping it. Prevents
    # blinking during brief tracking dropouts. Set to 0 to disable prediction.
    max_prediction_frames: int = 15

    # Prediction: velocity decay per predicted frame. Each prediction step
    # multiplies the stored velocity by this factor, so extrapolation
    # decelerates to a stop. 0.0 = freeze, 1.0 = constant velocity.
    prediction_velocity_decay: float = 0.75


@dataclass
class RealtimeSkeletonFilter:
    """
    Frame-by-frame realtime skeleton filter with online bone length estimation.

    Handles partial keypoint data gracefully: keypoints missing from a frame
    are extrapolated using the One Euro filter's stored velocity for up to
    `max_prediction_frames` consecutive frames. The velocity decays each
    prediction step so the extrapolation slows to a stop.

    This keeps the skeleton complete during brief tracking dropouts, allowing
    FABRIK to keep running and preventing blinking in the output.

    Bone lengths are estimated online from observed inter-keypoint distances
    and blended with an anthropometric prior. The FABRIK solver uses the
    latest blended bone lengths each frame.

    FABRIK runs when all joints in the tree are present (including predicted).
    """

    skeleton: SkeletonDefinition
    config: RealtimeFilterConfig
    bone_estimator: BoneLengthEstimator
    fabrik_tree: FabrikTree = field(repr=False)
    _filters: dict[str, OneEuroFilter3D] = field(
        default_factory=dict, init=False, repr=False,
    )
    # Tracks how many consecutive frames each keypoint has been predicted.
    # Reset to 0 when a real observation arrives.
    _consecutive_predictions: dict[str, int] = field(
        default_factory=dict, init=False, repr=False,
    )
    # All keypoint names we've ever seen (so we know what to try predicting).
    _known_keypoints: set[str] = field(
        default_factory=set, init=False, repr=False,
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
        self._consecutive_predictions.clear()
        self._known_keypoints.clear()
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
    ) -> FilterResult:
        """
        Process one frame of triangulated 3D keypoint positions.

        Args:
            t: timestamp in seconds (must be strictly increasing across calls).
            positions: raw triangulated positions, mapping name -> (3,) array.
                       May be a subset of skeleton keypoints.

        Returns:
            FilterResult with filtered+constrained positions for all keypoints
            (including predicted ones) and the set of predicted keypoint names.
        """
        if not positions and not self._known_keypoints:
            return FilterResult(positions={}, predicted_names=frozenset())

        # --- Step 0: Feed the bone length estimator (only real observations) ---
        if positions:
            self.bone_estimator.observe(positions=positions)

        # --- Step 1: One Euro filter each present keypoint ---
        filtered: dict[str, np.ndarray] = {}
        predicted_names: set[str] = set()

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

            self._known_keypoints.add(name)
            self._consecutive_predictions[name] = 0

        # --- Step 1b: Predict missing keypoints using filter velocity ---
        if self.config.max_prediction_frames > 0:
            for name in self._known_keypoints:
                if name in filtered:
                    continue  # already have fresh data
                if name not in self._filters:
                    continue  # no filter to predict from

                streak = self._consecutive_predictions.get(name, 0)
                if streak >= self.config.max_prediction_frames:
                    continue  # exhausted prediction budget, drop this keypoint

                filtered[name] = self._filters[name].predict(
                    t=t,
                    velocity_decay=self.config.prediction_velocity_decay,
                )
                self._consecutive_predictions[name] = streak + 1
                predicted_names.add(name)

        # --- Step 2: Tree FABRIK with latest bone lengths ---
        if not self.fabrik_tree.nodes or not filtered:
            return FilterResult(
                positions=filtered,
                predicted_names=frozenset(predicted_names),
            )

        # Check if all FABRIK tree joints are present (including predicted)
        all_tree_joints_present = all(
            name in filtered for name in self.fabrik_tree.topo_order
        )

        if not all_tree_joints_present:
            # Can't run FABRIK with missing joints — return filter-only + predicted
            return FilterResult(
                positions=filtered,
                predicted_names=frozenset(predicted_names),
            )

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

        return FilterResult(
            positions=result,
            predicted_names=frozenset(predicted_names),
        )

    @property
    def current_bone_lengths(self) -> dict[str, float]:
        """Current blended bone length estimates."""
        return self.bone_estimator.current_lengths

    @property
    def current_confidence(self) -> dict[str, float]:
        """Current bone length estimation confidence (0->1) per bone."""
        return self.bone_estimator.current_confidence