"""
Real-time skeleton fitter — measure bone lengths from keypoints, run FABRIK, blend.

Loads canonical anatomical models and tracker→canonical mappings once at
init, then runs per-frame::

    1. Map tracker keypoints → canonical landmark positions
    2. Measure bone lengths from the current frame's keypoint distances
    3. Clamp measured lengths to anatomical prior ±20%
    4. Warm-start FABRIK from the previous frame's solution
    5. Run ONE FABRIK solve per tree
    6. Blend result toward keypoint targets
    7. Return fitted skeleton

No online estimation, no integral correctors, no refinement passes,
no convergence tracking — just: measure → clamp → FABRIK → blend.

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

import time
from dataclasses import dataclass, field
from pathlib import Path

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
# Derived center joints — computed landmarks (means of tracked keypoints)
# rather than directly tracked.  These get extra post-FABRIK blending toward
# their tracker targets to reduce jitter amplification.
# ---------------------------------------------------------------------------

_CENTER_JOINT_NAMES: frozenset[str] = frozenset({
    "hips_center",
    "trunk_center",
    "neck_center",
    "head_center",
})


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

    # Bone lengths used for the FABRIK solve (measured from keypoints,
    # clamped to anatomical prior)
    body_bone_lengths: dict[str, float]
    left_hand_bone_lengths: dict[str, float]
    right_hand_bone_lengths: dict[str, float]


# ---------------------------------------------------------------------------
# Helpers (module-level, no allocations in the hot path beyond the calls)
# ---------------------------------------------------------------------------


def _build_hand_mapping(yaml_path: Path, *, side: str) -> tuple[TrackerMapping, dict[str, str]]:
    """Build a hand tracker→canonical mapping and a canonical→tracker reverse map.

    RTMPose composes hand landmarks with a uniform ``{side}_hand_`` prefix
    (``right_hand_root``, ``right_hand_thumb1``, …), so the mapping just strips
    that prefix to match the unprefixed entries in the mapping YAML
    (``root``, ``thumb1``, …) via ``TrackerMapping``'s ``prefix`` feature.

    Returns (mapping, reverse_map):
      - ``mapping.apply(tracker_positions)`` → canonical-named positions.
      - ``reverse_map`` converts canonical landmark names back to tracker
        names (``thumb_cmc`` → ``right_hand_thumb1``) so fitted hand points
        key into the frontend's RTMPose hand schema.
    """
    import yaml
    with open(yaml_path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    prefix = f"{side}_hand_"
    mapping = TrackerMapping(entries=raw, prefix=prefix)
    reverse_map = {canonical: f"{prefix}{relative}" for canonical, relative in raw.items()}
    return mapping, reverse_map


# ---------------------------------------------------------------------------
# RealtimeSkeletonFitter
# ---------------------------------------------------------------------------


@dataclass
class RealtimeSkeletonFitter:
    """Per-frame skeleton fitting: measure → clamp → FABRIK → blend.

    Created once at aggregator init.  The ``fit_frame`` method is the
    per-frame hot path — no allocations beyond what numpy/FABRIK need.
    No online estimation state: bone lengths are measured fresh from each
    frame's keypoints and clamped to the static anatomical prior.
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

    # Static anatomical bone-length priors (dict[str, float])
    # Computed once in create() from canonical ratios × height_mm.
    # Used as fallback when a bone's endpoints aren't observed, and as
    # the clamp center when bone_length_clamp_ratio > 0.
    _static_body_priors: dict[str, float] = field(repr=False)
    _static_hand_priors: dict[str, float] = field(repr=False)

    # Hand canonical → tracker name reverse maps (built once, used per-frame)
    _hand_name_to_tracker_r: dict[str, str] = field(default_factory=dict, repr=False)
    _hand_name_to_tracker_l: dict[str, str] = field(default_factory=dict, repr=False)

    # Previous frame's FABRIK solutions — warm-start for the next frame.
    # None until the first solve completes.
    _prev_body_solution: dict[str, np.ndarray] | None = field(default=None, repr=False, init=False)
    _prev_rhand_solution: dict[str, np.ndarray] | None = field(default=None, repr=False, init=False)
    _prev_lhand_solution: dict[str, np.ndarray] | None = field(default=None, repr=False, init=False)

    # Per-tree timing (ms) for the most recent fit_frame() call.
    # Populated when log_timing is enabled; read by aggregator
    # for the fine-grained timing report.
    last_body_time_ms: float = field(default=0.0, repr=False, init=False)
    last_rhand_time_ms: float = field(default=0.0, repr=False, init=False)
    last_lhand_time_ms: float = field(default=0.0, repr=False, init=False)

    # Config (all lengths in mm — keypoint-coordinate units)
    height_mm: float = 1750.0
    fabrik_tolerance: float = 20.0   # mm — convergence threshold
    fabrik_max_iterations: int = 10  # max forward/backward passes per solve
    center_blend_factor: float = 0.4  # extra snap for center joints post-FABRIK
    bone_length_clamp_ratio: float = 0.2  # clamp measured lengths to prior ±20%
    keypoint_blend_factor: float = 0.6  # global post-solve pull toward keypoints

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        height_mm: float = 1750.0,
        fabrik_tolerance: float = 20.0,
        fabrik_max_iterations: int = 10,
        center_blend_factor: float = 0.4,
        bone_length_clamp_ratio: float = 0.2,
        keypoint_blend_factor: float = 0.6,
    ) -> "RealtimeSkeletonFitter":
        """Load canonical models and tracker mappings.

        Parameters
        ----------
        height_mm : float
            Subject standing height in mm (keypoint-coordinate units).
            Bone-length priors are scaled by this value.
        fabrik_tolerance : float
            FABRIK convergence threshold (mm).  20 mm = 2 cm.
        fabrik_max_iterations : int
            Maximum FABRIK forward/backward passes per solve.
        center_blend_factor : float
            Post-FABRIK blend factor for derived center joints
            (hips_center, neck_center, head_center).  0 = no blend
            (pure FABRIK), 1 = snap to tracker target.  Default 0.4.
        bone_length_clamp_ratio : float
            Clamp measured bone lengths to anatomical prior ± this ratio.
            0.2 = ±20%.  0 = no clamp.
        keypoint_blend_factor : float
            Post-solve global blend toward raw keypoint targets.
            0.6 = 60% keypoint, 40% FABRIK.
        """
        # ---- Canonical models ----
        body_info = CanonicalBodyModelInfo()
        body_anatomy = AnatomicalStructure.from_model_info(body_info, "body")

        hand_info = CanonicalHandModelInfo()
        hand_anatomy = AnatomicalStructure.from_model_info(hand_info, "hand")

        # ---- Tracker mappings (RTMPose — the realtime pipeline tracker) ----
        body_mapping = TrackerMapping.from_yaml(_RTMPOSE_BODY_MAPPING_YAML)
        hand_mapping_r, hand_name_to_tracker_r = _build_hand_mapping(
            _RTMPOSE_HAND_MAPPING_YAML, side="right",
        )
        hand_mapping_l, hand_name_to_tracker_l = _build_hand_mapping(
            _RTMPOSE_HAND_MAPPING_YAML, side="left",
        )

        # ---- FABRIK trees ----
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

        # ---- Static anatomical priors (ratios × height, computed once) ----
        body_priors = cls._build_static_priors(
            tree=body_tree,
            bone_length_ratios=body_anatomy.bone_length_ratios,
            height_mm=height_mm,
        )
        hand_priors = cls._build_static_priors(
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
            _static_body_priors=body_priors,
            _static_hand_priors=hand_priors,
            _hand_name_to_tracker_r=hand_name_to_tracker_r,
            _hand_name_to_tracker_l=hand_name_to_tracker_l,
            height_mm=height_mm,
            fabrik_tolerance=fabrik_tolerance,
            fabrik_max_iterations=fabrik_max_iterations,
            center_blend_factor=center_blend_factor,
            bone_length_clamp_ratio=bone_length_clamp_ratio,
            keypoint_blend_factor=keypoint_blend_factor,
        )

    @staticmethod
    def _build_static_priors(
        *,
        tree: FabrikTree,
        bone_length_ratios: dict[str, float] | None,
        height_mm: float,
    ) -> dict[str, float]:
        """Compute one-time anatomical bone lengths from ratios × height.

        Every bone in the tree must have a ratio in the canonical model's
        ``bone_length_ratios``.  A missing or non-positive ratio is a model
        error: fail loudly.
        """
        if bone_length_ratios is None:
            raise ValueError(
                "Canonical model has no bone_length_ratios — cannot compute "
                "anatomical priors (is skellyforge installed/synced?)."
            )
        priors: dict[str, float] = {}
        for bone_key in tree.bone_keys:
            ratio = bone_length_ratios.get(bone_key)
            if ratio is None or ratio <= 0.0:
                raise ValueError(
                    f"No positive bone-length ratio for '{bone_key}' in the "
                    f"canonical model — every tree bone needs one."
                )
            priors[bone_key] = ratio * height_mm
        return priors

    # ------------------------------------------------------------------
    # Per-frame hot path
    # ------------------------------------------------------------------

    def fit_frame(
        self,
        tracker_positions: dict[str, np.ndarray],
        *,
        log_timing: bool = False,
    ) -> SkeletonFittingResult:
        """Fit skeleton to one frame of tracker keypoints.

        Parameters
        ----------
        tracker_positions : dict of str → (3,) ndarray
            Raw 3D keypoint positions with tracker-specific names
            (RTMPose convention: ``nose``, ``left_shoulder``,
            ``right_hand_root``, ``left_hand_thumb1``, …).
        log_timing : bool
            If True, populate ``last_body_time_ms``, ``last_rhand_time_ms``,
            ``last_lhand_time_ms`` for the pipeline timing report.

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

        # ---- 2. Measure bone lengths from current keypoints ----
        body_lengths = _measure_lengths(
            canonical_body, self._body_tree, self._static_body_priors,
        )
        rhand_lengths = _measure_lengths(
            canonical_rhand, self._hand_tree, self._static_hand_priors,
        )
        lhand_lengths = _measure_lengths(
            canonical_lhand, self._hand_tree, self._static_hand_priors,
        )

        # ---- 3. Clamp to anatomical prior ± ratio ----
        if self.bone_length_clamp_ratio > 0.0:
            body_lengths = _clamp_to_prior(
                body_lengths, self._static_body_priors, self.bone_length_clamp_ratio,
            )
            rhand_lengths = _clamp_to_prior(
                rhand_lengths, self._static_hand_priors, self.bone_length_clamp_ratio,
            )
            lhand_lengths = _clamp_to_prior(
                lhand_lengths, self._static_hand_priors, self.bone_length_clamp_ratio,
            )

        # ---- 4. Warm-start positions (translate prev solution to current root) ----
        body_initial = _warm_start_positions(
            prev_solution=self._prev_body_solution,
            targets=canonical_body,
            root_names=("hips_center",),
        )
        rhand_initial = _warm_start_positions(
            prev_solution=self._prev_rhand_solution,
            targets=canonical_rhand,
            root_names=("wrist",),
        )
        lhand_initial = _warm_start_positions(
            prev_solution=self._prev_lhand_solution,
            targets=canonical_lhand,
            root_names=("wrist",),
        )

        # ---- 5. FABRIK solve + post-blend (one solve per tree) ----
        t_body_start = time.perf_counter() if log_timing else 0.0
        body_fitted = _solve_and_blend(
            targets=canonical_body,
            tree=self._body_tree,
            bone_lengths=body_lengths,
            tolerance=self.fabrik_tolerance,
            max_iterations=self.fabrik_max_iterations,
            initial_positions=body_initial,
            keypoint_blend_factor=self.keypoint_blend_factor,
            center_blend_factor=self.center_blend_factor,
        )
        if log_timing:
            self.last_body_time_ms = (time.perf_counter() - t_body_start) * 1e3

        t_rhand_start = time.perf_counter() if log_timing else 0.0
        rhand_fitted = _solve_and_blend(
            targets=canonical_rhand,
            tree=self._hand_tree,
            bone_lengths=rhand_lengths,
            tolerance=self.fabrik_tolerance,
            max_iterations=self.fabrik_max_iterations,
            initial_positions=rhand_initial,
            keypoint_blend_factor=self.keypoint_blend_factor,
            center_blend_factor=self.center_blend_factor,
        )
        if log_timing:
            self.last_rhand_time_ms = (time.perf_counter() - t_rhand_start) * 1e3

        t_lhand_start = time.perf_counter() if log_timing else 0.0
        lhand_fitted = _solve_and_blend(
            targets=canonical_lhand,
            tree=self._hand_tree,
            bone_lengths=lhand_lengths,
            tolerance=self.fabrik_tolerance,
            max_iterations=self.fabrik_max_iterations,
            initial_positions=lhand_initial,
            keypoint_blend_factor=self.keypoint_blend_factor,
            center_blend_factor=self.center_blend_factor,
        )
        if log_timing:
            self.last_lhand_time_ms = (time.perf_counter() - t_lhand_start) * 1e3

        # ---- 6. Cache solutions for next frame's warm-start ----
        self._prev_body_solution = body_fitted
        self._prev_rhand_solution = rhand_fitted
        self._prev_lhand_solution = lhand_fitted

        # ---- 7. Convert hand canonical names → tracker names ----
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

        # ---- 8. Return result ----
        return SkeletonFittingResult(
            body_positions=body_fitted,
            left_hand_positions=lhand_tracker,
            right_hand_positions=rhand_tracker,
            body_bone_lengths=body_lengths,
            left_hand_bone_lengths=lhand_lengths,
            right_hand_bone_lengths=rhand_lengths,
        )

    # ------------------------------------------------------------------
    # State reset
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Clear warm-start cache — next frame starts fresh."""
        self._prev_body_solution = None
        self._prev_rhand_solution = None
        self._prev_lhand_solution = None

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def body_bone_statistics(self) -> dict[str, dict[str, float]]:
        """Per-bone anatomical prior lengths for the body tree."""
        return {
            bk: {"prior": prior}
            for bk, prior in self._static_body_priors.items()
        }


