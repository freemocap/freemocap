"""
Tracker-schema handshake message.

Sent once when a WebSocket client connects, and rebroadcast if the pipeline's
tracker configuration changes. Carries the active tracker schemas (RTMPose +
MediaPipe wholebody definitions, from the tracker side) plus the standard-human
schema (keypoints + segment connections for 3D skeleton rendering), built from
the composed model. The standard human is local skellyforge code that is always
present, so there are no silent fallbacks here.
"""

from typing import Any

import msgspec

from freemocap.api.websocket.websocket_message_types import WebsocketMessageType
from freemocap.core.tracking.tracker_definitions import TrackerDefinition, RTMPOSE_WHOLEBODY_DEFINITION, MEDIAPIPE_WHOLEBODY_DEFINITION


class TrackerSchemasMessage(msgspec.Struct):
    """Dict of ``tracker_id -> TrackerDefinition.model_dump()``.

    Values are pre-serialized to plain dicts because msgspec.Struct cannot
    carry arbitrary Pydantic models directly. The frontend treats the inner
    dicts as the canonical TS ``TrackerDefinition`` shape.
    """
    schemas: dict[str, dict[str, Any]]
    message_type: WebsocketMessageType = WebsocketMessageType.TRACKER_SCHEMAS


def collect_active_tracker_schemas() -> dict[str, dict[str, Any]]:
    """Collect every active tracker schema the freemocap pipeline can emit.

    The RTMPose/MediaPipe wholebody definitions carry the tracker-side
    keypoint schemas (2D overlays + keypoint classification); the
    ``standard_human`` definition carries the standard human's keypoints and
    segment connections (3D skeleton rendering), built from the composed
    model — the old ``canonical_body``/``canonical_hand`` AnatomicalStructure
    schemas are retired with it.
    """
    from skellyforge.skellymodels.standard_human.standard_human_model import (
        compose_standard_human,
    )

    human = compose_standard_human()
    connections = tuple(
        (segment.parent, segment.name)
        for segment in human.segments
        if segment.parent is not None
    )
    standard_human_schema = TrackerDefinition(
        name="standard_human",
        tracked_points=tuple(sorted(human.required_keypoints())),
        connections=connections,
    )

    active: dict[str, TrackerDefinition] = {
        RTMPOSE_WHOLEBODY_DEFINITION.name: RTMPOSE_WHOLEBODY_DEFINITION,
        MEDIAPIPE_WHOLEBODY_DEFINITION.name: MEDIAPIPE_WHOLEBODY_DEFINITION,
        standard_human_schema.name: standard_human_schema,
    }
    return {definition.name: definition.model_dump() for definition in active.values()}
