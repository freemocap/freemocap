"""
Per-frame center of mass calculation for the real-time pipeline.

Computes whole-body and per-segment center of mass from a ``dict[str, np.ndarray]``
of named 3D positions — the exact standard-human-named format the real-time
aggregator node produces after rigidification — using the de Leva (1996)
body-segment inertial parameters (BSIP) rather than the retired Winter table.

Reference
---------
de Leva, P. (1996). *Adjustments to Zatsiorsky-Seluyanov's segment inertia
parameters.* Journal of Biomechanics, 29(9), 1223–1230, Table 4. Values are
provided by ``skellyforge.kinematics.inertial.anthropometric_parameters``,
referenced to **joint centres** (which is what the standard-human landmarks are),
unlike Winter's bony-landmark table (which is why the old model needed a ``head``
segment spanning ear-to-ear).

Segment mapping (de Leva → FreeMoCap, documented with provenance)
-----------------------------------------------------------------
de Leva's 8 segments are mapped onto the standard-human landmark spans below;
**every VRM segment outside a mapped span carries zero mass** — its anatomy
lives inside a mapped span:

* ``hips`` / ``spine`` / ``chest`` / ``upper_chest`` individually, and ``shoulder``
  (the sternoclavicular→shoulder clavicle piece): zero mass, inside ``trunk``.
* ``neck`` (a VRM segment, not a de Leva segment): de Leva's head **includes the
  neck**, so ``neck`` is part of the mapped ``head`` span (below).
* ``eyes`` / ``jaw`` (the driven face bones): zero mass, inside ``head``.
* the four finger segments and ``toes``: zero mass — fingers are inside de Leva's
  ``hand`` mass; ``toes`` is inside de Leva's ``foot``.

Mass redistribution
-------------------
Missing distal segments have their mass fraction rolled up to the nearest
visible proximal segment along anatomical chains::

    foot → shank → thigh          (leg chains, ×2 sides)
    hand → forearm → upper_arm    (arm chains, ×2 sides)

If an entire chain is invisible, its accumulated mass lands on the **trunk**.
Trunk and head mass is never redistributed.

Confidence tiers
----------------
A ``CoMConfidence`` enum and ``directly_observed_mass`` float are included in
every result so consumers can make their own validity decisions. The CoM is
always computed — never NaN-gated.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict

from skellyforge.kinematics.inertial.anthropometric_parameters import (
    SegmentInertialParameters,
    segment_inertial_parameters,
)
from skellytracker.core.io.tracker_mapping import TrackerMapping

from freemocap.core.tasks.mocap.tracker_mappings import (
    body_mapping_yaml_path,
)


# ---------------------------------------------------------------------------
# The de Leva → FreeMoCap span table (module constant, single source of truth).
#
# Each de Leva segment maps to (proximal_keypoint, distal_keypoint) for a single
# side; limb segments are expanded to ``f"{side}_{segment}"`` for ``left_`` /
# ``right_``, and the midline segments (``head``, ``trunk``) are side-less.
# ``com_fraction`` is measured from the **proximal** (or cranial) endpoint, so
#   com = proximal + com_fraction × (distal − proximal)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Span:
    """A de Leva segment's two endpoint keypoint names (side-agnostic)."""

    proximal: str
    distal: str
    # Whether the segment is a paired limb (expanded to left_/right_) or a
    # midline segment (head/trunk).
    sided: bool


# de Leva head includes the neck → the span is neck_center → head_vertex.
# de Leva trunk: suprasternale ≈ mid_sternum (cranial), mid-hip ≈ hips_center
#   (caudal); com_fraction is from the CRANIAL end, i.e. mid_sternum first.
# upper_arm span is shoulder → elbow (the GH joint is origin — reported clean).
# forearm span is elbow → wrist.
# hand span is wrist → middle_finger_tip (dactylion III; the fingers carry no
#   separate de Leva mass — they are inside the hand).
# thigh span is hip → knee.
# shank span is knee → ankle.
# foot span is ankle → foot_ball (metatarsale II); toes carry zero mass (inside
#   de Leva's foot).
_DE_LEVA_SPANS: dict[str, _Span] = {
    "head": _Span("neck_center", "head_vertex", sided=False),
    "trunk": _Span("mid_sternum", "hips_center", sided=False),
    "upper_arm": _Span("shoulder", "elbow", sided=True),
    "forearm": _Span("elbow", "wrist", sided=True),
    "hand": _Span("wrist", "middle_finger_tip", sided=True),
    "thigh": _Span("hip", "knee", sided=True),
    "shank": _Span("knee", "ankle", sided=True),
    "foot": _Span("ankle", "foot_ball", sided=True),
}

