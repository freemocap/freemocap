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
class _BoneLengthCorrector:
    """Per-bone integral corrector for persistent FABRIK residuals.

    After each FABRIK solve, the axial residual (tracker_child - solved_child)
    projected onto the bone direction is accumulated into a leaky integral.
    Unlike a simple low-pass filter, this integrator can grow beyond the
    instantaneous error magnitude — exactly like the I term in a PID
    controller.  The leak prevents windup by slowly decaying the accumulator
    when errors disappear.

    Usage per frame::

        # 1. Apply the current integral as a bone-length bias
        effective = blended + corrector.get_correction(max_mm)

        # 2. Run FABRIK with the effective length

        # 3. Feed the post-solve axial residual back
        corrector.update(axial_error_mm, leak=leak, ki=gain)
        # → integral grows while error persists, saturates at clamp limit
    """

    integral: float = 0.0  # accumulated correction (mm)

    def update(self, axial_error_mm: float, *, leak: float, ki: float) -> None:
        """Accumulate a new axial residual observation.

        The update is::

            integral = leak * integral + ki * axial_error

        With ``leak < 1`` this is a leaky integrator — old errors decay
        exponentially.  With ``leak = 1`` it's a pure integrator (no decay).
        ``ki`` is the integral gain: how aggressively each frame's error
        contributes to the accumulator.

        The integral is NOT clamped here — clamping happens at read time
        via :meth:`get_correction`.

        Args:
            axial_error_mm:
                ``dot(tracker_child - solved_child, bone_direction)``.
                Positive → tracker wants child farther → bone too short.
                Negative → tracker wants child closer → bone too long.
            leak:
                Per-frame retention factor.  0.95 = 5% decay per frame.
                At 30 fps this is a ~0.67 s time constant.
            ki:
                Integral gain — mm of accumulation per mm of axial error.
                Typical: 0.03–0.20.
        """
        self.integral = leak * self.integral + ki * axial_error_mm

    def get_correction(self, max_correction_mm: float) -> float:
        """Return the integral clamped to ±max_correction_mm."""
        return float(np.clip(self.integral, -max_correction_mm, max_correction_mm))


@dataclass
class _WelfordTracker:
    """Online mean/variance for a single bone — O(1) memory, no buffers."""

    prior: float = 0.0
    count: int = 0
    mean: float = 0.0
    M2: float = 0.0  # sum of squared differences from mean

    def observe(self, value: float, max_effective_samples: int = 300) -> None:
        """Update running statistics with a new observation.

        Uses cumulative-mean Welford updates for the first
        *max_effective_samples* frames, then switches to a
        constant-weight EMA update.  This prevents the estimator from
        becoming arbitrarily resistant to change during long recordings
        (where 1/count → 0 and early bad data permanently biases the mean).
        """
        self.count += 1
        if self.count <= max_effective_samples:
            # Standard Welford cumulative update
            delta = value - self.mean
            self.mean += delta / self.count
            delta2 = value - self.mean
            self.M2 += delta * delta2
        else:
            # Capped-weight EMA: constant learning rate so the estimator
            # stays responsive regardless of recording length.
            weight = 1.0 / max_effective_samples
            old_mean = self.mean
            self.mean = (1.0 - weight) * self.mean + weight * value
            # Approximate M2 update for the EMA regime: track a
            # decaying variance estimate so blended_length() confidence
            # still works.
            delta = value - self.mean
            delta_old = value - old_mean
            self.M2 = (1.0 - weight) * self.M2 + weight * delta * delta_old

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
        prior_forget_samples: int = 300,
    ) -> float:
        """Blend prior and observed mean with linear prior decay.

        The prior weight starts at 1.0 and decays linearly to 0.0 over
        *prior_forget_samples* frames.  After that the pure observed mean
        is returned — the anthropometric seed is completely forgotten.

        This is intentionally simpler than the old CV-based formula:
        the Welford EMA cap already handles measurement noise by keeping
        the estimator responsive, so we don't need CV to gate confidence.
        """
        if self.count == 0:
            return self.prior

        # Linear decay: prior_weight goes 1.0 → 0.0 over prior_forget_samples
        prior_weight = max(0.0, 1.0 - self.count / prior_forget_samples)

        return self.prior * prior_weight + self.mean * (1.0 - prior_weight)


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


# Derived center joints — computed landmarks (means of tracked keypoints)
# rather than directly tracked.  These get post-FABRIK blending toward
# their tracker targets to reduce jitter amplification.
_CENTER_JOINT_NAMES: frozenset[str] = frozenset({
    "hips_center",
    "trunk_center",
    "neck_center",
    "head_center",
})


