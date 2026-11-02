"""Shared channel-assembly helpers for frame-channel composition.

Turn an aggregator output message into the packed float32 bytes a ChannelBlock
ships. Kept as a leaf (not inside the producers package) so no package-init
import cycle.
"""
from __future__ import annotations

from typing import Any
from functools import lru_cache
from skellytracker.core.io.tracker_profiles import tracker_profile
from collections.abc import Mapping  # noqa: TC003 - runtime type checking
from skellyforge.core.data_tensors.channel_values import ChannelValues

import numpy as np

from skellyforge.core.skeleton.skeleton_definition import SkeletonDefinition  # noqa: TC002

TEMPORAL_STATUS_LABELS = ('unavailable', 'current_input', 'predicted_support', 'retained_value')


def temporal_status_bytes(*, names: tuple[str, ...], status: ChannelValues | None) -> bytes | None:
    if status is None:
        return None
    return np.nan_to_num(status.aligned(names), nan=0).astype(np.uint8).tobytes()


def assemble_channel_bytes(*, names: tuple[str, ...], positions: Mapping,
                           columns: tuple[str, ...], unavailable_components: tuple[str, ...] = ()) -> bytes:
    """Pack declared entity/component axes; unavailable wire components stay NaN."""
    if not set(unavailable_components).issubset(columns):
        raise ValueError("Unavailable components must belong to the wire layout")
    source_columns = tuple(column for column in columns if column not in unavailable_components)
    if isinstance(positions, ChannelValues):
        values = positions.aligned(names)
        if positions.component_names:
            if positions.component_names != source_columns:
                raise ValueError("Numerical components do not match the declared wire columns")
        elif len(source_columns) == 1:
            values = values[:, None]
        else:
            raise ValueError("Scalar values require a single wire component")
    else:
        values = ChannelValues.from_mapping(positions, component_names=source_columns).aligned(names)
    rows = np.full((len(names), len(columns)), np.nan, dtype='<f4')
    selected = tuple(index for index, column in enumerate(columns) if column not in unavailable_components)
    rows[:, selected] = values
    return rows.tobytes(order='C')


# Which camera-node observation, and which of its stages, a detector's 2D points live in.
# A camera node runs several detectors per frame and files each under its own observation,
# so a consumer asking for "the detections" has to say whose.
_OBSERVATION_BY_DETECTOR: dict[str, tuple[str, tuple[str, ...]]] = {
    "rtmpose": ("skeleton_observation", ("body",)),
    "mediapipe": ("skeleton_observation", ("body",)),
    "rtmw_mediapipe_hands": ("skeleton_observation", ("body",)),
    "charuco": ("charuco_observation", ("charuco",)),
}


@lru_cache(maxsize=8)
def detector_crop_paths(detector_type: str) -> tuple[tuple[str, ...], ...]:
    """Tracker declares meaningful crop stages; Core connects them to the wire."""
    if detector_type not in _OBSERVATION_BY_DETECTOR:
        raise KeyError(f"unknown detector type {detector_type!r}")
    return () if detector_type == 'charuco' else tracker_profile(detector_type).crop_stage_paths


def detector_produces_boxes(detector_type: str) -> bool:
    return bool(detector_crop_paths(detector_type))


@lru_cache(maxsize=8)
def detector_stage_names(detector_type: str) -> tuple[str, ...]:
    return tuple('/'.join(path) for path in detector_crop_paths(detector_type))


def camera_2d_detections(
    message: Any,  # duck-typed: the concrete type pulls skellytracker/mediapipe
    camera_id: str,
    *,
    detector_type: str,
    stage_path: tuple[str, ...] | None = None,
) -> ChannelValues:
    """One detector's per-camera 2D detections (name -> (x, y, visibility)).

    `detector_type` is required rather than defaulted because a camera node produces
    several observations per frame and defaulting to one of them is how the charuco
    detections went missing from the overlay for as long as they did.

    Raises:
        KeyError: an unknown detector type. A new detector needs a line above saying where
            it files its points, rather than silently overlaying nothing.
    """
    try:
        observation_attribute, stage_names = (("skeleton_observation", ()) if stage_path is not None
                                              else _OBSERVATION_BY_DETECTOR[detector_type])
    except KeyError as error:
        raise KeyError(
            f"unknown detector type {detector_type!r} - add it to "
            f"`_OBSERVATION_BY_DETECTOR` so its 2D points can be found. Known: "
            f"{sorted(_OBSERVATION_BY_DETECTOR)}"
        ) from error

    components = ('x', 'y', 'visibility')
    cam_output = message.camera_node_outputs.get(camera_id)
    observation = getattr(cam_output, observation_attribute, None) if cam_output is not None else None
    if observation is None:
        return ChannelValues.empty(component_names=components)
    if stage_path is not None:
        stages = observation.stages
        for name in stage_path:
            stage = stages.get(name)
            if stage is None:
                return ChannelValues.empty(component_names=components)
            stages = stage.children
        if not stage_path or stage.keypoints is None:
            return ChannelValues.empty(component_names=components)
        keypoints = stage.keypoints
        values = np.column_stack((keypoints.xyz[:, :2], keypoints.visibility))
        return ChannelValues(tuple(keypoints.names), values,
            np.isfinite(values[:, :2]).all(axis=-1), component_names=components)
    point_channels = []
    for stage_name in stage_names:
        stage = observation.stages.get(stage_name)
        if stage is None or stage.keypoints is None:
            continue
        keypoints = stage.keypoints
        values = np.column_stack((keypoints.xyz[:, :2], keypoints.visibility))
        point_channels.append(ChannelValues(tuple(keypoints.names), values,
            ~np.isnan(values[:, :2]).any(axis=-1), component_names=components))
    if not point_channels:
        return ChannelValues.empty(component_names=components)
    return ChannelValues(tuple(name for channel in point_channels for name in channel.names),
        np.concatenate([channel.data_values for channel in point_channels]),
        np.concatenate([channel.entry_present for channel in point_channels]), component_names=components)


BOX_COMPONENTS = ('x1', 'y1', 'x2', 'y2', 'confidence', 'detector_ran')


def camera_2d_boxes(message: Any, camera_id: str, *, detector_type: str) -> ChannelValues:
    """Pack actual executed crops, including hand crops with no detected keypoints.

    Stage identities come from Tracker. Numerical rows share one dense tensor;
    absent crops retain a declared unavailable row rather than disappearing.
    """
    paths = detector_crop_paths(detector_type)
    names = detector_stage_names(detector_type)
    rows = np.full((len(paths), len(BOX_COMPONENTS)), np.nan, dtype=np.float32)
    attribute = _OBSERVATION_BY_DETECTOR[detector_type][0]
    output = message.camera_node_outputs.get(camera_id)
    observation = getattr(output, attribute, None) if output is not None else None
    if observation is not None:
        for row, path in enumerate(paths):
            stages = observation.stages
            stage = None
            for name in path:
                stage = stages.get(name)
                if stage is None:
                    break
                stages = stage.children
            if stage is None or not stage.bounding_boxes:
                continue
            box = stage.bounding_boxes[0]
            rows[row] = (box.x1, box.y1, box.x2, box.y2, box.confidence, float(stage.detector_ran))
    return ChannelValues(names, rows, ~np.isnan(rows[:, :4]).any(axis=1), component_names=BOX_COMPONENTS)


def origin_landmark_names(skeleton: SkeletonDefinition) -> dict[str, str]:
    """segment name -> origin landmark name (from the standard human model)."""
    return {segment.name: segment.frame_definition.origin_point_name for segment in skeleton.segments.values()}
