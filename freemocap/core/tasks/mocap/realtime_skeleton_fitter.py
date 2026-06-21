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
        min_samples: int = 20,
        cv_sensitivity: float = 2.0,
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
    # Hip half-width. hips_center (mean of hips) and hip joints are at the
    # same height, so this is just the lateral distance ≈ 100 mm.
    "hips_center->left_hip":            0.057,
    "hips_center->right_hip":           0.057,
    # Trunk: hips_center (≈0.53 H) → trunk_center (≈0.675 H)
    "hips_center->trunk_center":        0.145,
    # Trunk: trunk_center (≈0.675 H) → neck_center / C7 (≈0.84 H)
    "trunk_center->neck_center":        0.165,
    # Neck → shoulder 3D distance. neck_center settles at C7 (~1442 mm);
    # shoulder target at acromion (~1400 mm, 200 mm lateral).
    # 3D Euclidean = √(200² + (1442−1400)²) ≈ 204 mm.
    "neck_center->left_shoulder":       0.117,
    "neck_center->right_shoulder":      0.117,
    # Neck: C7 (≈0.84 H) → head_center / mid-ear (≈0.93 H)
    "neck_center->head_center":         0.090,
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


def _build_hand_mapping(yaml_path: Path, *, side: str) -> tuple[TrackerMapping, dict[str, str]]:
    """Build a hand tracker→canonical mapping AND a canonical→schema-name reverse map.

    Two different naming conventions collide here:

    1. **Native RTMPose names** — what the tracker detector outputs.
       Wrist = ``right_hand_root``, but fingers = ``right_thumb1``
       (no ``_hand_``).  Historically inconsistent.

    2. **Schema names** — what the composed tracker schema and the
       frontend ConnectionRenderer expect.  The schema YAML composes
       hands with ``prefix: "right_hand_"``, producing names like
       ``right_hand_root``, ``right_hand_thumb1``, etc.

    The *mapping* must look up native names (what the tracker outputs).
    The *reverse map* must produce schema names (what the frontend expects).

    Returns (mapping, reverse_map) where mapping produces canonical names
    and reverse_map goes canonical→schema-name.
    """
    import yaml
    with open(yaml_path, "r") as fh:
        raw = yaml.safe_load(fh)
    native_entries: dict[str, str] = {}
    schema_reverse: dict[str, str] = {}
    for canonical_name, relative_name in raw.items():
        if canonical_name == "wrist":
            # Wrist: native = right_hand_root, schema = right_hand_root (same)
            native_entries[canonical_name] = f"{side}_hand_{relative_name}"
            schema_reverse[canonical_name] = f"{side}_hand_{relative_name}"
        else:
            # Fingers: native = right_thumb1, schema = right_hand_thumb1
            native_entries[canonical_name] = f"{side}_{relative_name}"
            schema_reverse[canonical_name] = f"{side}_hand_{relative_name}"
    return TrackerMapping(entries=native_entries, prefix=""), schema_reverse


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
    _body_tree: FabrikTree = field(repr=False)       # full body (for observation)
    _torso_tree: FabrikTree = field(repr=False)      # torso-only (for solving)
    _hand_tree: FabrikTree = field(repr=False)

    # Per-bone segment-length trackers
    _body_trackers: dict[str, _WelfordTracker] = field(repr=False)
    _hand_trackers_r: dict[str, _WelfordTracker] = field(repr=False)
    _hand_trackers_l: dict[str, _WelfordTracker] = field(repr=False)

    # Hand canonical → tracker name reverse maps (built once, used per-frame)
    _hand_name_to_tracker_r: dict[str, str] = field(default_factory=dict, repr=False)
    _hand_name_to_tracker_l: dict[str, str] = field(default_factory=dict, repr=False)

    # Config (all lengths in mm — keypoint-coordinate units)
    height_mm: float = 1750.0
    fabrik_tolerance: float = 0.1  # mm — FABRIK convergence threshold
    fabrik_max_iterations: int = 20
    min_samples: int = 20           # frames for full count confidence (~0.7s at 30fps)
    cv_sensitivity: float = 2.0     # lower = trust observed measurements sooner

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
        min_samples: int = 20,
        cv_sensitivity: float = 2.0,
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
            Number of observations for full count confidence.
            Default 20 → ~0.7 s at 30 fps.
        cv_sensitivity : float
            How strongly the coefficient of variation penalizes
            confidence.  Lower = trust observed measurements sooner.
            Default 2.0 → with CV=0.1, max confidence ~83%.
        """
        # ---- Canonical models ----
        body_info = CanonicalBodyModelInfo()
        body_anatomy = AnatomicalStructure.from_model_info(body_info, "body")

        hand_info = CanonicalHandModelInfo()
        hand_anatomy = AnatomicalStructure.from_model_info(hand_info, "hand")

        # ---- Tracker mappings (RTMPose — the realtime pipeline tracker) ----
        body_mapping = TrackerMapping.from_yaml(_RTMPOSE_BODY_MAPPING_YAML)
        # RTMPose hand naming is inconsistent: wrist = "right_hand_root"
        # (has `_hand_`) but every finger = "right_thumb1" (no `_hand_`).
        # The composed schema uses `right_hand_` prefix on everything.
        # _build_hand_mapping returns (native_name_mapping, schema_name_reverse_map).
        hand_mapping_r, hand_name_to_tracker_r = _build_hand_mapping(
            _RTMPOSE_HAND_MAPPING_YAML, side="right",
        )
        hand_mapping_l, hand_name_to_tracker_l = _build_hand_mapping(
            _RTMPOSE_HAND_MAPPING_YAML, side="left",
        )

        # ---- FABRIK trees ----
        # Full body tree (for bone length observation of limb bones only).
        if body_anatomy.joint_hierarchy is None:
            raise ValueError("Canonical body model has no joint_hierarchy")
        body_tree = FabrikTree.from_joint_hierarchy(
            joint_hierarchy=body_anatomy.joint_hierarchy,
        )

        # Torso-only tree for FABRIK solving.  Arms and legs are excluded
        # because FABRIK linear chains ignore tracker targets on internal
        # nodes (shoulder, elbow, knee).  Limb positions pass through
        # directly from the 1:1 tracker→canonical mapping.
        _torso_hierarchy: dict[str, list[str]] = {
            "hips_center":   ["left_hip", "right_hip", "trunk_center"],
            "trunk_center":  ["neck_center"],
            "neck_center":   ["left_shoulder", "right_shoulder", "head_center"],
            "head_center":   ["nose", "left_eye", "right_eye", "left_ear", "right_ear"],
        }
        _torso_tree = FabrikTree.from_joint_hierarchy(
            joint_hierarchy=_torso_hierarchy,
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
            _torso_tree=_torso_tree,
            _hand_tree=hand_tree,
            _body_trackers=body_trackers,
            _hand_trackers_r=hand_trackers_r,
            _hand_trackers_l=hand_trackers_l,
            _hand_name_to_tracker_r=hand_name_to_tracker_r,
            _hand_name_to_tracker_l=hand_name_to_tracker_l,
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
        # The full body tree includes arms and legs as linear chains.
        # In FABRIK, only leaves and roots snap to targets; intermediate
        # joints (shoulder, elbow, hip, knee, ankle) are positioned solely
        # by bone-length constraints from the leaf, ignoring their tracker
        # targets. This causes drift.
        #
        # Fix: run FABRIK on a torso-only tree (spine + head + face).
        # Limb positions come directly from the tracker (1:1 mapping).
        body_fitted = self._try_solve_torso(
            targets=canonical_body,
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

        # ---- 5. Convert hand canonical names → tracker names ----
        # The FABRIK trees produce canonical names (wrist, thumb_cmc, …).
        # The frontend ConnectionRenderer expects tracker names with side
        # prefix (left_hand_root, right_hand_thumb1, …). Reverse-map so
        # the skeleton dict keys match what the frontend looks up.
        lhand_tracker: dict[str, np.ndarray] = {}
        for cname, pos in lhand_fitted.items():
            tname = self._hand_name_to_tracker_l.get(cname)
            if tname is not None:
                lhand_tracker[tname] = pos
        rhand_tracker: dict[str, np.ndarray] = {}
        for cname, pos in rhand_fitted.items():
            tname = self._hand_name_to_tracker_r.get(cname)
            if tname is not None:
                rhand_tracker[tname] = pos

        return SkeletonFittingResult(
            body_positions=body_fitted,
            left_hand_positions=lhand_tracker,
            right_hand_positions=rhand_tracker,
            body_bone_lengths=body_lengths,
            left_hand_bone_lengths=lhand_lengths,
            right_hand_bone_lengths=rhand_lengths,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    # Joints whose canonical position is derived (computed as a mean of
    # other points, not directly tracked). Bones where the parent is a
    # derived joint have observed lengths that don't match the FABRIK
    # tree geometry. E.g. canonical neck_center is at shoulder height
    # (mean of shoulders) but the FABRIK tree places it at C7 level.
    # Skip observation for these — they stay at their anthropometric prior.
    _DERIVED_JOINTS: frozenset[str] = frozenset({
        "hips_center", "neck_center", "trunk_center", "head_center",
    })

    @staticmethod
    def _observe_tree(
        canonical_positions: dict[str, np.ndarray],
        tree: FabrikTree,
        trackers: dict[str, _WelfordTracker],
    ) -> None:
        """Feed observed bone lengths into running statistics.

        Only bones whose parent is a directly-tracked landmark (not a
        derived midpoint) contribute observations. Bones hanging from
        derived joints stay at their anthropometric prior.
        """
        derived = RealtimeSkeletonFitter._DERIVED_JOINTS
        for bone_key in tree.bone_keys:
            parent_name, child_name = bone_key.split("->", 1)
            if parent_name in derived:
                continue  # canonical parent position doesn't match tree geometry
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

    # Joints that are in the full body tree but NOT in the torso tree —
    # these are limb joints whose positions pass through directly from
    # the tracker (1:1 mapping).  FABRIK linear chains ignore tracker
    # targets on internal nodes (shoulder, knee, etc.), so we bypass
    # FABRIK for limbs entirely.
    _LIMB_ONLY_JOINTS: frozenset[str] = frozenset({
        "left_elbow", "left_wrist",
        "right_elbow", "right_wrist",
        "left_knee", "left_ankle",
        "right_knee", "right_ankle",
        "left_heel", "left_big_toe", "left_small_toe",
        "right_heel", "right_big_toe", "right_small_toe",
    })

    def _try_solve_torso(
        self,
        *,
        targets: dict[str, np.ndarray],
        bone_lengths: dict[str, float],
    ) -> dict[str, np.ndarray]:
        """FABRIK-solve the torso tree, then merge limb positions directly
        from the tracker targets (bypassing FABRIK for linear limb chains).
        """
        # 1. FABRIK solve for torso joints
        torso_fitted = self._try_solve(
            targets=targets,
            tree=self._torso_tree,
            bone_lengths=bone_lengths,
        )

        # 2. Merge limb positions directly from tracker targets
        result = dict(torso_fitted)
        for name in self._LIMB_ONLY_JOINTS:
            if name in targets:
                result[name] = np.asarray(targets[name], dtype=np.float64)

        return result

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