# ---------------------------------------------------------------------------
# Helpers (module-level, no allocations in the hot path beyond the calls)
# ---------------------------------------------------------------------------


def _update_correctors(
    *,
    solved: dict[str, np.ndarray],
    targets: dict[str, np.ndarray],
    tree: FabrikTree,
    correctors: dict[str, _BoneLengthCorrector],
    leak: float,
    ki: float,
) -> None:
    """Feed post-FABRIK axial residuals into the per-bone integral correctors.

    Calls :meth:`_BoneLengthCorrector.update` on every bone whose endpoints
    are present.  Missing bones are silently skipped (their integrals decay
    toward zero via the leak).
    """
    residuals = _compute_axial_residuals_dict(
        solved=solved, targets=targets, tree=tree,
    )
    for bone_key, axial_error_mm in residuals.items():
        correctors[bone_key].update(
            axial_error_mm=axial_error_mm, leak=leak, ki=ki,
        )


def _compute_axial_residuals_dict(
    *,
    solved: dict[str, np.ndarray],
    targets: dict[str, np.ndarray],
    tree: FabrikTree,
) -> dict[str, float]:
    """Return per-bone axial residuals from a FABRIK solution.

    For each bone, projects ``target_child - solved_child`` onto
    ``normalize(solved_child - solved_parent)``.  Positive = bone was
    too short, negative = bone was too long.

    Used by both the integral corrector (across frames) and the
    within-frame refinement passes.
    """
    residuals: dict[str, float] = {}
    for bone_key in tree.bone_keys:
        parent_name, child_name = bone_key.split("->", 1)
        solved_parent = solved.get(parent_name)
        solved_child = solved.get(child_name)
        target_child = targets.get(child_name)
        if solved_parent is None or solved_child is None or target_child is None:
            continue
        bone_vec = solved_child - solved_parent
        bone_dist = float(np.linalg.norm(bone_vec))
        if bone_dist < 1e-9:
            continue
        bone_dir = bone_vec / bone_dist
        residual = target_child - solved_child
        residuals[bone_key] = float(np.dot(residual, bone_dir))
    return residuals


def _compute_total_residual(
    solved: dict[str, np.ndarray],
    targets: dict[str, np.ndarray],
) -> float:
    """Sum of Euclidean distances between solved and target positions.

    Only joints present in BOTH dicts contribute.  This is the objective
    function that the refinement passes minimise.
    """
    total = 0.0
    for name in solved:
        target = targets.get(name)
        if target is not None:
            total += float(np.linalg.norm(solved[name] - target))
    return total


