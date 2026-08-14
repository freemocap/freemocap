"""Single-frame forward-pass rigidifier for the realtime pipeline.

This is the streaming counterpart of skellyforge's posthoc
``rigidify_forward_pass`` (``enforce_rigid_bones.py``). For one frame:

    * anchor each present root at its observed position,
    * walk the tree from the roots outward (topological / BFS order),
    * for each segment, take the direction from the *corrected* parent toward the
      observed child, normalize it, and place the child exactly ``length`` away.

The trees are keyed onto the **segment model** (the composed standard human),
not arrow-key joint pairs. Each segment's tree node is the segment *name*; the
node's observed position is that segment's ``origin_keypoint`` from the
tracker→standard-human mapping output (a mapping-produced point). An edge
parent→child exists only when ``child.origin_keypoint == parent's EXACT axis
target`` (the shared-keypoint chain — the EXACT axis is the segment's defining
direction); its enforced length is the *parent* segment's estimate, keyed by the
child node's name. Every other segment (origin-attached or keypoint-mismatched)
is a tree root, anchored at its observed position — no length is enforced on
those edges.

**Graded dispatch:** a segment whose ``rigid_points`` has ≥ 3 keypoints is a
rigid body in the ordinary sense and gets the per-group rigid fit (see below);
a 2-point segment keeps the span/edge path. Six segments qualify: ``head`` (7
points), ``hips`` (4), ``left_foot``/``right_foot`` (3),
``left_toes``/``right_toes`` (3).

**Per-group rigid fits.** Each ≥ 3-rigid-point segment owns a
``RigidPointTemplate`` holding its invariant pairwise distances (built from a
pair estimator dedicated to that group), and each frame the template is rigidly
placed onto the observed points with ``fit_template_to_observed``. The fit is a
rotation pinned at the segment's ``origin_keypoint`` (the anchor owns the
segment's position): for a tree root (``hips``) the anchor is the observed
origin; for a chain segment (``head``, the feet, the toes) it is the body
tree's *corrected* origin, so the tree owns the position and the fit only
rotates the rigid point set. The orientations of the exact/approximate axes are
*not* read positionally — every rigid point of the group rides the fit at its
template distance from the anchor.

The articulated face points (``jaw`` / ``left_mouth`` / ``right_mouth``) are
NOT in any rigid set. They (and any other segment origin keypoint or axis
target the tree and fits leave out) anchor at their observed position via a
general rule: after the tree + fit passes, any keypoint referenced by a
segment's origin or axes but missing from the output takes its observed
position. The 52 blendshape channels (ARKit) are declared-but-null and never
touch the rigidifier.

Keeping the observed direction but overriding the length is what makes the
skeleton track the subject's pose while holding rigid segment lengths. The
per-segment last-good direction is carried across frames, so a segment whose
origin drops out for a few frames is gap-filled along its last direction instead
of collapsing onto its parent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path  # noqa: TC003  # used at runtime in beartype-checked module-level type variables
from typing import Literal

import numpy as np

from skellytracker.core.io.tracker_mapping import TrackerMapping

from freemocap.core.streaming.standard_stream.stream_schema import (
    NOMINAL_SUBJECT_HEIGHT_MM,
)
from freemocap.core.tasks.mocap.tracker_mappings import (
    body_mapping_yaml_path,
    hand_mapping_yaml_path,
)

from skellyforge.kinematics.online_segment_lengths import SegmentLengthEstimator
from skellyforge.kinematics.rigid_point_set import (
    RigidPointTemplate,
    fit_template_to_observed,
)
from skellyforge.kinematics.skeleton_rigidifier import TreeRigidifier
from skellyforge.skellymodels.standard_human.face_part import FACE_PART
from skellyforge.skellymodels.standard_human.hand_part import HAND_PART
from skellyforge.skellymodels.standard_human.segment_definition import (
    AxisDefinition,
    AxisKind,
    SegmentDefinition,
)
from skellyforge.skellymodels.standard_human.standard_human_model import (
    StandardHuman,  # noqa: TC002  # used at runtime (beartype resolves the forward ref in `create`)
)

# The face's segments participate in the body tree as anatomical segments but
# their keypoints are covered by the head rigid set (eyes/nose/ears ride the
# head's rigid fit) or the orphan-anchor rule (jaw/mouths) — they need no tree
# treatment of their own. They stay out of the length ESTIMATOR for the same
# reason: their spans are either rigid on the head or nominal direction
# references.
_FACE_SEGMENT_NAMES: frozenset[str] = frozenset(s.name for s in FACE_PART.segments)

# Unprefixed hand-part segment names (the composed model's hand segments are
# ``left_``/``right_``-prefixed versions of these).
_HAND_SEGMENT_NAMES: frozenset[str] = frozenset(s.name for s in HAND_PART.segments)


# How often (in frames) each rigid-group template is rebuilt from the current
# pair medians. Rebuilds keep chirality/orientation stable by seeding the MDS
# with the previous template's positions. 30 frames ≈ once per second at 30fps.
_TEMPLATE_REBUILD_INTERVAL_FRAMES = 30


# ===========================================================================
# Hand tracker→standard-human mapping helper
# ===========================================================================


def _build_hand_mapping(yaml_path: Path, *, side: str) -> tuple[TrackerMapping, dict[str, str]]:
    """Build a hand tracker→standard-human mapping + a standard-human→tracker reverse map.

    Both RTMPose and MediaPipe compose hand landmarks with a uniform
    ``{side}_hand_`` prefix (``right_hand_thumb1`` ...), so the mapping strips
    that prefix to match the unprefixed entries in the mapping YAML
    (``thumb1`` ...). The reverse map converts fitted standard-human hand names
    back to tracker names so they key into the frontend's hand schema.
    """
    import yaml
    with open(yaml_path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    prefix = f"{side}_hand_"
    mapping = TrackerMapping(entries=raw, prefix=prefix)
    reverse_map = {standard: f"{prefix}{relative}" for standard, relative in raw.items()}
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
    the face's. Hand = side-prefixed hand-part names (``left_hand``,
    ``left_thumb_metacarpal``, ...); face = the ``FACE_PART`` segment names.
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


def _exact_axis(segment: SegmentDefinition) -> AxisDefinition:
    """The segment's EXACT axis (its defining direction), by ``kind``.

    The EXACT axis — regardless of which basis axis (x/y/z) it is tagged on —
    names the segment's shared-keypoint chain endpoint. Its ``target_keypoint``
    is the distal keypoint a child's ``origin_keypoint`` must equal for the two
    to chain.
    """
    for axis in segment.axes:
        if axis.kind is AxisKind.EXACT:
            return axis
    raise ValueError(
        f"segment {segment.name!r} has no EXACT axis — cannot derive its "
        "defining direction"
    )


def _exact_axis_target(segment: SegmentDefinition) -> str:
    """The EXACT axis's ``target_keypoint`` (the segment's defining endpoint)."""
    return _exact_axis(segment).target_keypoint


def _hierarchy(group: list[SegmentDefinition]) -> dict[str, list[str]]:
    """Parent → children over a group's SEGMENT names, following the shared-
    keypoint chain.

    An edge ``parent → child`` is kept only when ``child.origin_keypoint ==
    parent's EXACT axis target`` (name equality). Segments that are
    ORIGIN-attached or keypoint-mismatched are dropped from the hierarchy —
    ``TreeRigidifier`` then treats them as roots and anchors them at their
    observed position (no length enforced on those edges).

    Root segments (``parent is None``) are left out — ``TreeRigidifier`` derives
    its roots as parents that never appear as children. Parent keys that refer
    outside the group (e.g. ``left_hand``'s parent ``left_lower_arm``) are
    dropped: the hand tree is rooted at the ``*_hand`` segment.
    """
    name_to_seg = {seg.name: seg for seg in group}
    hierarchy: dict[str, list[str]] = {}
    for seg in group:
        if seg.parent is None:
            continue
        parent_seg = name_to_seg.get(seg.parent)
        if parent_seg is None:
            continue
        if seg.origin_keypoint != _exact_axis_target(parent_seg):
            continue
        hierarchy.setdefault(seg.parent, []).append(seg.name)
    return hierarchy


def _pair_key(a: str, b: str) -> tuple[str, str]:
    """Canonical (sorted) pair key for a pairwise distance."""
    return (a, b) if a <= b else (b, a)


def _canonical_pair_string(a: str, b: str) -> str:
    """The plain data key for a pair: ``"a|b"`` with names sorted."""
    ka, kb = _pair_key(a, b)
    return f"{ka}|{kb}"


def _all_pairs(names: tuple[str, ...]) -> list[tuple[str, str]]:
    """Every unordered pair (sorted) of the given names."""
    return [
        _pair_key(names[i], names[j])
        for i in range(len(names))
        for j in range(i + 1, len(names))
    ]


def _rigid_groups(
    segments: tuple[SegmentDefinition, ...],
) -> tuple[SegmentDefinition, ...]:
    """Every segment with ≥ 3 rigid points, in model order.

    Each such segment is a rigid body fit per frame with its own template and
    pair estimator. Derived from the model at ``create()`` — no hardcoded names.
    """
    return tuple(seg for seg in segments if len(seg.rigid_points) >= 3)


# ===========================================================================
# RealtimeSkeletonRigidifier
# ===========================================================================


@dataclass(slots=True)
class RigidifyResult:
    """Rigidified skeleton positions for one frame.

    ``body_positions`` is keyed by standard-human body keypoint names, including
    the corrected exact-axis endpoints (``head_vertex``, ``mid_sternum``-adjacent
    endpoints, ``foot_ball``, ``toes``, ...) so the solver and center-of-mass get
    every derived endpoint. The ≥ 3-rigid-point groups (``head``'s seven points,
    ``hips``'s four, both feet and toes) are rigidly aligned — their pairwise
    distances are held at the template's, the group's origin is the body tree's
    correction, and the rest ride the rotation-only fit. The articulated face
    points (``jaw`` / ``left_mouth`` / ``right_mouth``) anchor at their observed
    positions. Hand positions use the configured detector's side-prefixed
    tracker names (``right_hand_thumb1`` for RTMPose, ``right_hand_thumb_cmc``
    for MediaPipe) so they key into the frontend's hand schema. The
    ``*_standard_positions`` fields carry the same hand points keyed by the
    standard-human side-prefixed names (``left_wrist``,
    ``left_index_finger_tip``, ...), now including the corrected exact-axis
    endpoints (the finger tips), for the composed standard-human orientation
    solver. Trees with insufficient data (missing root) come back empty.
    """

    body_positions: dict[str, np.ndarray]
    left_hand_positions: dict[str, np.ndarray]
    right_hand_positions: dict[str, np.ndarray]
    left_hand_standard_positions: dict[str, np.ndarray]
    right_hand_standard_positions: dict[str, np.ndarray]


# Per-rigid-group state: the set of rigid point names, a pair estimator over
# them, the invariant template, and the rebuild bookkeeping.
@dataclass(slots=True)
class _RigidGroupState:
    """State for one ≥ 3-rigid-point segment's per-frame rigid fit."""

    segment: SegmentDefinition
    # The rigid points, in the model's declared order.
    points: tuple[str, ...]
    # The segment's origin keypoint (the fit anchor, present among ``points``).
    anchor: str
    # Pairwise-length estimator over the group's rigid set, keyed by the
    # canonical ``"a|b"`` pair strings.
    pairs: SegmentLengthEstimator
    # The invariant template, built from pair medians + a chirality/anchor
    # reference configuration. ``None`` until the first fully-observed frame.
    template: RigidPointTemplate | None = None
    # Frames processed since the last template (re)build.
    frames_since_template_build: int = 0


@dataclass
class RealtimeSkeletonRigidifier:
    """Per-frame rigid-body skeleton correction: map -> estimate -> rigidify.

    Created once at aggregator init for a specific detector type (RTMPose or
    MediaPipe — see ``create``) and a composed ``StandardHuman``. Each frame:
    map the configured detector's raw keypoints onto the standard-human body +
    hand keypoints, advance the per-segment length estimators with the
    **measured** (real, not extrapolated) keypoints, and run a single closed-form
    forward pass over the segment trees that holds the estimated lengths while
    following the observed pose, then place every ≥ 3-rigid-point group rigidly
    over its corrected origin.

    The trees are keyed onto the segment model: three groups (body, right hand,
    left hand) each get their own hierarchy, length estimator, and tree
    rigidifier. Every segment with ≥ 3 rigid points is additionally fit with a
    ``RigidPointTemplate`` over its rigid set, whose pairwise distances are
    estimated by a dedicated pair estimator. The fit is rotation-only, pinned at
    the segment's origin — for a tree root (``hips``) the observed origin, for a
    chain segment the body tree's corrected origin.
    """

    _body_mapping: TrackerMapping = field(repr=False)
    _hand_mapping_r: TrackerMapping = field(repr=False)
    _hand_mapping_l: TrackerMapping = field(repr=False)

    _body_segments: tuple[SegmentDefinition, ...] = field(repr=False)
    _rhand_segments: tuple[SegmentDefinition, ...] = field(repr=False)
    _lhand_segments: tuple[SegmentDefinition, ...] = field(repr=False)

    _body_tree: TreeRigidifier = field(repr=False)
    _hand_tree_r: TreeRigidifier = field(repr=False)
    _hand_tree_l: TreeRigidifier = field(repr=False)

    _body_lengths: SegmentLengthEstimator = field(repr=False)
    _rhand_lengths: SegmentLengthEstimator = field(repr=False)
    _lhand_lengths: SegmentLengthEstimator = field(repr=False)

    _hand_name_to_tracker_r: dict[str, str] = field(repr=False)
    _hand_name_to_tracker_l: dict[str, str] = field(repr=False)

    # ── Rigid-group state ─────────────────────────────────────────────────
    # Per-segment rigid-fit state for every ≥ 3-rigid-point body segment
    # (``head``, ``hips``, both feet, both toes), keyed by segment name.
    _rigid_groups: dict[str, _RigidGroupState] = field(repr=False, default_factory=dict)

    height_mm: float = NOMINAL_SUBJECT_HEIGHT_MM

    @classmethod
    def create(
        cls,
        *,
        standard_human: StandardHuman,
        detector_type: Literal["rtmpose", "mediapipe"] = "rtmpose",
        height_mm: float = NOMINAL_SUBJECT_HEIGHT_MM,
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

        # The body TREE carries the body segments *plus* the face segments (its
        # anatomical segments enter as potential roots), while the length
        # ESTIMATOR stays body-only (face spans are covered by the head rigid
        # set or the orphan-anchor rule, not lengths to enforce).
        body_tree_group = [*body, *face]

        body_mapping = TrackerMapping.from_yaml(body_mapping_yaml_path(detector_type))
        hand_yaml = hand_mapping_yaml_path(detector_type)
        hand_mapping_r, name_to_tracker_r = _build_hand_mapping(hand_yaml, side="right")
        hand_mapping_l, name_to_tracker_l = _build_hand_mapping(hand_yaml, side="left")

        def make_spec(group: list[SegmentDefinition]) -> tuple[
            SegmentLengthEstimator,
            dict[str, tuple[str, str]],
        ]:
            seeds = {seg.name: seg.length_ratio * height_mm for seg in group}
            endpoints = {
                seg.name: (seg.origin_keypoint, _exact_axis_target(seg))
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

        # ── Rigid-group pair estimators ───────────────────────────────────
        # Every ≥ 3-rigid-point body segment gets a pair estimator over its
        # rigid points, so its template can hold the invariant pairwise
        # distances. Seeds are nominal placeholders replaced by measured medians
        # within a frame or two of full observation (they only exist so the
        # estimator's ``lengths`` has a value before the first measurement).
        rigid_groups: dict[str, _RigidGroupState] = {}
        for seg in _rigid_groups(standard_human.segments):
            points = tuple(seg.rigid_points)
            pair_endpoints = {
                _canonical_pair_string(a, b): (a, b)
                for a, b in _all_pairs(points)
            }
            pair_seeds = {key: 0.02 * height_mm for key in pair_endpoints}
            pairs = SegmentLengthEstimator(
                segment_endpoints=pair_endpoints,
                segment_seeds=pair_seeds,
                window_seconds=window_s,
            )
            rigid_groups[seg.name] = _RigidGroupState(
                segment=seg,
                points=points,
                anchor=seg.origin_keypoint,
                pairs=pairs,
            )

        return cls(
            _body_mapping=body_mapping,
            _hand_mapping_r=hand_mapping_r,
            _hand_mapping_l=hand_mapping_l,
            _body_segments=tuple(body_tree_group),
            _rhand_segments=tuple(rhand),
            _lhand_segments=tuple(lhand),
            _body_tree=TreeRigidifier(joint_hierarchy=_hierarchy(body_tree_group)),
            _hand_tree_r=TreeRigidifier(joint_hierarchy=_hierarchy(rhand)),
            _hand_tree_l=TreeRigidifier(joint_hierarchy=_hierarchy(lhand)),
            _body_lengths=body_lengths,
            _rhand_lengths=rhand_lengths,
            _lhand_lengths=lhand_lengths,
            _hand_name_to_tracker_r=name_to_tracker_r,
            _hand_name_to_tracker_l=name_to_tracker_l,
            _rigid_groups=rigid_groups,
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
        standard_body = self._body_mapping.apply(tracker_positions)
        # The hand mapping produces UNPREFIXED standard names (``wrist``,
        # ``thumb_cmc``, ...); the segment model references side-prefixed ones
        # (``left_wrist``, ...). Prefix here so positions key into the trees.
        standard_rhand = _prefix_keypoints(
            self._hand_mapping_r.apply(tracker_positions), "right_"
        )
        standard_lhand = _prefix_keypoints(
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
            standard_body,
            self._body_lengths.lengths,
        )
        rhand_out, _ = self._rigidify_group(
            self._rhand_segments,
            self._hand_tree_r,
            standard_rhand,
            self._rhand_lengths.lengths,
        )
        lhand_out, _ = self._rigidify_group(
            self._lhand_segments,
            self._hand_tree_l,
            standard_lhand,
            self._lhand_lengths.lengths,
        )

        body_positions = body_out

        # ── Rigid-group fits (body only — the hand groups have no rigid body) ─
        self._apply_rigid_group_fits(
            body_positions=body_positions,
            measured_body=measured_body,
            standard_body=standard_body,
            t=t,
        )

        # ── Orphan-anchor rule ────────────────────────────────────────────
        # Any keypoint the tree + fits left out of the output takes its observed
        # position so no tracked keypoint silently vanishes. This covers every
        # keypoint a group's segments reference — a segment's origin and every
        # axis' target keypoint (the approximate axes' twist-direction
        # keypoints — e.g. ``left_heel``/``right_heel`` on the foot and
        # ``left_small_toe``/``right_small_toe`` on the toes — are never part of
        # the tree output). Roots/orphans alone (the articulated face points
        # ``jaw`` / ``left_mouth`` / ``right_mouth``) are each some segment's
        # origin, so a single pass over every segment's origin + axis targets is
        # the general rule.
        for seg in self._body_segments:
            referenced = {seg.origin_keypoint}
            referenced.add(_exact_axis_target(seg))
            for axis in seg.axes:
                referenced.add(axis.target_keypoint)
            for keypoint in referenced:
                if keypoint not in body_positions:
                    obs = standard_body.get(keypoint)
                    if obs is not None:
                        body_positions[keypoint] = obs

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
        # orientation solver directly, corrected exact-axis endpoints included.
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

    def _apply_rigid_group_fits(
        self,
        *,
        body_positions: dict[str, np.ndarray],
        measured_body: dict[str, np.ndarray],
        standard_body: dict[str, np.ndarray],
        t: float,
    ) -> None:
        """Advance each rigid group's pair estimator and place its template.

        For every ≥ 3-rigid-point segment, the pair estimator is advanced with
        the group's rigid points from the MAPPING OUTPUT (the ``standard_body``
        positions), using the real-only ``measured`` variant — extrapolated
        points never teach lengths. The template is then fit onto the observed
        rigid points. The anchor is the segment's origin:

        * For a tree root (``hips``) — ``parent is None`` on the tree — the
          anchor is the OBSERVED origin (the root owns its position); the fit
          is rotation-only.
        * For a chain segment (``head``, the feet, the toes) the anchor is the
          body tree's CORRECTED origin (the tree's chain owns the position);
          the fit only rotates the rigid point set.

        Template build/rebuild policy:

        * The FIRST build happens at the first frame where every rigid point is
          observed, using the current pair medians and
          ``reference_configuration =`` that frame's observed positions — the
          real-data chirality anchor.
        * Subsequent REBUILDS — every ``_TEMPLATE_REBUILD_INTERVAL_FRAMES``
          frames, or on ``reset()`` — pass the PREVIOUS template's positions as
          the reference configuration, keeping chirality + orientation stable.
        """
        for state in self._rigid_groups.values():
            points = state.points

            # Advance the pair estimator with measured points (real only).
            measured_points = {
                name: measured_body[name]
                for name in points
                if name in measured_body
            }
            state.pairs.update(measured_points, t=t)

            # Observed points from the mapping output; missing/non-finite points
            # are dropped — the fit extrapolates them from the template.
            observed_points = {
                name: standard_body[name]
                for name in points
                if name in standard_body and np.all(np.isfinite(standard_body[name]))
            }

            all_observed = all(name in observed_points for name in points)

            if all_observed and (
                state.template is None
                or state.frames_since_template_build >= _TEMPLATE_REBUILD_INTERVAL_FRAMES
            ):
                pair_distances = self._pair_distances(state)
                reference_configuration: dict[str, np.ndarray] = (
                    {name: state.template.positions[points.index(name)]
                     for name in points}
                    if state.template is not None
                    else dict(observed_points)
                )
                state.template = RigidPointTemplate.from_distances(
                    point_names=list(points),
                    pair_distances=pair_distances,
                    reference_configuration=reference_configuration,
                )
                state.frames_since_template_build = 0

            if state.template is None:
                # No template yet (not enough points observed this frame) — the
                # group's points stay at whatever the tree produced; the orphan
                # anchor rule below fills in any observed point the tree missed.
                continue

            # Anchor: the tree's corrected origin for chain segments, the
            # observed origin for tree roots.
            anchor_observed = body_positions.get(state.anchor)
            if anchor_observed is None:
                anchor_observed = standard_body.get(state.anchor)

            if (
                anchor_observed is not None
                and np.all(np.isfinite(anchor_observed))
                and state.anchor in observed_points
            ):
                observed_points = {**observed_points, state.anchor: anchor_observed}

            corrected = fit_template_to_observed(
                state.template,
                observed_points,
                anchor_name=state.anchor,
            )

            # Merge the corrected group into body_positions, overwriting what
            # the tree wrote for the group's rigid points.
            for name in points:
                pos = corrected.get(name)
                if pos is not None and np.all(np.isfinite(pos)):
                    body_positions[name] = pos

            state.frames_since_template_build += 1

    def _pair_distances(self, state: _RigidGroupState) -> dict[tuple[str, str], float]:
        """The current pair medians, keyed by the template's ``(a, b)`` tuples."""
        lengths = state.pairs.lengths
        return {
            _pair_key(a, b): lengths[_canonical_pair_string(a, b)]
            for a, b in _all_pairs(state.points)
        }

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
        segment's corrected origin plus its corrected exact-axis endpoint) and
        ``used_directions`` maps each SEGMENT name to the unit direction
        actually used.
        """
        name_to_seg = {seg.name: seg for seg in group}
        # Segment-keyed observed origins: this segment's node is its origin
        # keypoint from the mapping output (drop missing).
        positions = {
            seg.name: observed_keypoints[seg.origin_keypoint]
            for seg in group
            if seg.origin_keypoint in observed_keypoints
        }
        # Edge lengths follow the shared-keypoint chain: the enforced length for
        # a kept edge is the PARENT segment's estimate, keyed by the CHILD
        # node's name. Only edges father→child where child.origin_keypoint ==
        # father's EXACT axis target get an entry; roots have none.
        lengths_dict: dict[str, float] = {}
        for seg in group:
            if seg.parent is None:
                continue
            parent_seg = name_to_seg.get(seg.parent)
            if parent_seg is None:
                continue
            if seg.origin_keypoint != _exact_axis_target(parent_seg):
                continue
            lengths_dict[seg.name] = lengths[seg.parent]

        corrected, directions = tree.rigidify(
            positions, lengths_dict, return_directions=True
        )

        # Convert corrected segment origins into corrected KEYPOINT positions in
        # two phases over the group's segments.
        origin_set = {seg.origin_keypoint for seg in group}

        # Phase 1 (origins): each segment's corrected origin, under its origin
        # keypoint.
        out: dict[str, np.ndarray] = {}
        for seg in group:
            origin = corrected.get(seg.name)
            if origin is not None:
                out[seg.origin_keypoint] = origin

        # Phase 2 (exact-axis endpoints, only for keypoints NO segment's origin
        # owns). Leaf segments (``left_toes``, the finger distals) are extruded
        # from the observed origin→exact-axis direction at the segment's own
        # length. Face segments are SKIPPED here — their keypoints ride the head
        # rigid set or the orphan-anchor rule, not the tree. ≥ 3-rigid-point
        # segments are also skipped — their exact-axis endpoints are placed by the
        # rigid-group fit, not extruded here.
        for seg in group:
            distal_kp = _exact_axis_target(seg)
            if distal_kp in origin_set:
                continue
            if seg.name in _FACE_SEGMENT_NAMES:
                continue
            if seg.name in self._rigid_groups:
                continue
            origin = corrected.get(seg.name)
            observed_origin = positions.get(seg.name)
            observed_distal = observed_keypoints.get(distal_kp)
            if origin is None or observed_origin is None or observed_distal is None:
                continue
            vec = np.asarray(observed_distal, dtype=float) - np.asarray(
                observed_origin, dtype=float
            )
            norm = float(np.linalg.norm(vec))
            if np.isfinite(norm) and norm > 1e-6:
                out[distal_kp] = origin + (vec / norm) * lengths[seg.name]

        return out, directions

    def reset(self) -> None:
        """Forget learned lengths, the rigid-group templates, and gap directions.

        Clears the rolling-window length buffers (estimates fall back to the
        anthropometric seeds), the rigid-group templates (next fully-observed
        frame rebuilds them), and the carried per-segment gap-fill directions,
        so the next frames re-derive everything from fresh observations.
        """
        self._body_tree.reset()
        self._hand_tree_r.reset()
        self._hand_tree_l.reset()
        self._body_lengths.reset()
        self._rhand_lengths.reset()
        self._lhand_lengths.reset()
        for state in self._rigid_groups.values():
            state.template = None
            state.frames_since_template_build = 0
            state.pairs.reset()

    @property
    def body_segment_lengths(self) -> dict[str, float]:
        return self._body_lengths.lengths

    @property
    def right_hand_segment_lengths(self) -> dict[str, float]:
        return self._rhand_lengths.lengths

    @property
    def left_hand_segment_lengths(self) -> dict[str, float]:
        return self._lhand_lengths.lengths