_SIDES: tuple[str, str] = ("left", "right")


def _segment_key(de_leva_name: str, side: str) -> str:
    """Return the side-prefixed segment name used in ``segment_coms``."""
    return f"{side}_{de_leva_name}"


# ---------------------------------------------------------------------------
# Anatomical limb chains, distal → proximal, as (de Leva name, segment key)
# tuples. The de Leva name is carried alongside its side-prefixed segment key
# so downstream mass lookups never derive the name back out of the key by
# string parsing.
# ---------------------------------------------------------------------------

_SEGMENT_CHAINS: list[list[tuple[str, str]]] = [
    [
        ("foot", _segment_key("foot", side)),
        ("shank", _segment_key("shank", side)),
        ("thigh", _segment_key("thigh", side)),
    ]
    for side in _SIDES
] + [
    [
        ("hand", _segment_key("hand", side)),
        ("forearm", _segment_key("forearm", side)),
        ("upper_arm", _segment_key("upper_arm", side)),
    ]
    for side in _SIDES
]


# ---------------------------------------------------------------------------
# Confidence tiers
# ---------------------------------------------------------------------------


class CoMConfidence(IntEnum):
    """Ordered confidence tier for a center-of-mass estimate.

    Values are ordered so ``>=`` comparisons work naturally.
    """

    invalid = 0
    low = 1
    medium = 2
    high = 3


# Directly-observed-mass thresholds for each tier.
_CONFIDENCE_THRESHOLDS: list[tuple[float, CoMConfidence]] = [
    (0.90, CoMConfidence.high),
    (0.70, CoMConfidence.medium),
    (0.50, CoMConfidence.low),
]


def _confidence_from_mass(directly_observed: float) -> CoMConfidence:
    for threshold, tier in _CONFIDENCE_THRESHOLDS:
        if directly_observed >= threshold:
            return tier
    return CoMConfidence.invalid


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class BodyBiomechanics(BaseModel):
    """Validated body biomechanics for the realtime pipeline, loaded once at
    aggregator init.

    Carries the de Leva (1996) inertial-parameter table (mass fractions and
    segment-CoM fractions, keyed by de Leva segment name), plus the
    tracker→standard-human mapping used to derive the span endpoint landmarks
    each frame. The span table is a module constant (``_DE_LEVA_SPANS``), not a
    field — it is static data and never varies per subject.

    No Pydantic validation touches the hot loop: ``tracker_mapping`` is applied
    once per frame to produce standard-human landmark names, and the span/table
    lookups are plain dicts.
    """

    tracker_mapping: TrackerMapping
    de_leva: dict[str, SegmentInertialParameters]
    sex: Literal["mean", "female", "male"] = "mean"

    model_config = ConfigDict(arbitrary_types_allowed=True)


@dataclass(slots=True)
class CenterOfMassResult:
    """Per-frame center of mass output.

    Attributes
    ----------
    total_body_com : np.ndarray of shape (3,)
        Whole-body center of mass in 3D world coordinates. Always
        populated — never NaN.
    segment_coms : dict[str, np.ndarray]
        Per-segment center of mass positions, keyed by side-prefixed de Leva
        name (``left_thigh``, ``trunk``, ``head``, …) for the segments whose
        span endpoints were present this frame.
    directly_observed_mass : float
        Fraction of total body mass from segments whose endpoints were
        directly observed (0.0–1.0). Mass from invisible chains placed
        on trunk counts as 0.0.
    confidence : CoMConfidence
        Tiered confidence based on directly_observed_mass.
    """

    total_body_com: np.ndarray
    segment_coms: dict[str, np.ndarray]
    directly_observed_mass: float = 0.0
    confidence: CoMConfidence = CoMConfidence.invalid


# ---------------------------------------------------------------------------
# Loading (called once at aggregator init)
# ---------------------------------------------------------------------------