# ---------------------------------------------------------------------------
# RealtimeSkeletonFitter
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

    # Per-bone integral correctors (persistent-residual → bone-length bias)
    _body_correctors: dict[str, _BoneLengthCorrector] = field(repr=False)
    _hand_correctors_r: dict[str, _BoneLengthCorrector] = field(repr=False)
    _hand_correctors_l: dict[str, _BoneLengthCorrector] = field(repr=False)

    # Hand canonical → tracker name reverse maps (built once, used per-frame)
    _hand_name_to_tracker_r: dict[str, str] = field(default_factory=dict, repr=False)
    _hand_name_to_tracker_l: dict[str, str] = field(default_factory=dict, repr=False)

    # Config (all lengths in mm — keypoint-coordinate units)
    height_mm: float = 1750.0
    fabrik_tolerance: float = 0.1  # mm — FABRIK convergence threshold
    fabrik_max_iterations: int = 20
    prior_forget_samples: int = 300     # frames until prior is completely forgotten (~10s at 30fps)
    center_prior_forget_samples: int = 30  # faster for center→center bones (~1s)
    max_welford_samples: int = 300      # cap effective sample count (~10s at 30fps)
    center_blend_factor: float = 0.4    # how strongly to snap center joints toward tracker targets post-FABRIK

    # Integral bone-length correction (PID-like I term)
    integral_gain: float = 0.10     # mm correction per mm accumulated axial error
    integral_leak: float = 0.95     # per-frame decay (0.95 @ 30fps → ~0.67s time constant)
    max_integral_correction_mm: float = 50.0  # hard clamp on correction magnitude

    # Within-frame FABRIK refinement (escapes local minima from coupled bones)
    fabrik_refinement_passes: int = 2   # extra FABRIK solves per frame (0 = disabled)
    fabrik_refinement_gain: float = 0.5 # within-frame bone-length adjustment gain
    fabrik_jitter_mm: float = 3.0       # stddev of Gaussian jitter on bone lengths (mm)

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
        prior_forget_samples: int = 300,
        center_prior_forget_samples: int = 30,
        max_welford_samples: int = 300,
        center_blend_factor: float = 0.4,
        integral_gain: float = 0.10,
        integral_leak: float = 0.95,
        max_integral_correction_mm: float = 50.0,
        fabrik_refinement_passes: int = 2,
        fabrik_refinement_gain: float = 0.5,
        fabrik_jitter_mm: float = 3.0,
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
        prior_forget_samples : int
            Frames until anthropometric prior is completely forgotten.
            After this the blended length = pure observed mean.
            Default 300 (~10 s at 30 fps).
        center_prior_forget_samples : int
            Same for center→center bones (hips_center→trunk_center, etc.).
            Much shorter because these are derived landmarks with no
            anatomical truth.  Default 30 (~1 s).
        max_welford_samples : int
            Cap on effective sample count for the Welford estimator
            (~10 s at 30 fps).  Prevents freeze in long recordings.
        center_blend_factor : float
            Post-FABRIK blend factor for derived center joints
            (hips_center, neck_center, head_center).  0 = no blend
            (pure FABRIK), 1 = snap to tracker target.  Default 0.4.
        integral_gain : float
            Integral gain (ki) — mm of integral accumulation per mm of
            axial error per frame.  0 = no correction.  Default 0.10.
        integral_leak : float
            Per-frame retention factor for the integral accumulator.
            0.95 = 5% decay/frame → ~0.67 s time constant at 30 fps.
        max_integral_correction_mm : float
            Hard clamp on the absolute integral value (mm).
        fabrik_refinement_passes : int
            Extra FABRIK solves per frame to escape local minima.
            0 = disabled.  Default 2.
        fabrik_refinement_gain : float
            Within-frame bone-length adjustment gain.  Default 0.5.
        fabrik_jitter_mm : float
            Stddev of Gaussian jitter on bone lengths (mm).
            0 = deterministic only.  Default 3.0.
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
            _body_correctors={bk: _BoneLengthCorrector() for bk in body_tree.bone_keys},
            _hand_correctors_r={bk: _BoneLengthCorrector() for bk in hand_tree.bone_keys},
            _hand_correctors_l={bk: _BoneLengthCorrector() for bk in hand_tree.bone_keys},
            _hand_name_to_tracker_r=hand_name_to_tracker_r,
            _hand_name_to_tracker_l=hand_name_to_tracker_l,
            height_mm=height_mm,
            fabrik_tolerance=fabrik_tolerance,
            fabrik_max_iterations=fabrik_max_iterations,
            prior_forget_samples=prior_forget_samples,
            center_prior_forget_samples=center_prior_forget_samples,
            max_welford_samples=max_welford_samples,
            center_blend_factor=center_blend_factor,
            integral_gain=integral_gain,
            integral_leak=integral_leak,
            max_integral_correction_mm=max_integral_correction_mm,
            fabrik_refinement_passes=fabrik_refinement_passes,
            fabrik_refinement_gain=fabrik_refinement_gain,
            fabrik_jitter_mm=fabrik_jitter_mm,
        )

    @staticmethod
    def _build_trackers(
        *,
        tree: FabrikTree,
        bone_length_ratios: Optional[dict[str, float]],
        height_mm: float,
    ) -> dict[str, _WelfordTracker]:
        """Create per-bone Welford trackers seeded from canonical ratios (mm).

        Every bone in the tree must have a seed ratio in the canonical model's
        ``bone_length_ratios``. The seed is only an approximate starting point —
        the estimator adapts each bone toward the subject's observed lengths.
        A missing or non-positive seed is a model error: fail loudly.
        """
        if bone_length_ratios is None:
            raise ValueError(
                "Canonical model has no bone_length_ratios — cannot seed FABRIK "
                "bone lengths (is skellyforge's canonical model installed/synced?)."
            )
        trackers: dict[str, _WelfordTracker] = {}
        for bone_key in tree.bone_keys:
            ratio = bone_length_ratios.get(bone_key)
            if ratio is None or ratio <= 0.0:
                raise ValueError(
                    f"No positive bone-length seed for '{bone_key}' in the canonical "
                    f"model — every tree bone needs one (is skellyforge synced with "
                    f"all body bone ratios?)."
                )
            trackers[bone_key] = _WelfordTracker(prior=ratio * height_mm)
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
        self._observe_tree(canonical_body, self._body_tree, self._body_trackers,
                           max_welford_samples=self.max_welford_samples)
        self._observe_tree(canonical_rhand, self._hand_tree, self._hand_trackers_r,
                           max_welford_samples=self.max_welford_samples)
        self._observe_tree(canonical_lhand, self._hand_tree, self._hand_trackers_l,
                           max_welford_samples=self.max_welford_samples)

        # ---- 3. Current blended lengths ----
        # Center→center bones (hips_center→trunk_center, etc.) use a much
        # shorter prior-forget window: their "lengths" depend entirely on
        # tracker landmark definitions, not anatomy.  All other bones use
        # the standard prior_forget_samples.
        def _forget_for(bone_key: str) -> int:
            """Return prior_forget_samples appropriate for this bone."""
            parent, child = bone_key.split("->", 1)
            if "center" in parent and "center" in child:
                return self.center_prior_forget_samples
            return self.prior_forget_samples

        body_lengths_blended = {
            bk: t.blended_length(prior_forget_samples=_forget_for(bk))
            for bk, t in self._body_trackers.items()
        }
        rhand_lengths_blended = {
            bk: t.blended_length(prior_forget_samples=self.prior_forget_samples)
            for bk, t in self._hand_trackers_r.items()
        }
        lhand_lengths_blended = {
            bk: t.blended_length(prior_forget_samples=self.prior_forget_samples)
            for bk, t in self._hand_trackers_l.items()
        }

        # ---- 3b. Apply integral correction → effective bone lengths ----
        # The integral corrector accumulates persistent axial residuals from
        # previous FABRIK solves.  A positive correction lengthens the bone
        # (tracker consistently wants the child farther out); a negative
        # correction shortens it.  This is the "I term" — it catches and
        # fixes bone-length drift that the Welford estimator is too slow to
        # reverse on its own.
        body_lengths = {}
        for bk, blended in body_lengths_blended.items():
            body_lengths[bk] = blended + self._body_correctors[bk].get_correction(
                self.max_integral_correction_mm,
            )
        rhand_lengths = {}
        for bk, blended in rhand_lengths_blended.items():
            rhand_lengths[bk] = blended + self._hand_correctors_r[bk].get_correction(
                self.max_integral_correction_mm,
            )
        lhand_lengths = {}
        for bk, blended in lhand_lengths_blended.items():
            lhand_lengths[bk] = blended + self._hand_correctors_l[bk].get_correction(
                self.max_integral_correction_mm,
            )

        # ---- 4. FABRIK solve ----
        # The FABRIK solver now snaps ALL non-branch nodes to their tracker
        # targets during the forward pass (not just leaves).  Every tracked
        # joint constrains the skeleton.  Branch points (hips_center,
        # neck_center, wrist, etc.) are positioned by averaging child
        # suggestions — they're computed landmarks, not directly tracked.
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

        # ---- 4b. Update integral correctors from FABRIK residuals ----
        # After the solve, measure how far each solved joint is from its
        # tracker target along the bone axis.  Feed that axial residual
        # into the leaky integrator so the next frame's effective bone
        # length can compensate.
        _update_correctors(
            solved=body_fitted,
            targets=canonical_body,
            tree=self._body_tree,
            correctors=self._body_correctors,
            leak=self.integral_leak,
            ki=self.integral_gain,
        )
        _update_correctors(
            solved=rhand_fitted,
            targets=canonical_rhand,
            tree=self._hand_tree,
            correctors=self._hand_correctors_r,
            leak=self.integral_leak,
            ki=self.integral_gain,
        )
        _update_correctors(
            solved=lhand_fitted,
            targets=canonical_lhand,
            tree=self._hand_tree,
            correctors=self._hand_correctors_l,
            leak=self.integral_leak,
            ki=self.integral_gain,
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

    @staticmethod
    def _observe_tree(
        canonical_positions: dict[str, np.ndarray],
        tree: FabrikTree,
        trackers: dict[str, _WelfordTracker],
        max_welford_samples: int = 300,
    ) -> None:
        """Feed observed bone lengths into the running statistics.

        Every bone with both endpoints present this frame contributes an
        observation — including bones between derived centers (head/neck/
        trunk/hips_center), which are computed from tracked points and so have
        well-defined, observable lengths. Each bone's anthropometric seed is
        only a starting point; observation lets it adapt to the subject (and
        self-corrects seeds that disagree with the actual center geometry).
        """
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
                trackers[bone_key].observe(
                    length,
                    max_effective_samples=max_welford_samples,
                )

    def _try_solve(
        self,
        *,
        targets: dict[str, np.ndarray],
        tree: FabrikTree,
        bone_lengths: dict[str, float],
    ) -> dict[str, np.ndarray]:
        """Run FABRIK with optional within-frame refinement passes.

        The primary solve uses the given *bone_lengths*.  If refinement is
        enabled (``fabrik_refinement_passes > 0``), additional solves are
        attempted with bone lengths nudged in the direction of the per-bone
        axial residuals — a cheap gradient-following step.  One pass also
        adds Gaussian jitter to help escape local minima caused by coupled
        bones (e.g. knee stuck behind the hip because femur + shank + foot
        bones reached a compromise that satisfies constraints but not
        tracker targets).

        The solution with the lowest total joint error is returned.
        Refined bone lengths are ephemeral — they do NOT persist to the
        next frame or feed the integral corrector.
        """
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
        working_lengths: dict[str, float] = dict(bone_lengths)
        for bone_key in tree.bone_keys:
            if bone_key not in working_lengths:
                working_lengths[bone_key] = 50.0  # mm fallback

        # ---- Primary solve ----
        best_solution = solve_fabrik_tree(
            targets=fabrik_targets,
            tree=tree,
            bone_lengths=working_lengths,
            tolerance=self.fabrik_tolerance,
            max_iterations=self.fabrik_max_iterations,
        )
        best_error = _compute_total_residual(best_solution, fabrik_targets)
        best_lengths = dict(working_lengths)

        # ---- Refinement passes ----
        rng = np.random.default_rng()
        for pass_idx in range(self.fabrik_refinement_passes):
            # Compute axial residuals from the CURRENT best solution.
            # These tell us which direction each bone length should move.
            axial_residuals = _compute_axial_residuals_dict(
                solved=best_solution,
                targets=fabrik_targets,
                tree=tree,
            )

            # Build candidate bone lengths: nudge each bone in the
            # direction that reduces its residual.
            candidate_lengths: dict[str, float] = {}
            for bk, length in best_lengths.items():
                axial = axial_residuals.get(bk, 0.0)
                # Deterministic nudge + optional jitter on the last pass
                jitter = 0.0
                if pass_idx == self.fabrik_refinement_passes - 1 and self.fabrik_jitter_mm > 0.0:
                    jitter = rng.normal(0.0, self.fabrik_jitter_mm)
                candidate_lengths[bk] = length + self.fabrik_refinement_gain * axial + jitter
                # Don't let bone lengths go negative or absurdly short
                if candidate_lengths[bk] < 5.0:
                    candidate_lengths[bk] = 5.0

            # Re-solve with candidate lengths
            candidate_solution = solve_fabrik_tree(
                targets=fabrik_targets,
                tree=tree,
                bone_lengths=candidate_lengths,
                tolerance=self.fabrik_tolerance,
                max_iterations=self.fabrik_max_iterations,
            )
            candidate_error = _compute_total_residual(candidate_solution, fabrik_targets)

            # Keep if better
            if candidate_error < best_error:
                best_solution = candidate_solution
                best_error = candidate_error
                best_lengths = candidate_lengths

        # ---- Post-solve: blend derived-center joints toward tracker targets ----
        # hips_center, neck_center, and head_center are branch points whose
        # positions are determined by averaging child suggestions in the
        # forward pass and bone-length enforcement in the backward pass —
        # they're NOT snapped to their tracker targets.  This makes them
        # jumpier than the underlying keypoints.  Blending toward the
        # tracker target dampens that amplification.
        if self.center_blend_factor > 0.0:
            for joint_name in _CENTER_JOINT_NAMES:
                if joint_name in best_solution and joint_name in fabrik_targets:
                    target = fabrik_targets[joint_name]
                    solved = best_solution[joint_name]
                    best_solution[joint_name] = (
                        (1.0 - self.center_blend_factor) * solved
                        + self.center_blend_factor * target
                    )

        return best_solution

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def body_bone_statistics(self) -> dict[str, dict[str, float]]:
        """Per-bone statistics for the body tree."""
        return {
            bk: {"count": t.count, "mean": t.mean, "std": t.std,
                 "prior": t.prior, "blended": t.blended_length(
                     prior_forget_samples=self.prior_forget_samples,
                 )}
            for bk, t in self._body_trackers.items()
        }
