"""Shared channel-assembly helpers for frame-channel composition.

Turn an aggregator output message into the packed float32 bytes a ChannelBlock
ships. Kept as a leaf (not inside the producers package) so no package-init
import cycle.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from skellyforge.core.skeleton.skeleton_definition import SkeletonDefinition  # noqa: TC002


def assemble_channel_bytes(
    *,
    names: tuple[str, ...],
    positions: dict[str, np.ndarray | None],
    n_cols: int,
) -> bytes:
    """Pack (len(names), n_cols) float32 little-endian bytes, NaN-filling
    missing names (a missing point is a NaN row, never a dropped row)."""
    rows = np.full((len(names), n_cols), np.nan, dtype=np.float32)
    for i, name in enumerate(names):
        pos = positions.get(name)
        if pos is None:
            continue
        arr = np.asarray(pos, dtype=np.float32)
        if arr.size == 0:
            continue
        k = min(n_cols, int(arr.size))
        rows[i, :k] = arr[:k]
    return rows.tobytes(order="C")


# Which camera-node observation, and which of its stages, a detector's 2D points live in.
# A camera node runs several detectors per frame and files each under its own observation,
# so a consumer asking for "the detections" has to say whose.
_OBSERVATION_BY_DETECTOR: dict[str, tuple[str, tuple[str, ...]]] = {
    "rtmpose": ("skeleton_observation", ("body",)),
    "mediapipe": ("skeleton_observation", ("body",)),
    "charuco": ("charuco_observation", ("charuco",)),
}


# Which detectors actually run an object detector, and therefore produce a bounding box
# that MEANS something. A stage with no object detector gets `BoundingBox.full_image`
# from DetectionStage — a rectangle around the whole frame, which says nothing about
# where the subject is. Drawing or recording that is worse than showing nothing, and is
# why a MediaPipe posthoc run looked like it had a box covering the entire screen.
_DETECTORS_WITH_OBJECT_DETECTOR: frozenset[str] = frozenset({"rtmpose"})


def detector_produces_boxes(detector_type: str) -> bool:
    """Whether this detector's boxes are a real measurement rather than the full frame."""
    if detector_type not in _OBSERVATION_BY_DETECTOR:
        raise KeyError(
            f"unknown detector type {detector_type!r} - add it to "
            f"`_OBSERVATION_BY_DETECTOR`. Known: {sorted(_OBSERVATION_BY_DETECTOR)}"
        )
    return detector_type in _DETECTORS_WITH_OBJECT_DETECTOR


def detector_stage_names(detector_type: str) -> tuple[str, ...]:
    """The stages a detector files its output under, in wire order.

    This is the declared row set for that detector's per-stage channels, so a stage
    that detected nothing this frame is still a NaN row rather than a missing one.

    Raises:
        KeyError: an unknown detector type — same contract as `camera_2d_detections`.
    """
    try:
        return _OBSERVATION_BY_DETECTOR[detector_type][1]
    except KeyError as error:
        raise KeyError(
            f"unknown detector type {detector_type!r} - add it to "
            f"`_OBSERVATION_BY_DETECTOR`. Known: {sorted(_OBSERVATION_BY_DETECTOR)}"
        ) from error


def camera_2d_detections(
    message: Any,  # duck-typed: the concrete type pulls skellytracker/mediapipe
    camera_id: str,
    *,
    detector_type: str,
) -> dict[str, np.ndarray]:
    """One detector's per-camera 2D detections (name -> (x, y, visibility)).

    `detector_type` is required rather than defaulted because a camera node produces
    several observations per frame and defaulting to one of them is how the charuco
    detections went missing from the overlay for as long as they did.

    Raises:
        KeyError: an unknown detector type. A new detector needs a line above saying where
            it files its points, rather than silently overlaying nothing.
    """
    try:
        observation_attribute, stage_names = _OBSERVATION_BY_DETECTOR[detector_type]
    except KeyError as error:
        raise KeyError(
            f"unknown detector type {detector_type!r} - add it to "
            f"`_OBSERVATION_BY_DETECTOR` so its 2D points can be found. Known: "
            f"{sorted(_OBSERVATION_BY_DETECTOR)}"
        ) from error

    cam_output = message.camera_node_outputs.get(camera_id)
    if cam_output is None:
        return {}
    observation = getattr(cam_output, observation_attribute, None)
    if observation is None:
        return {}

    detections: dict[str, np.ndarray] = {}
    for stage_name in stage_names:
        stage = observation.stages.get(stage_name)
        if stage is None or stage.keypoints is None:
            continue
        keypoints = stage.keypoints
        for index, name in enumerate(keypoints.names):
            x, y, _z = keypoints.xyz[index]
            if np.isnan(x) or np.isnan(y):
                continue
            detections[name] = np.array(
                [x, y, keypoints.visibility[index]], dtype=np.float32
            )
    return detections


def camera_2d_boxes(
    message: Any,  # duck-typed: the concrete type pulls skellytracker/mediapipe
    camera_id: str,
    *,
    detector_type: str,
) -> dict[str, np.ndarray]:
    """One detector's per-camera bounding boxes (stage name -> box row).

    Each row is (x1, y1, x2, y2, confidence, detector_ran). `detector_ran` is the
    stage's own flag for whether the object detector produced this box THIS frame or
    it was carried forward from the tracked keypoints — the distinction the overlay
    colours by, and the one that makes an over-eager redetect visible on sight.

    A stage is keyed by its own name rather than by index, so a tracker running several
    stages (body plus, later, face/hands children) files each box under a stable label.

    Raises:
        KeyError: an unknown detector type — same contract as `camera_2d_detections`.
    """
    try:
        observation_attribute, stage_names = _OBSERVATION_BY_DETECTOR[detector_type]
    except KeyError as error:
        raise KeyError(
            f"unknown detector type {detector_type!r} - add it to "
            f"`_OBSERVATION_BY_DETECTOR` so its boxes can be found. Known: "
            f"{sorted(_OBSERVATION_BY_DETECTOR)}"
        ) from error
    if detector_type not in _DETECTORS_WITH_OBJECT_DETECTOR:
        return {}

    cam_output = message.camera_node_outputs.get(camera_id)
    if cam_output is None:
        return {}
    observation = getattr(cam_output, observation_attribute, None)
    if observation is None:
        return {}

    boxes: dict[str, np.ndarray] = {}
    for stage_name in stage_names:
        stage = observation.stages.get(stage_name)
        if stage is None or not stage.bounding_boxes:
            continue
        # One box per stage — freemocap runs no multi-person tracker, so a second
        # entry would mean the stage contract changed rather than that two people
        # are in view. Take the first and leave widening to a real multi-person path.
        box = stage.bounding_boxes[0]
        boxes[stage_name] = np.array(
            [box.x1, box.y1, box.x2, box.y2, box.confidence, float(stage.detector_ran)],
            dtype=np.float32,
        )
    return boxes


def origin_landmark_names(skeleton: SkeletonDefinition) -> dict[str, str]:
    """segment name -> origin landmark name (from the standard human model)."""
    return {segment.name: segment.frame_definition.origin_point_name for segment in skeleton.segments.values()}
