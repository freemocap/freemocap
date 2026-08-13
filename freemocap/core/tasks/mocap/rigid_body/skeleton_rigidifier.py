"""Single-frame forward-pass rigidifier for the realtime pipeline.

This is the streaming counterpart of skellyforge's posthoc
``rigidify_forward_pass`` (``enforce_rigid_bones.py``). For one frame:

    * anchor each present root at its observed position,
    * walk the tree from the roots outward (topological / BFS order),
    * for each segment, take the direction from the *corrected* parent toward the
      observed child, normalize it, and place the child exactly ``length`` away.

The trees are keyed onto the **segment model** (the composed standard human),
not the old landmark-pair joint hierarchy. Each segment's tree node is the
segment *name*; the node's observed position is that segment's ``origin_keypoint``
from the tracker→standard-human mapping output (a mapping-produced point), and
the enforced length is the segment's origin→long-axis distance. The face's three
segments (``left_eye`` / ``right_eye`` / ``jaw``) are excluded from the trees —
their spans are nominal and enforcing them would corrupt live eye/jaw positions;
their keypoints pass through uncorrected.

Keeping the observed direction but overriding the length is what makes the
skeleton track the subject's pose while holding rigid segment lengths. The
per-segment last-good direction is carried across frames, so a segment whose
origin drops out for a few frames is gap-filled along its last direction instead
of collapsing onto its parent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np

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

from skellyforge.kinematics.online_segment_lengths import SegmentLengthEstimator
from skellyforge.kinematics.skeleton_rigidifier import TreeRigidifier
from skellyforge.skellymodels.standard_human.face_part import FACE_PART
from skellyforge.skellymodels.standard_human.hand_part import HAND_PART
from skellyforge.skellymodels.standard_human.segment_definition import (
    SegmentDefinition,
)
from skellyforge.skellymodels.standard_human.standard_human_model import (
    StandardHuman,
)

# The face's three segments are excluded from the rigidify trees: their spans
# are nominal (0.01 ratio) and enforcing them would corrupt live eye/jaw
# positions. Their keypoints pass straight through uncorrected.
_FACE_SEGMENT_NAMES: frozenset[str] = frozenset(s.name for s in FACE_PART.segments)

# Unprefixed hand-part segment names (the composed model's hand segments are
# ``left_``/``right_``-prefixed versions of these).
_HAND_SEGMENT_NAMES: frozenset[str] = frozenset(s.name for s in HAND_PART.segments)

# Tracker->canonical mapping YAMLs (shipped with skellytracker), keyed by
# CameraNodeConfig.detector_type so RealtimeSkeletonRigidifier.create() can
# pick the mapping that matches the configured detector's keypoint names.
_BODY_MAPPING_YAML_BY_DETECTOR: dict[str, Path] = {
    "rtmpose": RTMPoseBodyDetector.standard_human_mapping_path(),
    "mediapipe": MediapipePoseKeypointDetector.standard_human_mapping_path(),
}
_HAND_MAPPING_YAML_BY_DETECTOR: dict[str, Path] = {
    "rtmpose": RTMPoseHandDetector.standard_human_mapping_path(),
    "mediapipe": MediapipeHandKeypointDetector.standard_human_mapping_path(),
}


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


def _prefix_keypoints(
    keypoints: dict[str, np.ndarray], prefix: str
) -> dict[str, np.ndarray]:
    """Add a side prefix to every keypoint name (``wrist`` → ``left_wrist``)."""
    return {f"{prefix}{name}": pos for name, pos in keypoints.items()}


def _split_segments(
    segments: tuple[SegmentDefinition, ...],
) -> tuple[list[SegmentDefinition], list[SegmentDefinition], list[SegmentDefinition]]:
    """Partition the composed model's segments into body / hand / face groups.

    Body = segments that are neither a side-prefixed hand-part name nor one of
    the face's three. Hand = side-prefixed hand-part names (``left_hand``,
    ``left_thumb_metacarpal``, ...); face = ``{left_eye, right_eye, jaw}``.
    """
    body: list[SegmentDefinition] = []
    hand: list[SegmentDefinition] = []
    face: list[SegmentDefinition] = []
    for seg in segments:
        if seg.name in _FACE_SEGMENT_NAMES:
            face.append(seg)
        elif seg.name.startswith(("left_", "right_")) and (
            seg.name.removeprefix("left_").removeprefix("right_") in _HAND_SEGMENT_NAMES
        ):
            hand.append(seg)
        else:
            body.append(seg)
    return body, hand, face


def _hierarchy(group: list[SegmentDefinition]) -> dict[str, list[str]]:
    """Parent → children over a group's SEGMENT names (``segment.parent``).

    Root segments (``parent is None``) are left out — ``TreeRigidifier``
    derives its roots as parents that never appear as children. Parent keys
    that refer outside the group (e.g. ``left_hand``'s parent ``left_lower_arm``)
    are dropped: the hand tree is rooted at the ``*_hand`` segment.
    """
    group_names = {seg.name for seg in group}
    hierarchy: dict[str, list[str]] = {}
    for seg in group:
        if seg.parent is None:
            continue
        if seg.parent not in group_names:
            continue
        hierarchy.setdefault(seg.parent, []).append(seg.name)
    return hierarchy


# ===========================================================================
# RealtimeSkeletonRigidifier
# ===========================================================================


@dataclass(slots=True)
class RigidifyResult:
    """Rigidified skeleton positions for one frame.

    ``body_positions`` is keyed by standard-human body keypoint names, including
    the corrected long-axis endpoints (``head_vertex``, ``mid_sternum``-adjacent
    endpoints, ``foot_ball``, ``toes``, ...) so the solver and center-of-mass get
    every derived endpoint. Hand positions use the configured detector's
    side-prefixed tracker names (``right_hand_thumb1`` for RTMPose,
    ``right_hand_thumb_cmc`` for MediaPipe) so they key into the frontend's hand
    schema. The ``*_standard_positions`` fields carry the same hand points keyed
    by the standard-human side-prefixed names (``left_wrist``,
    ``left_index_finger_tip``, ...), now including the corrected long-axis
    endpoints (the finger tips), for the composed standard-human orientation
    solver. The face's three segments pass through at their mapping-output
    positions uncorrected. Trees with insufficient data (missing root) come back
    empty.
    """

    body_positions: dict[str, np.ndarray]
    left_hand_positions: dict[str, np.ndarray]
    right_hand_positions: dict[str, np.ndarray]
    left_hand_standard_positions: dict[str, np.ndarray]
    right_hand_standard_positions: dict[str, np.ndarray]


@dataclass
class RealtimeSkeletonRigidifier:
    """Per-frame rigid-body skeleton correction: map -> estimate -> rigidify.

    Created once at aggregator init for a specific detector type (RTMPose or
    MediaPipe — see ``create``) and a composed ``StandardHuman``. Each frame:
    map the configured detector's raw keypoints onto the standard-human body +
    hand keypoints, advance the per-segment length estimators with the
    **measured** (real, not extrapolated) keypoints, and run a single
    closed-form forward pass over the segment trees that holds the estimated
    lengths while following the observed pose.

    The trees are keyed onto the segment model: three groups (body, right hand,
    left hand) each get their own hierarchy, length estimator, and tree
    rigidifier. The face's three segments are excluded (see module docstring).
    """

    _body_mapping: TrackerMapping = field(repr=False)
    _hand_mapping_r: TrackerMapping = field(repr=False)
    _hand_mapping_l: TrackerMapping = field(repr=False)

    _body_segments: tuple[SegmentDefinition, ...] = field(repr=False)
    _rhand_segments: tuple[SegmentDefinition, ...] = field(repr=False)
    _lhand_segments: tuple[SegmentDefinition, ...] = field(repr=False)
    _face_segments: tuple[SegmentDefinition, ...] = field(repr=False)

    _body_tree: TreeRigidifier = field(repr=False)
    _hand_tree_r: TreeRigidifier = field(repr=False)
    _hand_tree_l: TreeRigidifier = field(repr=False)

    _body_lengths: SegmentLengthEstimator = field(repr=False)
    _rhand_lengths: SegmentLengthEstimator = field(repr=False)
    _lhand_lengths: SegmentLengthEstimator = field(repr=False)

    _hand_name_to_tracker_r: dict[str, str] = field(repr=False)
    _hand_name_to_tracker_l: dict[str, str] = field(repr=False)

    height_mm: float = 1750.0

    @classmethod
    def create(
        cls,
        *,
        standard_human: StandardHuman,
        detector_type: Literal["rtmpose", "mediapipe"] = "rtmpose",
        height_mm: float = 1750.0,
        window_s: float = 10.0,
    ) -> "RealtimeSkeletonRigidifier":
        """Build the per-group state from the composed standard human + mappings.

        Parameters
        ----------
        standard_human : StandardHuman
            The composed standard human (``compose_standard_human()``) whose
            segments drive the trees, seeds and length estimators.
        detector_type : "rtmpose" | "mediapipe"
            Which detector's raw keypoint names to map from — must match
            ``CameraNodeConfig.detector_type`` for the pipeline this rigidifier
            is attached to, since the two detectors use different keypoint
            naming conventions.
        height_mm : float
            Subject standing height (mm); scales the anthropometric segment
            length seeds used until real observations accumulate in the window.
        window_s : float
            Rolling-window duration (s) over which each segment's median length
            is taken.
        """
        body, hand, face = _split_segments(standard_human.segments)

        rhand = [s for s in hand if s.name.startswith("right_")]
        lhand = [s for s in hand if s.name.startswith("left_")]

        body_mapping = TrackerMapping.from_yaml(_BODY_MAPPING_YAML_BY_DETECTOR[detector_type])
        hand_yaml = _HAND_MAPPING_YAML_BY_DETECTOR[detector_type]
        hand_mapping_r, name_to_tracker_r = _build_hand_mapping(hand_yaml, side="right")
        hand_mapping_l, name_to_tracker_l = _build_hand_mapping(hand_yaml, side="left")

        def make_spec(group: list[SegmentDefinition]) -> tuple[
            SegmentLengthEstimator,
            dict[str, tuple[str, str]],
        ]:
            seeds = {seg.name: seg.length_ratio * height_mm for seg in group}
            endpoints = {
                seg.name: (seg.origin_keypoint, seg.long_axis_keypoint)
                for seg in group
            }
            estimator = SegmentLengthEstimator(
                segment_endpoints=endpoints,
                segment_seeds=seeds,
                window_seconds=window_s,
            )
            return estimator, endpoints

        body_lengths, _ = make_spec(body)
        rhand_lengths, _ = make_spec(rhand)
        lhand_lengths, _ = make_spec(lhand)

        return cls(
            _body_mapping=body_mapping,
            _hand_mapping_r=hand_mapping_r,
            _hand_mapping_l=hand_mapping_l,
            _body_segments=tuple(body),
            _rhand_segments=tuple(rhand),
            _lhand_segments=tuple(lhand),
            _face_segments=tuple(face),
            _body_tree=TreeRigidifier(joint_hierarchy=_hierarchy(body)),
            _hand_tree_r=TreeRigidifier(joint_hierarchy=_hierarchy(rhand)),
            _hand_tree_l=TreeRigidifier(joint_hierarchy=_hierarchy(lhand)),
            _body_lengths=body_lengths,
            _rhand_lengths=rhand_lengths,
            _lhand_lengths=lhand_lengths,
            _hand_name_to_tracker_r=name_to_tracker_r,
            _hand_name_to_tracker_l=name_to_tracker_l,
            height_mm=height_mm,
        )

    def rigidify_frame(
        self,
        tracker_positions: dict[str, np.ndarray],
        *,
        measured: dict[str, np.ndarray],
        t: float,
    ) -> RigidifyResult:
        """Rigidify one frame of the configured detector's raw keypoints.

        Parameters
        ----------
        tracker_positions : dict[str, (3,) ndarray]
            This frame's keypoints (tracker names), including any gap-filled
            extrapolations — drives the rigidified output only.
        measured : dict[str, (3,) ndarray]
            The real-only subset of ``tracker_positions`` (extrapolated points
            removed) — the only positions allowed to teach segment lengths, so a
            gap-filled keypoint never feeds its own enforced length back in.
        t : float
            Frame timestamp (s); drives the rolling window's eviction. The
            caller owns the clock.
        """
        canonical_body = self._body_mapping.apply(tracker_positions)
        # The hand mapping produces UNPREFIXED standard names (``wrist``,
        # ``thumb_cmc``, ...); the segment model references side-prefixed ones
        # (``left_wrist``, ...). Prefix here so positions key into the trees.
        canonical_rhand = _prefix_keypoints(
            self._hand_mapping_r.apply(tracker_positions), "right_"
        )
        canonical_lhand = _prefix_keypoints(
            self._hand_mapping_l.apply(tracker_positions), "left_"
        )

        measured_body = self._body_mapping.apply(measured)
        measured_rhand = _prefix_keypoints(
            self._hand_mapping_r.apply(measured), "right_"
        )
        measured_lhand = _prefix_keypoints(
            self._hand_mapping_l.apply(measured), "left_"
        )

        self._body_lengths.update(measured_body, t=t)
        self._rhand_lengths.update(measured_rhand, t=t)
        self._lhand_lengths.update(measured_lhand, t=t)

        body_out, _ = self._rigidify_group(
            self._body_segments,
            self._body_tree,
            canonical_body,
            self._body_lengths.lengths,
        )
        rhand_out, _ = self._rigidify_group(
            self._rhand_segments,
            self._hand_tree_r,
            canonical_rhand,
            self._rhand_lengths.lengths,
        )
        lhand_out, _ = self._rigidify_group(
            self._lhand_segments,
            self._hand_tree_l,
            canonical_lhand,
            self._lhand_lengths.lengths,
        )

        # Face segments pass through uncorrected (mapping-output positions).
        face_out: dict[str, np.ndarray] = {}
        for seg in self._face_segments:
            origin = canonical_body.get(seg.origin_keypoint)
            if origin is not None:
                face_out[seg.origin_keypoint] = origin
            long_axis = canonical_body.get(seg.long_axis_keypoint)
            if long_axis is not None:
                face_out[seg.long_axis_keypoint] = long_axis

        body_positions = {**body_out, **face_out}

        rhand_tracker = {
            self._hand_name_to_tracker_r[name.removeprefix("right_")]: pos
            for name, pos in rhand_out.items()
            if name.startswith("right_")
            and name.removeprefix("right_") in self._hand_name_to_tracker_r
        }
        lhand_tracker = {
            self._hand_name_to_tracker_l[name.removeprefix("left_")]: pos
            for name, pos in lhand_out.items()
            if name.startswith("left_")
            and name.removeprefix("left_") in self._hand_name_to_tracker_l
        }
        # ``rhand_out``/``lhand_out`` are already keyed by side-prefixed standard
        # names (``left_wrist``, ``left_index_finger_tip``, ...) — the composed
        # standard human's own hand keypoint vocabulary — so they serve the
        # orientation solver directly, corrected long-axis endpoints included.
        rhand_standard = {
            name: pos for name, pos in rhand_out.items()
        }
        lhand_standard = {
            name: pos for name, pos in lhand_out.items()
        }

        return RigidifyResult(
            body_positions=body_positions,
            left_hand_positions=lhand_tracker,
            right_hand_positions=rhand_tracker,
            left_hand_standard_positions=lhand_standard,
            right_hand_standard_positions=rhand_standard,
        )

    def _rigidify_group(
        self,
        group: tuple[SegmentDefinition, ...],
        tree: TreeRigidifier,
        observed_keypoints: dict[str, np.ndarray],
        lengths: dict[str, float],
    ) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
        """Rigidify one group (body / hand): corrected segment origins + keypoints.

        Returns ``(corrected_keypoints, used_directions)`` where
        ``corrected_keypoints`` is keyed by the group's KEYPOINT names (each
        segment's corrected origin plus its corrected long-axis endpoint) and
        ``used_directions`` maps each SEGMENT name to the unit direction
        actually used.
        """
        # Segment-keyed observed origins: this segment's node is its origin
        # keypoint from the mapping output (drop missing).
        positions = {
            seg.name: observed_keypoints[seg.origin_keypoint]
            for seg in group
            if seg.origin_keypoint in observed_keypoints
        }
        # Segment-name-keyed tree lengths (the CHILD node's name, keyed by
        # segment name — the parent is known from the hierarchy). The root
        # segment has no parent, so its entry is simply absent.
        lengths_dict = {
            seg.name: lengths[seg.name]
            for seg in group
            if seg.parent is not None
        }

        corrected, directions = tree.rigidify(
            positions, lengths_dict, return_directions=True
        )

        # Convert corrected segment origins into corrected KEYPOINT positions,
        # including the corrected long-axis endpoint for each segment.
        out: dict[str, np.ndarray] = {}
        for seg in group:
            origin = corrected.get(seg.name)
            if origin is None:
                continue
            out[seg.origin_keypoint] = origin
            if seg.parent is None:
                # Root segment (no parent edge): derive the direction from the
                # observed origin→long-axis vector.
                direction = None
                observed_origin = positions.get(seg.name)
                observed_long = observed_keypoints.get(seg.long_axis_keypoint)
                if observed_origin is not None and observed_long is not None:
                    vec = np.asarray(observed_long, dtype=float) - np.asarray(
                        observed_origin, dtype=float
                    )
                    norm = float(np.linalg.norm(vec))
                    if np.isfinite(norm) and norm > 1e-6:
                        direction = vec / norm
            else:
                direction = directions.get(seg.name)
            if direction is not None:
                out[seg.long_axis_keypoint] = origin + direction * lengths[seg.name]
        return out, directions

    def reset(self) -> None:
        """Forget learned lengths and gap-fill directions.

        Clears the rolling-window length buffers (estimates fall back to the
        anthropometric seeds) and the carried per-segment gap-fill directions,
        so the next frames re-derive everything from fresh observations.
        """
        self._body_tree.reset()
        self._hand_tree_r.reset()
        self._hand_tree_l.reset()
        self._body_lengths.reset()
        self._rhand_lengths.reset()
        self._lhand_lengths.reset()

    @property
    def body_segment_lengths(self) -> dict[str, float]:
        return self._body_lengths.lengths

    @property
    def right_hand_segment_lengths(self) -> dict[str, float]:
        return self._rhand_lengths.lengths

    @property
    def left_hand_segment_lengths(self) -> dict[str, float]:
        return self._lhand_lengths.lengths
