"""Tracker → standard-human mapping YAML paths, keyed by detector type.

Shipped with skellytracker. Keyed by ``CameraNodeConfig.detector_type`` (``rtmpose``
/ ``mediapipe``) so every consumer that must turn raw tracker keypoint names into
standard-human names (the skeleton rigidifier, the center-of-mass loader) picks the
mapping that matches the configured detector's naming convention. Single source of
truth for these two dicts — both consumers import from here.
"""
from __future__ import annotations

from pathlib import Path  # noqa: TC003  # module-level var annotations are evaluated at runtime

from skellytracker.core.detectors.keypoint_detectors.mediapipe.body.mediapipe_pose_detector import (
    MediapipePoseKeypointDetector,
)
from skellytracker.core.detectors.keypoint_detectors.mediapipe.hands.mediapipe_hand_detector import (
    MediapipeHandKeypointDetector,
)
from skellytracker.core.detectors.keypoint_detectors.rtmpose.body.rtmpose_body_detector import (
    RTMPoseBodyDetector,
)
from skellytracker.core.detectors.keypoint_detectors.rtmpose.hand.rtmpose_hand_detector import (
    RTMPoseHandDetector,
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
