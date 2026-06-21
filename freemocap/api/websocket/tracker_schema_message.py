"""
Tracker-schema handshake message.

Sent once when a WebSocket client connects, and rebroadcast if the pipeline's
tracker configuration changes. Carries every active tracker's
`TrackedObjectDefinition` so the frontend can render points and connections
without hardcoding any tracker schema.
"""
from typing import Any

import msgspec
from skellytracker.trackers.base_tracker.tracked_object_definition import TrackedObjectDefinition
from skellytracker.trackers.rtmpose_tracker.names_and_connections import RTMPOSE_WHOLEBODY_DEFINITION

from freemocap.api.websocket.websocket_message_types import WebsocketMessageType


class TrackerSchemasMessage(msgspec.Struct):
    """Dict of ``tracker_id -> TrackedObjectDefinition.model_dump()``.

    Values are pre-serialized to plain dicts because msgspec.Struct cannot
    carry arbitrary Pydantic models directly. The frontend treats the inner
    dicts as the canonical TS ``TrackedObjectDefinition`` shape.
    """
    schemas: dict[str, dict[str, Any]]
    message_type: WebsocketMessageType = WebsocketMessageType.TRACKER_SCHEMAS


def _build_canonical_schema(
    *,
    name: str,
    landmark_names: list[str],
    segment_connections: dict[str, dict[str, str]] | None,
) -> TrackedObjectDefinition | None:
    """Build a ``TrackedObjectDefinition`` from canonical anatomical data.

    Parameters
    ----------
    name : str
        Schema identifier (e.g. ``"canonical_body"``).
    landmark_names : list of str
        All landmark names (tracked + virtual markers).
    segment_connections : dict or None
        Mapping of segment name → ``{"proximal": name, "distal": name}``.
        If ``None``, the schema carries no connections.
    """
    connections: tuple[tuple[str, str], ...] = ()
    if segment_connections is not None:
        connections = tuple(
            (conn["proximal"], conn["distal"])
            for conn in segment_connections.values()
        )
    return TrackedObjectDefinition(
        name=name,
        tracker_type="canonical",
        landmark_schema="canonical",
        tracked_points=tuple(landmark_names),
        connections=connections,
    )


def collect_active_tracker_schemas() -> dict[str, dict[str, Any]]:
    """Collect every active tracker schema the freemocap pipeline can emit.

    Includes the RTMPose wholebody definition (for 2D overlay + keypoint
    classification) and the canonical body/hand definitions (for 3D
    skeleton connections).
    """
    from skellyforge.skellymodels.models.anatomical_structure import AnatomicalStructure
    from skellyforge.skellymodels.models.tracking_model_info import (
        CanonicalBodyModelInfo,
        CanonicalHandModelInfo,
    )

    active: dict[str, TrackedObjectDefinition] = {
        RTMPOSE_WHOLEBODY_DEFINITION.name: RTMPOSE_WHOLEBODY_DEFINITION,
    }

    # Canonical body schema
    try:
        body_info = CanonicalBodyModelInfo()
        body_anatomy = AnatomicalStructure.from_model_info(body_info, "body")
        body_schema = _build_canonical_schema(
            name="canonical_body",
            landmark_names=body_anatomy.landmark_names,
            segment_connections=body_anatomy.segment_connections,
        )
        active[body_schema.name] = body_schema
    except Exception:
        pass  # canonical YAML not installed — skip gracefully

    # Canonical hand schema
    try:
        hand_info = CanonicalHandModelInfo()
        hand_anatomy = AnatomicalStructure.from_model_info(hand_info, "hand")
        hand_schema = _build_canonical_schema(
            name="canonical_hand",
            landmark_names=hand_anatomy.landmark_names,
            segment_connections=hand_anatomy.segment_connections,
        )
        active[hand_schema.name] = hand_schema
    except Exception:
        pass

    return {definition.name: definition.model_dump() for definition in active.values()}
