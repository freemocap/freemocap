"""Lightweight definitions for tracker keypoint schemas.

Provides RTMPOSE_WHOLEBODY_DEFINITION and MEDIAPIPE_BODY_DEFINITION as simple
named objects with .name, .tracked_points, and .connections fields, loaded from
the new skellytracker core YAML files. These replace imports from the old
skellytracker.trackers.*.names_and_connections modules.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

import skellytracker
from skellytracker.core.detectors.keypoint_detectors._schema_loader import (
    load_connections,
    load_point_names,
)

_CORE_DETECTORS = Path(skellytracker.__file__).parent / "core" / "detectors" / "keypoint_detectors"


class TrackerDefinition(BaseModel):
    """Schema of named keypoints + skeleton connections for a tracker."""

    name: str
    tracked_points: tuple[str, ...]
    connections: tuple[tuple[str, str], ...]


def _load(yaml_path: Path, name: str) -> TrackerDefinition:
    return TrackerDefinition(
        name=name,
        tracked_points=load_point_names(yaml_path),
        connections=load_connections(yaml_path),
    )


RTMPOSE_WHOLEBODY_DEFINITION: TrackerDefinition = _load(
    _CORE_DETECTORS / "rtmpose" / "wholebody" / "rtmpose_wholebody.yaml",
    name="rtmpose_wholebody",
)

MEDIAPIPE_BODY_DEFINITION: TrackerDefinition = _load(
    _CORE_DETECTORS / "mediapipe" / "body" / "mediapipe_body.yaml",
    name="mediapipe_body",
)

_BODY_YAML = _CORE_DETECTORS / "mediapipe" / "body" / "mediapipe_body.yaml"
_HAND_YAML = _CORE_DETECTORS / "mediapipe" / "hands" / "mediapipe_hand.yaml"
_FACE_YAML = _CORE_DETECTORS / "mediapipe" / "face" / "mediapipe_face_contour.yaml"
_MEDIAPIPE_STAGE = "body"


def _build_mediapipe_wholebody() -> TrackerDefinition:
    """Build a composite MediaPipe wholebody definition matching the runtime point names.

    Both the single-camera projection path and the multi-camera triangulation
    path strip the stage prefix that Observation.to_keypoints() adds, so
    keypoints_arrays keys arrive without any "body." prefix:
      - Body: nose, left_shoulder, ...
      - Hands: right_hand_wrist, left_hand_wrist, ...  (hand detector adds
        right_hand_/left_hand_ prefix internally; stage prefix is then stripped)
      - Face: face_0000, face_0007, ...
    """
    body_points = load_point_names(_BODY_YAML)
    body_connections = load_connections(_BODY_YAML)
    hand_points = load_point_names(_HAND_YAML)
    hand_connections = load_connections(_HAND_YAML)
    face_points = load_point_names(_FACE_YAML)
    face_connections = load_connections(_FACE_YAML)

    tracked_points: tuple[str, ...] = (
        tuple(body_points)
        + tuple(f"right_hand_{p}" for p in hand_points)
        + tuple(f"left_hand_{p}" for p in hand_points)
        + tuple(face_points)
    )

    connections: tuple[tuple[str, str], ...] = (
        tuple(body_connections)
        + tuple((f"right_hand_{a}", f"right_hand_{b}") for a, b in hand_connections)
        + tuple((f"left_hand_{a}", f"left_hand_{b}") for a, b in hand_connections)
        + tuple(face_connections)
    )

    return TrackerDefinition(
        name="mediapipe_wholebody",
        tracked_points=tracked_points,
        connections=connections,
    )


MEDIAPIPE_WHOLEBODY_DEFINITION: TrackerDefinition = _build_mediapipe_wholebody()