# ==================================================================
# Module-level helpers (static, no self)
# ==================================================================


def _measure_lengths(
    positions: dict[str, np.ndarray],
    tree: FabrikTree,
    fallback_priors: dict[str, float],
) -> dict[str, float]:
    """Measure inter-keypoint distances as bone lengths from one frame.

    Bones with both endpoints present get their observed Euclidean distance.
    Bones with a missing endpoint fall back to the static anatomical prior.
    """
    lengths: dict[str, float] = {}
    for bone_key in tree.bone_keys:
        parent_name, child_name = bone_key.split("->", 1)
        parent_pos = positions.get(parent_name)
        child_pos = positions.get(child_name)
        if parent_pos is not None and child_pos is not None:
            dist = float(np.linalg.norm(
                np.asarray(parent_pos) - np.asarray(child_pos)
            ))
            if dist > 0.0:
                lengths[bone_key] = dist
                continue
        # Fallback: use the static anatomical prior
        lengths[bone_key] = fallback_priors.get(bone_key, 50.0)
    return lengths


def _clamp_to_prior(
    lengths: dict[str, float],
    priors: dict[str, float],
    ratio: float,
) -> dict[str, float]:
    """Clamp each bone length to [prior*(1-ratio), prior*(1+ratio)].

    Prevents single-frame measurement noise from producing wildly
    non-anatomical bone lengths.  A 20% ratio on a 400 mm femur
    gives a 320-480 mm range.
    """
    clamped: dict[str, float] = {}
    for bk, length in lengths.items():
        prior = priors.get(bk)
        if prior is None or prior <= 0.0:
            clamped[bk] = length
            continue
        lo = prior * (1.0 - ratio)
        hi = prior * (1.0 + ratio)
        clamped[bk] = float(np.clip(length, lo, hi))
    return clamped


