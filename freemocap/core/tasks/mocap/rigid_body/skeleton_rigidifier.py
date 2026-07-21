"""Single-frame forward-pass rigidifier for the realtime pipeline.

This is the streaming counterpart of skellyforge's posthoc
``rigidify_forward_pass`` (``enforce_rigid_bones.py``). For one frame:

    * anchor each present root at its observed position,
    * walk the tree from the roots outward (topological / BFS order),
    * for each bone, take the direction from the *corrected* parent toward the
      observed child, normalize it, and place the child exactly ``length`` away.

Keeping the observed direction but overriding the length is what makes the
skeleton track the subject's pose while holding rigid segment lengths. The
per-bone last-good direction is carried across frames, so a joint that drops
out for a few frames is gap-filled along its last direction instead of
collapsing onto its parent.
"""
from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np

from skellyforge.skellymodels.models.anatomical_structure import AnatomicalStructure
from skellyforge.skellymodels.models.tracking_model_info import (
    CanonicalBodyModelInfo,
    CanonicalHandModelInfo,
)
from skellytracker.core.detectors.keypoint_detectors.mediapipe.body.mediapipe_pose_detector import (
    MediapipePoseKeypointDetector,
)
from skellytracker.core.detectors.keypoint_detectors.mediapipe.hands.mediapipe_hand_detector import (
    MediapipeHandKeypointDetector,
)
from skellytracker.core.detectors.keypoint_detectors.rtmpose.body.rtmpose_body_detector import (
    RTMPoseBodyDetector,
)
from skellytracker.core.detectors.keypoint_detectors.rtmpose.hand.rtmpose_hand_detector import (
    RTMPoseHandDetector,
)
from skellytracker.core.io.tracker_mapping import TrackerMapping

from freemocap.core.tasks.mocap.rigid_body.online_segment_lengths import OnlineBoneLengths

# Direction used for a bone that has never been observed (no carried direction).
_FALLBACK_DIRECTION: np.ndarray = np.array([0.0, 1.0, 0.0])

# Tracker->canonical mapping YAMLs (shipped with skellytracker), keyed by
# CameraNodeConfig.detector_type so RealtimeSkeletonRigidifier.create() can
# pick the mapping that matches the configured detector's keypoint names.
_BODY_MAPPING_YAML_BY_DETECTOR: dict[str, Path] = {
    "rtmpose": RTMPoseBodyDetector.canonical_mapping_path(),
    "mediapipe": MediapipePoseKeypointDetector.canonical_mapping_path(),
}
_HAND_MAPPING_YAML_BY_DETECTOR: dict[str, Path] = {
    "rtmpose": RTMPoseHandDetector.canonical_mapping_path(),
    "mediapipe": MediapipeHandKeypointDetector.canonical_mapping_path(),
}


class TreeRigidifier:
    """Forward-pass rigidify over a fixed joint hierarchy.

    The tree topology (roots + BFS edge order) is computed once at construction;
    ``rigidify`` is the per-frame hot path. Stateful across calls: it remembers
    each bone's last-good direction.
    """

    def __init__(self, *, joint_hierarchy: dict[str, list[str]]) -> None:
        children_of: dict[str, list[str]] = {
            parent: list(children) for parent, children in joint_hierarchy.items()
        }
        all_children = {c for children in children_of.values() for c in children}
        roots = [parent for parent in children_of if parent not in all_children]

        # BFS edge order: a parent is always emitted before its children, so the
        # forward pass can rely on the corrected parent already being placed.
        edges: list[tuple[str, str]] = []
        visited: set[str] = set(roots)
        queue: deque[str] = deque(roots)
        while queue:
            parent = queue.popleft()
            for child in children_of.get(parent, []):
                edges.append((parent, child))
                if child not in visited:
                    visited.add(child)
                    queue.append(child)

        self._roots: tuple[str, ...] = tuple(roots)
        self._edges: tuple[tuple[str, str], ...] = tuple(edges)
        self._last_direction: dict[str, np.ndarray] = {}

    def rigidify(
        self,
        positions: dict[str, np.ndarray],
        bone_lengths: dict[str, float],
    ) -> dict[str, np.ndarray]:
        """Return rigidified positions for every joint reachable from a present root.

        Parameters
        ----------
        positions : dict[str, (3,) ndarray]
            Observed joint positions this frame (missing joints simply absent).
        bone_lengths : dict[str, float]
            ``"parent->child" -> length (mm)`` to enforce. Bones without a
            positive length are skipped (their subtree is not placed).
        """
        corrected: dict[str, np.ndarray] = {}
        for root in self._roots:
            obs = positions.get(root)
            if obs is not None:
                corrected[root] = np.asarray(obs, dtype=float).copy()

        for parent, child in self._edges:
            parent_pos = corrected.get(parent)
            if parent_pos is None:
                continue  # subtree not anchored (root or ancestor missing)
            length = bone_lengths.get(f"{parent}->{child}")
            if length is None or length <= 0.0:
                continue

            bone_key = f"{parent}->{child}"
            direction: np.ndarray | None = None
            child_obs = positions.get(child)
            if child_obs is not None:
                vector = np.asarray(child_obs, dtype=float) - parent_pos
                norm = float(np.linalg.norm(vector))
                if math.isfinite(norm) and norm > 1e-6:
                    direction = vector / norm
                    self._last_direction[bone_key] = direction
            if direction is None:
                direction = self._last_direction.get(bone_key, _FALLBACK_DIRECTION)

            corrected[child] = parent_pos + direction * length

        return corrected

    def reset(self) -> None:
        """Forget all carried directions (e.g. on calibration reload)."""
        self._last_direction.clear()


