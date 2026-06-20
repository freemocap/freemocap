"""
Per-frame center of mass calculation for the real-time pipeline.

Loads RTMPose body biomechanics from the existing skellyforge YAML
(validated once at init via AnatomicalStructure), then computes
whole-body and per-segment center of mass from a dict[str, np.ndarray]
of named 3D keypoint positions — the exact format the real-time
aggregator node already produces.

The anthropometric calculation follows the same Winter-table math as
``skellyforge.skellymodels.biomechanics.calculations.calculate_center_of_mass``,
adapted to operate on per-frame (3,) arrays instead of batch (F, 3) arrays.

Mass redistribution
-------------------
Missing distal segments have their mass percentage rolled up to the
nearest visible proximal segment along anatomical chains::

    foot → shank → thigh          (leg chain)
    forearm → upper_arm           (arm chain)

If an entire chain is invisible, its accumulated mass lands on the
*spine* (trunk). Spine and head mass is never redistributed.

Confidence tiers
----------------
A ``CoMConfidence`` enum and ``directly_observed_mass`` float are
included in every result so consumers can make their own validity
decisions. The CoM is always computed — never NaN-gated.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

import numpy as np
from pydantic import BaseModel, ConfigDict

from skellyforge.skellymodels.models.anatomical_structure import AnatomicalStructure
from skellyforge.skellymodels.models.tracking_model_info import RTMPoseModelInfo
from skellyforge.skellymodels.utils.types import (
    SegmentCenterOfMassDefinition,
    SegmentConnection,
    SegmentName,
    VirtualMarkerDefinition,
)

# ---------------------------------------------------------------------------
# Anatomical limb chains, distal → proximal.
# ---------------------------------------------------------------------------
_SEGMENT_CHAINS: list[list[str]] = [
    ["right_foot", "right_shank", "right_thigh"],
    ["left_foot", "left_shank", "left_thigh"],
    ["right_forearm", "right_upper_arm"],
    ["left_forearm", "left_upper_arm"],
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


def _build_mass_lookup(
    com_defs: dict[SegmentName, SegmentCenterOfMassDefinition],
) -> dict[str, float]:
    """Pre-extract per-segment mass percentages for fast hot-loop access."""
    return {seg: info["segment_com_percentage"] for seg, info in com_defs.items()}


class RTMPoseBodyBiomechanics(BaseModel):
    """Validated RTMPose body biomechanics, loaded once at aggregator init.

    Mirrors the relevant fields of skellyforge's ``AnatomicalStructure``
    so the hot loop never touches Pydantic validation.
    """

    tracked_point_names: list[str]
    virtual_markers_definitions: dict[str, VirtualMarkerDefinition] | None = None
    segment_connections: dict[SegmentName, SegmentConnection] | None = None
    center_of_mass_definitions: dict[SegmentName, SegmentCenterOfMassDefinition] | None = None

    # Pre-computed for the hot loop
    segment_chains: list[list[str]] = _SEGMENT_CHAINS
    mass_percentages: dict[str, float] = {}

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
        Per-segment center of mass positions (only computed segments).
    directly_observed_mass : float
        Fraction of total body mass from segments whose endpoints were
        directly observed (0.0–1.0). Mass from invisible chains placed
        on spine counts as 0.0.
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


def load_rtmpose_biomechanics() -> RTMPoseBodyBiomechanics:
    """Load and validate RTMPose body biomechanics from skellyforge YAML."""
    model_info = RTMPoseModelInfo()
    body_structure: AnatomicalStructure = AnatomicalStructure.from_model_info(
        model_info=model_info, aspect_name="body"
    )

    com_defs = body_structure.center_of_mass_definitions or {}

    return RTMPoseBodyBiomechanics(
        tracked_point_names=body_structure.tracked_point_names,
        virtual_markers_definitions=body_structure.virtual_markers_definitions,
        segment_connections=body_structure.segment_connections,
        center_of_mass_definitions=com_defs,
        mass_percentages=_build_mass_lookup(com_defs),
    )


# ---------------------------------------------------------------------------
# Per-frame hot-path functions (no logging, no Pydantic, no allocation)
# ---------------------------------------------------------------------------


def compute_virtual_markers(
    keypoints: dict[str, np.ndarray],
    vm_defs: dict[str, VirtualMarkerDefinition],
) -> dict[str, np.ndarray]:
    """Compute virtual markers via weighted average of component keypoints."""
    result: dict[str, np.ndarray] = {**keypoints}
    for vm_name, vm_info in vm_defs.items():
        try:
            components = [keypoints[name] for name in vm_info["marker_names"]]
        except KeyError:
            continue
        weights = np.array(vm_info["marker_weights"])
        result[vm_name] = np.average(np.column_stack(components), axis=1, weights=weights)
    return result


def build_segment_positions(
    keypoints: dict[str, np.ndarray],
    connections: dict[SegmentName, SegmentConnection],
) -> dict[str, dict[str, np.ndarray]]:
    """Build proximal/distal segment endpoint dict from named keypoints."""
    positions: dict[str, dict[str, np.ndarray]] = {}
    for seg_name, conn in connections.items():
        proximal = keypoints.get(conn["proximal"])
        distal = keypoints.get(conn["distal"])
        if proximal is None or distal is None:
            continue
        positions[seg_name] = {"proximal": proximal, "distal": distal}
    return positions


def _calculate_all_segments_com_per_frame(
    segment_positions: dict[str, dict[str, np.ndarray]],
    com_defs: dict[SegmentName, SegmentCenterOfMassDefinition],
) -> dict[str, np.ndarray]:
    """Per-frame segment center of mass (same math as skellyforge)."""
    result: dict[str, np.ndarray] = {}
    for seg_name, seg_info in com_defs.items():
        pos = segment_positions.get(seg_name)
        if pos is None:
            continue
        result[seg_name] = pos["proximal"] + (pos["distal"] - pos["proximal"]) * seg_info["segment_com_length"]
    return result


def _calculate_total_body_com_with_redistribution(
    segment_com_data: dict[str, np.ndarray],
    biomechanics: RTMPoseBodyBiomechanics,
) -> tuple[np.ndarray, float]:
    """Weighted total body CoM with mass redistribution along limb chains.

    Only a segment's *own* base mass counts as directly observed.
    Redistributed mass from missing distal segments and orphan mass
    placed on spine do NOT contribute to the directly-observed total.
    """
    base_mass = biomechanics.mass_percentages
    total = np.zeros(3)
    directly_observed = 0.0

    # Mass from entirely invisible chains → placed on spine, not directly observed.
    orphan_mass = 0.0

    for chain in biomechanics.segment_chains:
        accumulated = 0.0  # redistributed mass from missing distal segments
        for seg_name in chain:  # distal → proximal
            seg_com = segment_com_data.get(seg_name)
            seg_mass = base_mass.get(seg_name, 0.0)
            if seg_com is not None:
                # Visible — own mass is directly observed, accumulated is not.
                total += seg_com * (seg_mass + accumulated)
                directly_observed += seg_mass
                accumulated = 0.0
            else:
                accumulated += seg_mass

        if accumulated > 0.0:
            orphan_mass += accumulated

    # Spine: own mass directly observed; orphan mass is not.
    spine_com = segment_com_data.get("spine")
    if spine_com is not None:
        spine_own = base_mass.get("spine", 0.0)
        total += spine_com * (spine_own + orphan_mass)
        directly_observed += spine_own

    # Head: always directly observed when visible.
    head_com = segment_com_data.get("head")
    if head_com is not None:
        head_mass = base_mass.get("head", 0.0)
        total += head_com * head_mass
        directly_observed += head_mass

    return total, directly_observed


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def calculate_center_of_mass_per_frame(
    keypoints: dict[str, np.ndarray],
    biomechanics: RTMPoseBodyBiomechanics,
) -> CenterOfMassResult:
    """Compute whole-body and per-segment center of mass for one frame.

    Always returns a result — never NaN. Check ``confidence`` or
    ``directly_observed_mass`` to assess measurement quality.
    """
    if biomechanics.center_of_mass_definitions is None:
        raise ValueError("No center_of_mass_definitions in biomechanics.")
    if biomechanics.segment_connections is None:
        raise ValueError("No segment_connections in biomechanics.")

    # 1. Compute virtual markers
    if biomechanics.virtual_markers_definitions:
        augmented = compute_virtual_markers(
            keypoints, biomechanics.virtual_markers_definitions
        )
    else:
        augmented = keypoints

    # 2. Build segment endpoint dict (silently skips missing endpoints)
    segment_positions = build_segment_positions(
        augmented, biomechanics.segment_connections
    )

    # 3. Per-segment CoM (silently skips missing segments)
    segment_coms = _calculate_all_segments_com_per_frame(
        segment_positions, biomechanics.center_of_mass_definitions
    )

    # 4. Weighted total body CoM with mass redistribution
    total_body_com, directly_observed = _calculate_total_body_com_with_redistribution(
        segment_coms, biomechanics,
    )

    return CenterOfMassResult(
        total_body_com=total_body_com,
        segment_coms=segment_coms,
        directly_observed_mass=directly_observed,
        confidence=_confidence_from_mass(directly_observed),
    )