def load_body_biomechanics(
    detector_type: Literal["rtmpose", "mediapipe"] = "rtmpose",
    sex: Literal["mean", "female", "male"] = "mean",
) -> BodyBiomechanics:
    """Load body biomechanics from the de Leva (1996) BSIP table.

    The de Leva table comes from skellyforge's ``segment_inertial_parameters``
    (default: the mean of the female/male tables); span endpoints are derived
    each frame via the skellytracker tracker→standard-human mapping for the
    given ``detector_type`` (the same one the skeleton fitter uses).
    """
    return BodyBiomechanics(
        tracker_mapping=TrackerMapping.from_yaml(body_mapping_yaml_path(detector_type)),
        de_leva=segment_inertial_parameters(sex),
        sex=sex,
    )


# ---------------------------------------------------------------------------
# Per-frame hot-path functions (no logging, no Pydantic, no allocation)
# ---------------------------------------------------------------------------


def _build_span_endpoints(
    keypoints: dict[str, np.ndarray],
) -> dict[str, tuple[str, dict[str, np.ndarray]]]:
    """Resolve the proximal/distal endpoint of every de Leva span for this frame.

    Returns a dict keyed by *final segment key* (``trunk``, ``head``,
    ``left_thigh``, …) → ``(de_leva_name, {"proximal": ... , "distal": ...})``.
    The de Leva name is carried alongside its endpoints so downstream lookups
    never derive it back out of the key by string parsing. A span whose endpoint
    is absent this frame is omitted — the redistribution handles it.
    """
    endpoints: dict[str, tuple[str, dict[str, np.ndarray]]] = {}
    for de_leva_name, span in _DE_LEVA_SPANS.items():
        if span.sided:
            for side in _SIDES:
                proximal = keypoints.get(f"{side}_{span.proximal}")
                distal = keypoints.get(f"{side}_{span.distal}")
                if proximal is None or distal is None:
                    continue
                endpoints[_segment_key(de_leva_name, side)] = (
                    de_leva_name,
                    {"proximal": proximal, "distal": distal},
                )
        else:
            proximal = keypoints.get(span.proximal)
            distal = keypoints.get(span.distal)
            if proximal is None or distal is None:
                continue
            endpoints[de_leva_name] = (
                de_leva_name,
                {"proximal": proximal, "distal": distal},
            )
    return endpoints


def _calculate_all_segments_com_per_frame(
    span_endpoints: dict[str, tuple[str, dict[str, np.ndarray]]],
    de_leva: dict[str, SegmentInertialParameters],
) -> dict[str, np.ndarray]:
    """Per-frame segment center of mass, de Leva (1996) math.

    For every present span, ``com = proximal + com_fraction × (distal − proximal)``.
    The trunk's ``com_fraction`` is measured from the CRANIAL end (suprasternale
    ≈ mid_sternum), so ``trunk`` follows the same formula with ``mid_sternum`` as
    ``proximal``.
    """
    result: dict[str, np.ndarray] = {}
    for seg_key, (de_leva_name, endpoints) in span_endpoints.items():
        seg_info = de_leva.get(de_leva_name)
        if seg_info is None:
            continue
        proximal = endpoints["proximal"]
        distal = endpoints["distal"]
        result[seg_key] = proximal + (distal - proximal) * seg_info.com_fraction
    return result


def _calculate_total_body_com_with_redistribution(
    segment_com_data: dict[str, np.ndarray],
    de_leva: dict[str, SegmentInertialParameters],
) -> tuple[np.ndarray, float]:
    """Weighted total body CoM with mass redistribution along limb chains.

    Only a segment's *own* base mass counts as directly observed.
    Redistributed mass from missing distal segments and orphan mass
    placed on trunk do NOT contribute to the directly-observed total.

    Chains are de Leva limbs (foot/shank/thigh and hand/forearm/upper_arm)
    ×2 sides, distal → proximal. Trunk and head mass are never redistributed;
    an entirely invisible chain's accumulated mass lands on trunk.
    """
    total = np.zeros(3)
    directly_observed = 0.0

    # Mass from entirely invisible chains → placed on trunk, not directly observed.
    orphan_mass = 0.0

    for chain in _SEGMENT_CHAINS:
        accumulated = 0.0  # redistributed mass from missing distal segments
        for de_leva_name, seg_key in chain:  # distal → proximal
            seg_com = segment_com_data.get(seg_key)
            seg_mass = de_leva[de_leva_name].mass_fraction
            if seg_com is not None:
                # Visible — own mass is directly observed, accumulated is not.
                total += seg_com * (seg_mass + accumulated)
                directly_observed += seg_mass
                accumulated = 0.0
            else:
                accumulated += seg_mass

        if accumulated > 0.0:
            orphan_mass += accumulated

    # Trunk: own mass directly observed; orphan mass is not.
    trunk_com = segment_com_data.get("trunk")
    if trunk_com is not None:
        trunk_mass = de_leva["trunk"].mass_fraction
        total += trunk_com * (trunk_mass + orphan_mass)
        directly_observed += trunk_mass

    # Head: always directly observed when visible.
    head_com = segment_com_data.get("head")
    if head_com is not None:
        head_mass = de_leva["head"].mass_fraction
        total += head_com * head_mass
        directly_observed += head_mass

    return total, directly_observed


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Extrapolated Center of Mass (Hof 2008)
# ---------------------------------------------------------------------------
# XCoM = CoM + v / ω₀   where ω₀ = √(g / l)
#   g = 9810 mm/s²  (gravitational acceleration in keypoint-coordinate units)
#   l = CoM height above ground (z coordinate, mm)
#   v = CoM velocity (mm/s, from frame-to-frame position difference)
#
# The XCoM is a point on the ground plane (z=0) that predicts where the CoM
# would come to rest if the body were modeled as an inverted pendulum. It is
# offset from the vertical projection by v_xy / ω₀ in the direction of travel.
# All units are mm — the coordinate system is set by the ChArUco calibration.