def _warm_start_positions(
    *,
    prev_solution: dict[str, np.ndarray] | None,
    targets: dict[str, np.ndarray],
    root_names: tuple[str, ...],
) -> dict[str, np.ndarray] | None:
    """Translate the previous frame's solution so its root aligns with
    the current root target, producing a warm-start initial guess for
    FABRIK.  Returns None if no previous solution exists.

    Global translation is removed so FABRIK only needs to resolve the
    differential pose change between frames — which is tiny at 30+ fps.
    """
    if prev_solution is None:
        return None
    # Find the first root present in both prev and current
    root_name = None
    for name in root_names:
        if name in prev_solution and name in targets:
            root_name = name
            break
    if root_name is None:
        return None
    offset = np.asarray(targets[root_name]) - np.asarray(prev_solution[root_name])
    # Only translate if the offset is meaningful (>1 μm)
    if float(np.linalg.norm(offset)) < 1e-6:
        return dict(prev_solution)
    translated: dict[str, np.ndarray] = {}
    for name, pos in prev_solution.items():
        if name in targets:
            translated[name] = np.asarray(pos) + offset
    return translated


def _solve_and_blend(
    *,
    targets: dict[str, np.ndarray],
    tree: FabrikTree,
    bone_lengths: dict[str, float],
    tolerance: float,
    max_iterations: int,
    initial_positions: dict[str, np.ndarray] | None,
    keypoint_blend_factor: float,
    center_blend_factor: float,
) -> dict[str, np.ndarray]:
    """Run one FABRIK solve, then blend the result toward keypoint targets.

    Returns empty dict if the tree has no nodes or no root in targets.
    """
    if not tree.nodes:
        return {}
    if not any(root in targets for root in tree.root_names):
        return {}

    # Build target dict; missing joints get parent position as fallback
    fabrik_targets: dict[str, np.ndarray] = {}
    for name in tree.topo_order:
        if name in targets:
            fabrik_targets[name] = np.asarray(targets[name], dtype=np.float64)
        else:
            node = tree.nodes[name]
            if node.parent_name is not None and node.parent_name in fabrik_targets:
                fabrik_targets[name] = fabrik_targets[node.parent_name].copy()
            else:
                continue
    if not fabrik_targets:
        return {}

    # Fill any missing bone lengths with a 50 mm fallback
    working_lengths: dict[str, float] = dict(bone_lengths)
    for bone_key in tree.bone_keys:
        if bone_key not in working_lengths:
            working_lengths[bone_key] = 50.0

    # Single FABRIK solve
    solved = solve_fabrik_tree(
        targets=fabrik_targets,
        tree=tree,
        bone_lengths=working_lengths,
        tolerance=tolerance,
        max_iterations=max_iterations,
        initial_positions=initial_positions,
    )

    # Post-solve blend toward keypoint targets.
    # Two factors compose:
    #   keypoint_blend_factor — global pull toward raw targets (default 0.6)
    #   center_blend_factor  — extra pull for branch points (hips_center, etc.)
    #                           that get no direct snap in the forward pass.
    apply_global = keypoint_blend_factor > 0.0
    apply_center = center_blend_factor > 0.0
    if apply_global or apply_center:
        for joint_name in solved:
            target = fabrik_targets.get(joint_name)
            if target is None:
                continue
            result = solved[joint_name]
            if apply_global:
                result = (
                    (1.0 - keypoint_blend_factor) * result
                    + keypoint_blend_factor * target
                )
            if apply_center and joint_name in _CENTER_JOINT_NAMES:
                result = (
                    (1.0 - center_blend_factor) * result
                    + center_blend_factor * target
                )
            solved[joint_name] = result

    return solved
