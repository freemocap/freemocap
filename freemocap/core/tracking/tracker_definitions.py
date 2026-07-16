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
