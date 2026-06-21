"""
Real-time skeleton fitter with online segment length estimation.

Loads canonical anatomical models and tracker→canonical mappings once at
init, then runs per-frame::

    1. Map tracker keypoints → canonical landmark positions
    2. Update online segment-length statistics (Welford's algorithm)
    3. Blend Winter priors with observed lengths
    4. Run FABRIK for body and each hand independently

Follows the same ``load-once → numpy-hot-loop`` pattern as
``center_of_mass.py``.  No Pydantic, no YAML, no logging in the hot path.

Usage::

    fitter = RealtimeSkeletonFitter.create(height_mm=1750.0)
    for tracker_positions in stream:
        result = fitter.fit_frame(tracker_positions)
        # result.body_positions, result.left_hand_positions,
        # result.right_hand_positions are canonical-name-keyed
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from skellyforge.skellymodels.models.anatomical_structure import AnatomicalStructure
from skellyforge.skellymodels.models.tracking_model_info import (
    CanonicalBodyModelInfo,
    CanonicalHandModelInfo,
)
from skellytracker.trackers.base_tracker.tracker_mapping import TrackerMapping

from freemocap.core.tasks.mocap.skeleton_dewiggler.dewiggling_methods.fabrik_solver import (
    FabrikTree,
    solve_fabrik_tree,
)

# ---------------------------------------------------------------------------
# Paths to tracker mapping YAMLs (shipped with skellytracker package)
# ---------------------------------------------------------------------------

import skellytracker

_SKELLYTRACKER_TRACKERS_DIR = (
    Path(skellytracker.__file__).parent / "trackers"
)

_RTMPOSE_BODY_MAPPING_YAML = (
    _SKELLYTRACKER_TRACKERS_DIR / "rtmpose_tracker" / "names_and_connections" / "rtmpose_body_to_canonical_mapping.yaml"
)
_RTMPOSE_HAND_MAPPING_YAML = (
    _SKELLYTRACKER_TRACKERS_DIR / "rtmpose_tracker" / "names_and_connections" / "rtmpose_hand_to_canonical_mapping.yaml"
)

# ---------------------------------------------------------------------------
# Segment-length tracker (Welford's online algorithm)
# ---------------------------------------------------------------------------


@dataclass
class _WelfordTracker:
    """Online mean/variance for a single bone — O(1) memory, no buffers."""

    prior: float = 0.0
    count: int = 0
    mean: float = 0.0
    M2: float = 0.0  # sum of squared differences from mean

    def observe(self, value: float) -> None:
        """Update running statistics with a new observation."""
        self.count += 1
        delta = value - self.mean
        self.mean += delta / self.count
        delta2 = value - self.mean
        self.M2 += delta * delta2

    @property
    def variance(self) -> float:
        """Sample variance (requires count >= 2)."""
        return self.M2 / (self.count - 1) if self.count > 1 else 0.0

    @property
    def std(self) -> float:
        """Sample standard deviation."""
        return np.sqrt(self.variance) if self.count > 1 else 0.0

    def blended_length(
        self,
        *,
        min_samples: int = 100,
        cv_sensitivity: float = 10.0,
    ) -> float:
        """Confidence-weighted blend of prior and observed mean.

        Confidence = count_factor × consistency_factor where::

            count_factor      = clamp(n / min_samples, 0, 1)
            consistency_factor = 1 / (1 + sensitivity × CV)
            CV                 = std / mean  (coefficient of variation)

        Lower CV → tighter measurements → higher confidence.
        """
        if self.count == 0:
            return self.prior

        count_factor = min(1.0, self.count / min_samples)

        if self.mean > 1e-9:
            cv = self.std / self.mean
        else:
            cv = float("inf")

        consistency_factor = 1.0 / (1.0 + cv_sensitivity * cv)
        confidence = count_factor * consistency_factor

        return self.prior * (1.0 - confidence) + self.mean * confidence


# ---------------------------------------------------------------------------
# Per-frame result
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class SkeletonFittingResult:
    """FABRIK-fitted skeleton positions for one frame.

    All positions use canonical landmark names.  Trees with insufficient
    data (missing root, empty targets) are returned as empty dicts.
    """

    body_positions: dict[str, np.ndarray]
    left_hand_positions: dict[str, np.ndarray]
    right_hand_positions: dict[str, np.ndarray]

    # Current blended bone lengths used for the FABRIK solve
    body_bone_lengths: dict[str, float]
    left_hand_bone_lengths: dict[str, float]
    right_hand_bone_lengths: dict[str, float]


# ---------------------------------------------------------------------------
# Torso/spine/head bone ratios — the canonical anatomical model only provides
# limb bone ratios. Without these, 12/26 FABRIK tree bones get zero-length
# priors and the skeleton collapses to a point. Sources: Winter 2009,
# Drillis & Contini 1966.
# ---------------------------------------------------------------------------
_TORSO_BONE_RATIOS: dict[str, float] = {
    # Hip width (bi-iliac breadth / 2)
    "hips_center->left_hip":            0.096,
    "hips_center->right_hip":           0.096,
    # Trunk — split ~50/50
    "hips_center->trunk_center":        0.144,
    "trunk_center->neck_center":        0.144,
    # Shoulder width (bi-acromial breadth / 2)
    "neck_center->left_shoulder":       0.130,
    "neck_center->right_shoulder":      0.130,
    # Head + neck
    "neck_center->head_center":         0.130,
    # Face features (approximate)
    "head_center->nose":                0.040,
    "head_center->left_eye":            0.020,
    "head_center->right_eye":           0.020,
    "head_center->left_ear":            0.060,
    "head_center->right_ear":           0.060,
}


# ---------------------------------------------------------------------------
# RealtimeSkeletonFitter
# ---------------------------------------------------------------------------


@dataclass
class RealtimeSkeletonFitter:
    """Per-frame skeleton fitting with online segment length estimation.

    Created once at aggregator init.  The ``fit_frame`` method is the
    per-frame hot path — no allocations beyond what numpy/FABRIK need.
    """

    # Canonical anatomical structures (loaded once, read-only)
    _body_anatomy: AnatomicalStructure = field(repr=False)
    _hand_anatomy: AnatomicalStructure = field(repr=False)

    # Tracker → canonical mappings
    _body_mapping: TrackerMapping = field(repr=False)
    _hand_mapping_r: TrackerMapping = field(repr=False)
    _hand_mapping_l: TrackerMapping = field(repr=False)

    # FABRIK trees (frozen topology)
    _body_tree: FabrikTree = field(repr=False)
    _hand_tree: FabrikTree = field(repr=False)

    # Per-bone segment-length trackers
    _body_trackers: dict[str, _WelfordTracker] = field(repr=False)
    _hand_trackers_r: dict[str, _WelfordTracker] = field(repr=False)
    _hand_trackers_l: dict[str, _WelfordTracker] = field(repr=False)

    # Config (all lengths in mm — keypoint-coordinate units)
    height_mm: float = 1750.0
    fabrik_tolerance: float = 0.1  # mm — FABRIK convergence threshold
    fabrik_max_iterations: int = 20
    min_samples: int = 100
    cv_sensitivity: float = 10.0

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        height_mm: float = 1750.0,
        fabrik_tolerance: float = 0.1,
        fabrik_max_iterations: int = 20,
        min_samples: int = 100,
        cv_sensitivity: float = 10.0,
    ) -> "RealtimeSkeletonFitter":
        """Load canonical models and tracker mappings.

        Parameters
        ----------
        height_mm : float
            Subject standing height in mm (keypoint-coordinate units).
            Bone-length priors are scaled by this value.
        fabrik_tolerance : float
            FABRIK convergence threshold (mm).
        fabrik_max_iterations : int
            Maximum FABRIK forward/backward passes per frame.
        min_samples : int
            Number of observations for full confidence in the
            observed mean.
        cv_sensitivity : float
            How strongly the coefficient of variation penalizes
            confidence.  Higher = less trust in noisy measurements.
        """
        # ---- Canonical models ----
        body_info = CanonicalBodyModelInfo()
        body_anatomy = AnatomicalStructure.from_model_info(body_info, "body")

        hand_info = CanonicalHandModelInfo()
        hand_anatomy = AnatomicalStructure.from_model_info(hand_info, "hand")

        # ---- Tracker mappings (RTMPose — the realtime pipeline tracker) ----
        body_mapping = TrackerMapping.from_yaml(_RTMPOSE_BODY_MAPPING_YAML)
        hand_mapping_r = TrackerMapping.from_yaml(
            _RTMPOSE_HAND_MAPPING_YAML, prefix="right_hand_"
        )
        hand_mapping_l = TrackerMapping.from_yaml(
            _RTMPOSE_HAND_MAPPING_YAML, prefix="left_hand_"
        )

        # ---- FABRIK trees from canonical joint hierarchies ----
        if body_anatomy.joint_hierarchy is None:
            raise ValueError("Canonical body model has no joint_hierarchy")
        body_tree = FabrikTree.from_joint_hierarchy(
            joint_hierarchy=body_anatomy.joint_hierarchy,
        )

        if hand_anatomy.joint_hierarchy is None:
            raise ValueError("Canonical hand model has no joint_hierarchy")
        hand_tree = FabrikTree.from_joint_hierarchy(
            joint_hierarchy=hand_anatomy.joint_hierarchy,
        )

        # ---- Per-bone Welford trackers seeded with Winter priors ----
        body_trackers = cls._build_trackers(
            tree=body_tree,
            bone_length_ratios=body_anatomy.bone_length_ratios,
            height_mm=height_mm,
        )
        hand_trackers_r = cls._build_trackers(
            tree=hand_tree,
            bone_length_ratios=hand_anatomy.bone_length_ratios,
            height_mm=height_mm,
        )
        hand_trackers_l = cls._build_trackers(
            tree=hand_tree,
            bone_length_ratios=hand_anatomy.bone_length_ratios,
            height_mm=height_mm,
        )

        return cls(
            _body_anatomy=body_anatomy,
            _hand_anatomy=hand_anatomy,
            _body_mapping=body_mapping,
            _hand_mapping_r=hand_mapping_r,
            _hand_mapping_l=hand_mapping_l,
            _body_tree=body_tree,
            _hand_tree=hand_tree,
            _body_trackers=body_trackers,
            _hand_trackers_r=hand_trackers_r,
            _hand_trackers_l=hand_trackers_l,
            height_mm=height_mm,
            fabrik_tolerance=fabrik_tolerance,
            fabrik_max_iterations=fabrik_max_iterations,
            min_samples=min_samples,
            cv_sensitivity=cv_sensitivity,
        )

    @staticmethod
    def _build_trackers(
        *,
        tree: FabrikTree,
        bone_length_ratios: Optional[dict[str, float]],
        height_mm: float,
    ) -> dict[str, _WelfordTracker]:
        """Create per-bone Welford trackers seeded with Winter priors (mm).

        Limb bones use ratios from the canonical anatomical model.
        Torso/spine/head bones use ``_TORSO_BONE_RATIOS`` because the
        canonical model only provides limb ratios.
        """
        trackers: dict[str, _WelfordTracker] = {}
        for bone_key in tree.bone_keys:
            prior_ratio = 0.0
            if bone_length_ratios is not None:
                prior_ratio = bone_length_ratios.get(bone_key, 0.0)
            if prior_ratio == 0.0:
                prior_ratio = _TORSO_BONE_RATIOS.get(bone_key, 0.0)
            if prior_ratio == 0.0:
                # Last resort: 1% of height (~17.5 mm) prevents zero-length
                # bones that would collapse the skeleton.
                prior_ratio = 0.01
            prior_length = prior_ratio * height_mm
            trackers[bone_key] = _WelfordTracker(prior=prior_length)
        return trackers

    # ------------------------------------------------------------------
    # Per-frame hot path
    # ------------------------------------------------------------------

    def fit_frame(
        self,
        tracker_positions: dict[str, np.ndarray],
    ) -> SkeletonFittingResult:
        """Fit skeleton to one frame of tracker keypoints.

        Parameters
        ----------
        tracker_positions : dict of str → (3,) ndarray
            Raw 3D keypoint positions with tracker-specific names
            (RTMPose convention: ``nose``, ``left_shoulder``,
            ``right_hand_root``, ``left_hand_thumb1``, …).

        Returns
        -------
        SkeletonFittingResult
            FABRIK-fitted positions in canonical naming.  Trees with
            insufficient data return empty dicts.
        """
        # ---- 1. Map tracker → canonical ----
        canonical_body = self._body_mapping.apply(tracker_positions)
        canonical_rhand = self._hand_mapping_r.apply(tracker_positions)
        canonical_lhand = self._hand_mapping_l.apply(tracker_positions)

        # ---- 2. Observe segment lengths ----
        self._observe_tree(canonical_body, self._body_tree, self._body_trackers)
        self._observe_tree(canonical_rhand, self._hand_tree, self._hand_trackers_r)
        self._observe_tree(canonical_lhand, self._hand_tree, self._hand_trackers_l)

        # ---- 3. Current blended lengths ----
        body_lengths = {
            bk: t.blended_length(
                min_samples=self.min_samples,
                cv_sensitivity=self.cv_sensitivity,
            )
            for bk, t in self._body_trackers.items()
        }
        rhand_lengths = {
            bk: t.blended_length(
                min_samples=self.min_samples,
                cv_sensitivity=self.cv_sensitivity,
            )
            for bk, t in self._hand_trackers_r.items()
        }
        lhand_lengths = {
            bk: t.blended_length(
                min_samples=self.min_samples,
                cv_sensitivity=self.cv_sensitivity,
            )
            for bk, t in self._hand_trackers_l.items()
        }

        # ---- 4. FABRIK solve ----
        body_fitted = self._try_solve(
            targets=canonical_body,
            tree=self._body_tree,
            bone_lengths=body_lengths,
        )
        rhand_fitted = self._try_solve(
            targets=canonical_rhand,
            tree=self._hand_tree,
            bone_lengths=rhand_lengths,
        )
        lhand_fitted = self._try_solve(
            targets=canonical_lhand,
            tree=self._hand_tree,
            bone_lengths=lhand_lengths,
        )

        return SkeletonFittingResult(
            body_positions=body_fitted,
            left_hand_positions=lhand_fitted,
            right_hand_positions=rhand_fitted,
            body_bone_lengths=body_lengths,
            left_hand_bone_lengths=lhand_lengths,
            right_hand_bone_lengths=rhand_lengths,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _observe_tree(
        canonical_positions: dict[str, np.ndarray],
        tree: FabrikTree,
        trackers: dict[str, _WelfordTracker],
    ) -> None:
        """Feed observed bone lengths into running statistics."""
        for bone_key in tree.bone_keys:
            parent_name, child_name = bone_key.split("->", 1)
            parent_pos = canonical_positions.get(parent_name)
            child_pos = canonical_positions.get(child_name)
            if parent_pos is None or child_pos is None:
                continue
            length = float(np.linalg.norm(
                np.asarray(parent_pos) - np.asarray(child_pos)
            ))
            if length > 0.0:
                trackers[bone_key].observe(length)

    def _try_solve(
        self,
        *,
        targets: dict[str, np.ndarray],
        tree: FabrikTree,
        bone_lengths: dict[str, float],
    ) -> dict[str, np.ndarray]:
        """Run FABRIK if all tree joints are present, else return empty."""
        if not tree.nodes:
            return {}

        # Need at minimum the root joints present
        if not any(root in targets for root in tree.root_names):
            return {}

        # Build target dict with what we have; missing joints get
        # the nearest-available ancestor's position as a fallback.
        fabrik_targets: dict[str, np.ndarray] = {}

        # Walk topo order (roots first) and fill missing with parent
        for name in tree.topo_order:
            if name in targets:
                fabrik_targets[name] = np.asarray(targets[name], dtype=np.float64)
            else:
                node = tree.nodes[name]
                if node.parent_name is not None and node.parent_name in fabrik_targets:
                    fabrik_targets[name] = fabrik_targets[node.parent_name].copy()
                else:
                    # Can't place this joint — skip it and propagate later
                    continue

        if not fabrik_targets:
            return {}

        # Ensure bone_lengths covers all bones in the tree
        for bone_key in tree.bone_keys:
            if bone_key not in bone_lengths:
                bone_lengths[bone_key] = 50.0  # mm fallback — should never trigger now

        return solve_fabrik_tree(
            targets=fabrik_targets,
            tree=tree,
            bone_lengths=bone_lengths,
            tolerance=self.fabrik_tolerance,
            max_iterations=self.fabrik_max_iterations,
        )

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def body_bone_statistics(self) -> dict[str, dict[str, float]]:
        """Per-bone statistics for the body tree."""
        return {
            bk: {"count": t.count, "mean": t.mean, "std": t.std,
                 "prior": t.prior, "blended": t.blended_length(
                     min_samples=self.min_samples,
                     cv_sensitivity=self.cv_sensitivity,
                 )}
            for bk, t in self._body_trackers.items()
        }