# ===========================================================================
# Hand tracker->canonical mapping helper
# ===========================================================================


def _build_hand_mapping(yaml_path: Path, *, side: str) -> tuple[TrackerMapping, dict[str, str]]:
    """Build a hand tracker->canonical mapping + a canonical->tracker reverse map.

    Both RTMPose and MediaPipe compose hand landmarks with a uniform
    ``{side}_hand_`` prefix (``right_hand_thumb1`` ...), so the mapping strips
    that prefix to match the unprefixed entries in the mapping YAML
    (``thumb1`` ...). The reverse map converts fitted canonical hand names back
    to tracker names so they key into the frontend's hand schema.
    """
    import yaml
    with open(yaml_path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    prefix = f"{side}_hand_"
    mapping = TrackerMapping(entries=raw, prefix=prefix)
    reverse_map = {canonical: f"{prefix}{relative}" for canonical, relative in raw.items()}
    return mapping, reverse_map


def _seeds_from_ratios(
    *,
    joint_hierarchy: dict[str, list[str]],
    bone_length_ratios: dict[str, float] | None,
    height_mm: float,
) -> dict[str, float]:
    """Anthropometric seed length (mm) for every bone in the hierarchy.

    Every bone must have a positive ratio in the canonical model — a missing or
    non-positive ratio is a model error: fail loudly.
    """
    if bone_length_ratios is None:
        raise ValueError(
            "Canonical model has no bone_length_ratios — cannot seed bone lengths "
            "(is skellyforge synced into the venv?)."
        )
    seeds: dict[str, float] = {}
    for parent, children in joint_hierarchy.items():
        for child in children:
            bone_key = f"{parent}->{child}"
            ratio = bone_length_ratios.get(bone_key)
            if ratio is None or ratio <= 0.0:
                raise ValueError(
                    f"No positive bone-length ratio for '{bone_key}' in the canonical "
                    f"model — every bone needs one."
                )
            seeds[bone_key] = ratio * height_mm
    return seeds


def _hand_errors(
    errors: dict[str, float] | None,
    name_to_tracker: dict[str, str],
) -> dict[str, float] | None:
    """Remap reprojection errors from tracker keypoint names to canonical hand names.

    Parameters
    ----------
    errors : dict[str, float] | None
        Per-tracker-keypoint reprojection errors (px), keyed by the configured
        detector's side-prefixed tracker names (e.g. ``"right_hand_thumb1"``
        for RTMPose). ``None`` means no errors are available — all samples are
        treated as equally confident.
    name_to_tracker : dict[str, str]
        Reverse map from canonical hand landmark name to side-prefixed
        tracker name, as built by ``_build_hand_mapping``. For example
        ``{"wrist": "right_hand_root", "thumb_cmc": "right_hand_thumb1"}``.

    Returns
    -------
    dict[str, float] | None
        Errors remapped to canonical hand landmark names, or ``None`` if
        ``errors`` was ``None``. Canonical names whose tracker name is not
        present in ``errors`` are silently omitted (the bone estimator
        treats missing entries as error 0.0).
    """
    if errors is None:
        return None
    return {
        canonical: errors[tracker]
        for canonical, tracker in name_to_tracker.items()
        if tracker in errors
    }


# ===========================================================================
# RealtimeSkeletonRigidifier
# ===========================================================================


@dataclass(slots=True)
class RigidifyResult:
    """Rigidified skeleton positions for one frame.

    Body positions use canonical landmark names; hand positions use the
    configured detector's side-prefixed tracker names (``right_hand_thumb1``
    for RTMPose, ``right_hand_thumb_cmc`` for MediaPipe) so they key into the
    frontend's hand schema. Trees with insufficient data (missing root) come
    back empty.
    """

    body_positions: dict[str, np.ndarray]
    left_hand_positions: dict[str, np.ndarray]
    right_hand_positions: dict[str, np.ndarray]


@dataclass
class RealtimeSkeletonRigidifier:
    """Per-frame rigid-body skeleton correction: map -> estimate -> rigidify.

    Created once at aggregator init for a specific detector type (RTMPose or
    MediaPipe — see ``create``). Each frame: map the configured detector's raw
    keypoints onto the canonical body + hand models, update each bone's online
    length estimate
    (a best-K-by-reprojection-error median), and run a single closed-form
    forward pass that holds those lengths while following the observed pose.

    This is the streaming counterpart of the posthoc rigid-bones step
    (skellyforge ``enforce_rigid_bones``): same median-length + forward-pass
    method, applied online instead of over a whole recording.
    """

    _body_mapping: TrackerMapping = field(repr=False)
    _hand_mapping_r: TrackerMapping = field(repr=False)
    _hand_mapping_l: TrackerMapping = field(repr=False)

    _body_tree: TreeRigidifier = field(repr=False)
    _hand_tree_r: TreeRigidifier = field(repr=False)
    _hand_tree_l: TreeRigidifier = field(repr=False)

    _body_lengths: OnlineBoneLengths = field(repr=False)
    _rhand_lengths: OnlineBoneLengths = field(repr=False)
    _lhand_lengths: OnlineBoneLengths = field(repr=False)

    _hand_name_to_tracker_r: dict[str, str] = field(repr=False)
    _hand_name_to_tracker_l: dict[str, str] = field(repr=False)

    height_mm: float = 1750.0

    @classmethod
    def create(
        cls,
        *,
        detector_type: Literal["rtmpose", "mediapipe"] = "rtmpose",
        height_mm: float = 1750.0,
        buffer_capacity: int = 64,
        decay_tau_s: float = 30.0,
        max_reprojection_error: float | None = None,
        plausibility_tol: float | None = 0.5,
        min_samples: int = 1,
    ) -> "RealtimeSkeletonRigidifier":
        """Load canonical models + tracker mappings and build the per-tree state.

        Parameters
        ----------
        detector_type : "rtmpose" | "mediapipe"
            Which detector's raw keypoint names to map from — must match
            ``CameraNodeConfig.detector_type`` for the pipeline this rigidifier
            is attached to, since the two detectors use different keypoint
            naming conventions.
        height_mm : float
            Subject standing height (mm); scales the anthropometric bone-length
            seeds used until real observations accumulate.
        buffer_capacity : int
            Best-K buffer size per bone.
        decay_tau_s : float
            Age-decay time constant (s) for the buffer's eviction score.
        max_reprojection_error : float | None
            Reprojection-error gate for admitting a measurement (None = rely on
            the upstream NaN-rejection gate).
        plausibility_tol : float | None
            Fractional deviation from the running median above which a
            measurement is rejected as implausible.
        min_samples : int
            Measurements needed before the median replaces the seed.
        """
        body_anatomy = AnatomicalStructure.from_model_info(CanonicalBodyModelInfo(), "body")
        hand_anatomy = AnatomicalStructure.from_model_info(CanonicalHandModelInfo(), "hand")

        if body_anatomy.joint_hierarchy is None:
            raise ValueError("Canonical body model has no joint_hierarchy")
        if hand_anatomy.joint_hierarchy is None:
            raise ValueError("Canonical hand model has no joint_hierarchy")

        body_mapping = TrackerMapping.from_yaml(_BODY_MAPPING_YAML_BY_DETECTOR[detector_type])
        hand_yaml = _HAND_MAPPING_YAML_BY_DETECTOR[detector_type]
        hand_mapping_r, name_to_tracker_r = _build_hand_mapping(hand_yaml, side="right")
        hand_mapping_l, name_to_tracker_l = _build_hand_mapping(hand_yaml, side="left")

        body_seeds = _seeds_from_ratios(
            joint_hierarchy=body_anatomy.joint_hierarchy,
            bone_length_ratios=body_anatomy.bone_length_ratios,
            height_mm=height_mm,
        )
        hand_seeds = _seeds_from_ratios(
            joint_hierarchy=hand_anatomy.joint_hierarchy,
            bone_length_ratios=hand_anatomy.bone_length_ratios,
            height_mm=height_mm,
        )

        def make_lengths(seeds: dict[str, float]) -> OnlineBoneLengths:
            return OnlineBoneLengths(
                bone_seeds=seeds,
                capacity=buffer_capacity,
                decay_tau_s=decay_tau_s,
                min_samples=min_samples,
                max_error=max_reprojection_error,
                plausibility_tol=plausibility_tol,
            )

        return cls(
            _body_mapping=body_mapping,
            _hand_mapping_r=hand_mapping_r,
            _hand_mapping_l=hand_mapping_l,
            _body_tree=TreeRigidifier(joint_hierarchy=body_anatomy.joint_hierarchy),
            _hand_tree_r=TreeRigidifier(joint_hierarchy=hand_anatomy.joint_hierarchy),
            _hand_tree_l=TreeRigidifier(joint_hierarchy=hand_anatomy.joint_hierarchy),
            _body_lengths=make_lengths(body_seeds),
            _rhand_lengths=make_lengths(hand_seeds),
            _lhand_lengths=make_lengths(hand_seeds),
            _hand_name_to_tracker_r=name_to_tracker_r,
            _hand_name_to_tracker_l=name_to_tracker_l,
            height_mm=height_mm,
        )

    def rigidify_frame(
        self,
        tracker_positions: dict[str, np.ndarray],
        *,
        t: float | None = None,
        errors: dict[str, float] | None = None,
    ) -> RigidifyResult:
        """Rigidify one frame of the configured detector's raw keypoints.

        ``errors`` (optional) maps **tracker** keypoint name -> reprojection
        error (px); the bone-length estimator uses it to rank/gate samples so
        high-error frames don't corrupt the lengths. Most body limb landmarks
        share names with the canonical model directly (both RTMPose and
        MediaPipe use core COCO limb names); hand errors are remapped from the
        side-prefixed tracker names. When absent, samples are treated as
        equally confident.
        """
        if t is None:
            t = time.perf_counter()

        canonical_body = self._body_mapping.apply(tracker_positions)
        canonical_rhand = self._hand_mapping_r.apply(tracker_positions)
        canonical_lhand = self._hand_mapping_l.apply(tracker_positions)

        self._body_lengths.update(canonical_body, t=t, errors=errors)
        self._rhand_lengths.update(
            canonical_rhand, t=t, errors=_hand_errors(errors, self._hand_name_to_tracker_r),
        )
        self._lhand_lengths.update(
            canonical_lhand, t=t, errors=_hand_errors(errors, self._hand_name_to_tracker_l),
        )

        body_out = self._body_tree.rigidify(canonical_body, self._body_lengths.lengths)
        rhand_out = self._hand_tree_r.rigidify(canonical_rhand, self._rhand_lengths.lengths)
        lhand_out = self._hand_tree_l.rigidify(canonical_lhand, self._lhand_lengths.lengths)

        rhand_tracker = {
            self._hand_name_to_tracker_r[name]: pos
            for name, pos in rhand_out.items()
            if name in self._hand_name_to_tracker_r
        }
        lhand_tracker = {
            self._hand_name_to_tracker_l[name]: pos
            for name, pos in lhand_out.items()
            if name in self._hand_name_to_tracker_l
        }

        return RigidifyResult(
            body_positions=body_out,
            left_hand_positions=lhand_tracker,
            right_hand_positions=rhand_tracker,
        )

    def reset(self) -> None:
        """Restore the fitter to its just-created state.

        Forgets the learned bone lengths (every online estimate falls back to its
        anthropometric seed) and clears the carried gap-fill directions on all
        trees. The next frame re-fits from scratch, exactly as if the pipeline had
        just started.
        """
        self._body_tree.reset()
        self._hand_tree_r.reset()
        self._hand_tree_l.reset()
        self._body_lengths.reset()
        self._rhand_lengths.reset()
        self._lhand_lengths.reset()

    @property
    def body_bone_lengths(self) -> dict[str, float]:
        return self._body_lengths.lengths

    @property
    def right_hand_bone_lengths(self) -> dict[str, float]:
        return self._rhand_lengths.lengths

    @property
    def left_hand_bone_lengths(self) -> dict[str, float]:
        return self._lhand_lengths.lengths