_GRAVITY: float = 9810.0  # mm/s²  (9.81 m/s² in keypoint-coordinate units)


def calculate_xcom(
    *,
    com: np.ndarray,
    prev_com: np.ndarray,
    dt: float,
) -> np.ndarray:
    """Compute the extrapolated center of mass (Hof 2008) for one frame.

    Parameters
    ----------
    com : np.ndarray of shape (3,)
        Current whole-body center of mass (x, y, z) in world coordinates.
        z is the height above the ground plane.
    prev_com : np.ndarray of shape (3,)
        Previous frame's CoM position.
    dt : float
        Time delta since the previous frame, in seconds.

    Returns
    -------
    np.ndarray of shape (3,)
        XCoM position on the ground plane: (x_xcom, y_xcom, 0).
    """
    l = com[2]  # pendulum length = CoM height above ground
    if l <= 0.0:
        raise ValueError(f"CoM height must be positive, got {l}")
    omega_0 = np.sqrt(_GRAVITY / l)
    v = (com - prev_com) / dt
    return np.array([
        com[0] + v[0] / omega_0,
        com[1] + v[1] / omega_0,
        0.0,
    ])


def calculate_center_of_mass_per_frame(
    keypoints: dict[str, np.ndarray],
    biomechanics: BodyBiomechanics,
) -> CenterOfMassResult:
    """Compute center of mass from raw **tracker** keypoints for one frame.

    Maps tracker keypoints → standard-human landmarks (adding the derived span
    endpoints mid_sternum / head_vertex / foot_ball, etc.), then delegates to
    ``calculate_center_of_mass``.
    """
    standard_human_positions = biomechanics.tracker_mapping.apply(keypoints)
    return calculate_center_of_mass(standard_human_positions, biomechanics)


def calculate_center_of_mass(
    standard_human_positions: dict[str, np.ndarray],
    biomechanics: BodyBiomechanics,
) -> CenterOfMassResult:
    """Compute center of mass from already standard-human-named positions for one frame.

    Use this with the rigidified skeleton (``RealtimeSkeletonRigidifier`` output),
    whose positions are already standard-human-named and include the derived span
    endpoints. The input is still augmented per-frame by the tracker mapping at
    the *aggregator call site* (so it carries mid_sternum / head_vertex /
    foot_ball and the hand finger tips that ``body_positions`` alone lacks), but
    this path applies no remap itself.

    Always returns a result — never NaN. Check ``confidence`` or
    ``directly_observed_mass`` to assess measurement quality.
    """
    # 1. Resolve span endpoints (silently skips spans missing an endpoint).
    span_endpoints = _build_span_endpoints(standard_human_positions)

    # 2. Per-segment CoM (de Leva; silently skips missing spans).
    segment_coms = _calculate_all_segments_com_per_frame(
        span_endpoints, biomechanics.de_leva
    )

    # 3. Weighted total body CoM with mass redistribution.
    total_body_com, directly_observed = _calculate_total_body_com_with_redistribution(
        segment_coms, biomechanics.de_leva
    )

    return CenterOfMassResult(
        total_body_com=total_body_com,
        segment_coms=segment_coms,
        directly_observed_mass=directly_observed,
        confidence=_confidence_from_mass(directly_observed),
    )
