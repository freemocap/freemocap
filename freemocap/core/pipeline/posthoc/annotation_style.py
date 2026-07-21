"""Builds a posthoc annotation StageAnnotationSchema that matches the realtime
browser overlay's region-based coloring (see freemocap-ui's
skeleton-overlay-renderer.ts: classifySide/classifyHand/classifyFace/styleFor).
"""
from __future__ import annotations

from skellytracker.core.annotation.keypoint_annotator import (
    ConnectionGroupSchema,
    StageAnnotationSchema,
)

# BGR (cv2 convention) equivalents of the realtime renderer's hex colors.
_CENTER_COLOR = (0, 170, 0)       # #00AA00
_RIGHT_COLOR = (68, 68, 255)      # #FF4444
_LEFT_COLOR = (255, 136, 68)      # #4488FF
_RIGHT_HAND_COLOR = (0, 100, 255)  # #FF6400
_LEFT_HAND_COLOR = (255, 170, 0)  # #00AAFF
_FACE_COLOR = (0, 215, 255)       # #FFD700

_BOX_COLOR_DETECTED = (0, 255, 0)   # #00FF00
_BOX_COLOR_REUSED = (0, 140, 255)   # #FF8C00


def _classify_hand(name: str) -> str | None:
    lc = name.lower()
    if lc.startswith("left_hand"):
        return "left_hand"
    if lc.startswith("right_hand"):
        return "right_hand"
    return None


def _classify_face(name: str) -> bool:
    lc = name.lower()
    return lc.startswith("face")


def _classify_side(name: str) -> str:
    lc = name.lower()
    if "left" in lc:
        return "left"
    if "right" in lc:
        return "right"
    return "center"


def _is_center(name: str) -> bool:
    return (
        not _classify_face(name)
        and _classify_hand(name) is None
        and _classify_side(name) == "center"
    )


def _color_for(name: str) -> tuple[int, int, int]:
    if _classify_face(name):
        return _FACE_COLOR
    hand = _classify_hand(name)
    if hand == "left_hand":
        return _LEFT_HAND_COLOR
    if hand == "right_hand":
        return _RIGHT_HAND_COLOR
    side = _classify_side(name)
    if side == "left":
        return _LEFT_COLOR
    if side == "right":
        return _RIGHT_COLOR
    return _CENTER_COLOR


def _thickness_for(name: str) -> int:
    # 1px face lines match the realtime canvas overlay but don't survive H.264
    # compression in the saved video (thin diagonal strokes get smoothed away
    # while the solid keypoint dots don't), so use 2px here instead.
    return 2


def build_skeleton_stage_schema(
    connections: tuple[tuple[str, str], ...],
    tracked_points: tuple[str, ...],
) -> StageAnnotationSchema:
    """Build a StageAnnotationSchema whose connection_groups reproduce the
    realtime overlay's per-region coloring for the given connection list.

    Point color and line color are computed independently, matching the
    realtime renderer: each point is colored by its own name (`styleFor`),
    while each line takes its non-center endpoint's color. `KeypointAnnotator`
    only exposes per-point color via a connection group's shared
    `keypoint_color` (applied to both of that connection's endpoints), so line
    groups leave `keypoint_color` unset and a separate set of single-point
    "self-connection" groups carries the actual per-point colors.
    """
    line_buckets: dict[tuple[int, int, int], list[tuple[str, str]]] = {}
    for name_a, name_b in connections:
        color = _color_for(name_b) if _is_center(name_a) else _color_for(name_a)
        line_buckets.setdefault(color, []).append((name_a, name_b))

    point_buckets: dict[tuple[int, int, int], list[str]] = {}
    for name in tracked_points:
        point_buckets.setdefault(_color_for(name), []).append(name)

    connection_groups = tuple(
        ConnectionGroupSchema(
            connections=tuple(group_connections),
            connection_color=color,
            connection_thickness=_thickness_for(group_connections[0][0]),
        )
        for color, group_connections in line_buckets.items()
    ) + tuple(
        ConnectionGroupSchema(
            connections=tuple((name, name) for name in names),
            connection_color=color,
            connection_thickness=1,
            keypoint_color=color,
        )
        for color, names in point_buckets.items()
    )

    return StageAnnotationSchema(
        connections=connections,
        connection_groups=connection_groups,
        draw_boxes=True,
        box_color_detected=_BOX_COLOR_DETECTED,
        box_color_reused=_BOX_COLOR_REUSED,
    )
