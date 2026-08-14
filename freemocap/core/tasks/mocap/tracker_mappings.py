"""Tracker → standard-human mapping YAML paths + tracker keypoint names, keyed by detector type.

Shipped with skellytracker. Keyed by ``CameraNodeConfig.detector_type`` (``rtmpose``
/ ``mediapipe``) so every consumer that must turn raw tracker keypoint names into
standard-human names (the skeleton rigidifier, the center-of-mass loader) picks the
mapping that matches the configured detector's naming convention. Single source of
truth for these dicts — all consumers import from here.
"""
from __future__ import annotations

from pathlib import Path  # noqa: TC003  # module-level var annotations are evaluated at runtime

from skellytracker.core.detectors.keypoint_detectors.mediapipe.body.mediapipe_pose_detector import (
    MediapipePoseKeypointDetector,
    _POINT_NAMES as _MEDIAPIPE_BODY_NAMES,
)
from skellytracker.core.detectors.keypoint_detectors.mediapipe.hands.mediapipe_hand_detector import (
    MediapipeHandKeypointDetector,
    _HAND_POINT_NAMES as _MEDIAPIPE_HAND_NAMES,
)
from skellytracker.core.detectors.keypoint_detectors.rtmpose.body.rtmpose_body_detector import (
    RTMPoseBodyDetector,
    _POINT_NAMES as _RTMPOSE_BODY_NAMES,
)
from skellytracker.core.detectors.keypoint_detectors.rtmpose.hand.rtmpose_hand_detector import (
    RTMPoseHandDetector,
    _POINT_NAMES as _RTMPOSE_HAND_NAMES,
)

_BODY_MAPPING_YAML_BY_DETECTOR: dict[str, Path] = {
    "rtmpose": RTMPoseBodyDetector.standard_human_mapping_path(),
    "mediapipe": MediapipePoseKeypointDetector.standard_human_mapping_path(),
}
_HAND_MAPPING_YAML_BY_DETECTOR: dict[str, Path] = {
    "rtmpose": RTMPoseHandDetector.standard_human_mapping_path(),
    "mediapipe": MediapipeHandKeypointDetector.standard_human_mapping_path(),
}


def body_mapping_yaml_path(detector_type: str) -> Path:
    """The body tracker → standard-human mapping YAML for ``detector_type``."""
    return _BODY_MAPPING_YAML_BY_DETECTOR[detector_type]


def hand_mapping_yaml_path(detector_type: str) -> Path:
    """The hand tracker → standard-human mapping YAML for ``detector_type``."""
    return _HAND_MAPPING_YAML_BY_DETECTOR[detector_type]


def tracker_keypoint_names(detector_type: str) -> tuple[str, ...]:
    """The tracker keypoint names the standard stream's KEYPOINTS_3D carries, sorted.

    These are the names the detectors actually emit — the same constants the
    detectors load from their point-name YAMLs (imported here, aliased) — so the
    schema's KEYPOINTS_3D / OVERLAY_2D names and the per-frame
    ``keypoints_arrays`` keys stay in lockstep. Hand names are side-prefixed
    exactly as the detectors compose them (``left_hand_`` / ``right_hand_``).
    The mapping's ``TrackerMapping.tracker_names`` is NOT the source: its
    anatomical-offset forms may reference standard-human landmark names (e.g.
    ``hips_center`` as an offset origin), which the tracker never emits.
    """
    if detector_type == "rtmpose":
        body_names = _RTMPOSE_BODY_NAMES
        hand_names = _RTMPOSE_HAND_NAMES
    elif detector_type == "mediapipe":
        body_names = _MEDIAPIPE_BODY_NAMES
        hand_names = _MEDIAPIPE_HAND_NAMES
    else:
        raise ValueError(f"unknown detector_type {detector_type!r} (rtmpose | mediapipe)")
    names = set(body_names)
    for side in ("left", "right"):
        names.update(f"{side}_hand_{n}" for n in hand_names)
    return tuple(sorted(names))
