"""Tracker to standard-human mapping YAML paths + tracker keypoint names, keyed by detector type.

Shipped with skellytracker. Keyed by CameraNodeConfig.detector_type (rtmpose
/ mediapipe) so every consumer that must turn raw tracker keypoint names into
standard-human names (the skeleton rigidifier, the center-of-mass loader) picks the
mapping that matches the configured detector naming convention. Single source of
truth for these dicts — all consumers import from here.

The keypoint names are the tracker FULL output set: every name the configured
detector can emit appears in the schema KEYPOINTS_3D / OVERLAY_2D groups. The
tracker never filters its own keypoints — foot / hand / face points ride the
stream as pure measurements even where no standard-human landmark consumes them.

IMPORT-LIGHT BY DESIGN: this module is imported by the realtime aggregator (and
the center-of-mass loader), which run in their own process and must NOT drag the
mediapipe / onnxruntime trees in at startup. It therefore reads the tracker
metadata (point-name tuples + mapping paths) straight from skellytracker
import-light mapping_paths + _schema_loader modules — never from the detector
classes, whose module imports would pull in mediapipe / onnxruntime.
"""
from __future__ import annotations

from pathlib import Path  # noqa: TC003  # module-level annotations are evaluated lazily

from skellytracker.core.detectors.keypoint_detectors._schema_loader import (
    load_point_names,
)
from skellytracker.core.io.mapping_paths import (
    MEDIAPIPE_BODY_MAPPING,
    MEDIAPIPE_HAND_MAPPING,
    RTMPOSE_BODY_MAPPING,
    RTMPOSE_HAND_MAPPING,
)
from skellytracker.core.io.tracker_mapping import TrackerMapping
from skellytracker.core.io.composite_tracker_mapping import CompositeTrackerMapping

# The keypoint-detector schema YAMLs (the tracker emitted point names) live
# under the same keypoint_detectors/ tree as the mapping YAMLs. Derive that tree
# root from a mapping-path constant so the layout stays single-sourced.
_KEYPOINT_DETECTORS_DIR = RTMPOSE_BODY_MAPPING.parent.parent.parent

_MEDIAPIPE_BODY_NAMES: tuple[str, ...] = load_point_names(
    _KEYPOINT_DETECTORS_DIR / "mediapipe" / "body" / "mediapipe_body.yaml"
)
_MEDIAPIPE_FACE_NAMES: tuple[str, ...] = load_point_names(
    _KEYPOINT_DETECTORS_DIR / "mediapipe" / "face" / "mediapipe_face_contour.yaml"
)
_MEDIAPIPE_HAND_NAMES: tuple[str, ...] = load_point_names(
    _KEYPOINT_DETECTORS_DIR / "mediapipe" / "hands" / "mediapipe_hand.yaml"
)
_RTMPOSE_WHOLEBODY_NAMES: tuple[str, ...] = load_point_names(
    _KEYPOINT_DETECTORS_DIR / "rtmpose" / "wholebody" / "rtmpose_wholebody.yaml"
)

_BODY_MAPPING_YAML_BY_DETECTOR: dict[str, Path] = {
    "rtmpose": RTMPOSE_BODY_MAPPING,
    "mediapipe": MEDIAPIPE_BODY_MAPPING,
}
_HAND_MAPPING_YAML_BY_DETECTOR: dict[str, Path] = {
    "rtmpose": RTMPOSE_HAND_MAPPING,
    "mediapipe": MEDIAPIPE_HAND_MAPPING,
}


def body_mapping_yaml_path(detector_type: str) -> Path:
    """The body tracker to standard-human mapping YAML for detector_type."""
    return _BODY_MAPPING_YAML_BY_DETECTOR[detector_type]


def hand_mapping_yaml_path(detector_type: str) -> Path:
    """The hand tracker to standard-human mapping YAML for detector_type."""
    return _HAND_MAPPING_YAML_BY_DETECTOR[detector_type]


def tracker_keypoint_names(detector_type: str) -> tuple[str, ...]:
    """The tracker FULL keypoint-name set the frame carries, sorted.

    These are the names the configured detector actually emits — read from the
    detector own schema YAML — so the frame KEYPOINTS_3D / OVERLAY_2D names and
    the per-frame keypoints_arrays keys stay in lockstep. Every keypoint the
    model can produce appears here, including face / foot / hand points that no
    standard-human landmark consumes; the tracker never filters its own output.
    Hand names are side-prefixed exactly as the detectors compose them
    (left_hand_ / right_hand_). The mapping TrackerMapping.tracker_names is NOT
    the source: its anatomical-offset forms may reference standard-human
    landmark names (e.g. hips_center as an offset origin), which the tracker
    never emits.
    """
    if detector_type == "rtmpose":
        # RTMPose wholebody — one detector, all 133 keypoints (body + feet +
        # hands + face), side-prefixed by the detector itself.
        return tuple(sorted(_RTMPOSE_WHOLEBODY_NAMES))
    elif detector_type == "mediapipe":
        # MediaPipe pose + hands + face.
        names = set(_MEDIAPIPE_BODY_NAMES)
        names.update(_MEDIAPIPE_FACE_NAMES)
        for side in ("left", "right"):
            names.update(f"{side}_hand_{n}" for n in _MEDIAPIPE_HAND_NAMES)
        return tuple(sorted(names))
    else:
        raise ValueError(f"unknown detector_type {detector_type!r} (rtmpose | mediapipe)")


def load_standard_human_mapping(detector_type: str) -> CompositeTrackerMapping:
    """Load the merged body + hand tracker->standard-human mapping for a detector.

    Lives here (freemocap) because it needs skellytracker, which skellyforge never imports.
    """
    return CompositeTrackerMapping(mappings=(
        TrackerMapping.from_yaml(body_mapping_yaml_path(detector_type)),
        TrackerMapping.from_yaml(hand_mapping_yaml_path(detector_type)),
    ))
