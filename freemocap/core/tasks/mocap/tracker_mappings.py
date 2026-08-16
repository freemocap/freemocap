"""Tracker → standard-human mapping YAML paths + tracker keypoint names, keyed by detector type.

Shipped with skellytracker. Keyed by ``CameraNodeConfig.detector_type`` (``rtmpose``
/ ``mediapipe``) so every consumer that must turn raw tracker keypoint names into
standard-human names (the skeleton rigidifier, the center-of-mass loader) picks the
mapping that matches the configured detector's naming convention. Single source of
truth for these dicts — all consumers import from here.

The keypoint names are the tracker's FULL output set: every name the configured
detector can emit appears in the schema's KEYPOINTS_3D / OVERLAY_2D groups. The
tracker never filters its own keypoints — foot / hand / face points ride the
stream as pure measurements even where no standard-human landmark consumes them.
"""
from __future__ import annotations

from pathlib import Path  # noqa: TC003  # module-level var annotations are evaluated at runtime

from skellytracker.core.detectors.keypoint_detectors.mediapipe.body.mediapipe_pose_detector import (
    MediapipePoseKeypointDetector,
    _POINT_NAMES as _MEDIAPIPE_BODY_NAMES,
)
from skellytracker.core.detectors.keypoint_detectors.mediapipe.face.mediapipe_face_detector import (
    _POINT_NAMES as _MEDIAPIPE_FACE_NAMES,
)
from skellytracker.core.detectors.keypoint_detectors.mediapipe.hands.mediapipe_hand_detector import (
    MediapipeHandKeypointDetector,
    _HAND_POINT_NAMES as _MEDIAPIPE_HAND_NAMES,
)
from skellytracker.core.detectors.keypoint_detectors.rtmpose.body.rtmpose_body_detector import (
    RTMPoseBodyDetector,
)
from skellytracker.core.detectors.keypoint_detectors.rtmpose.hand.rtmpose_hand_detector import (
    RTMPoseHandDetector,
)
from skellytracker.core.detectors.keypoint_detectors.rtmpose.wholebody.rtmpose_wholebody_detector import (
    _POINT_NAMES as _RTMPOSE_WHOLEBODY_NAMES,
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
    """The tracker's FULL keypoint-name set the frame carries, sorted.

    These are the names the configured detector actually emits — imported from
    the detector's own point-name constants — so the frame's KEYPOINTS_3D /
    OVERLAY_2D names and the per-frame ``keypoints_arrays`` keys stay in
    lockstep. Every keypoint the model can produce appears here, including face
    / foot / hand points that no standard-human landmark consumes; the tracker
    never filters its own output. Hand names are side-prefixed exactly as the
    detectors compose them (``left_hand_`` / ``right_hand_``). The mapping's
    ``TrackerMapping.tracker_names`` is NOT the source: its anatomical-offset
    forms may reference standard-human landmark names (e.g. ``hips_center`` as
    an offset origin), which the tracker never emits.
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
