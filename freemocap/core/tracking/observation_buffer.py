"""Numerical access to fresh/saved recording tensors and calibration observations.

Known-length recording pipelines pass a camera series. Calibration's existing
incremental collector can still add individual observations.
"""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray  # noqa: TC002
from skellytracker.core.data_primitives.observation import Observation  # noqa: TC002
from freemocap.core.tracking.observation_series import ObservationFrame, ObservationSeries, ObservationFrames, RecordingObservationSeries
from freemocap.core.tracking.observation_arrays import (
    TRACKER_COMPONENTS, collected_point_names, observation_arrays, point_selection, visible_coordinates,
)


class ObservationBuffer:
    """Align camera recording arrays for triangulation and calibration."""

    def __init__(self, camera_series: ObservationSeries | RecordingObservationSeries | None = None) -> None:
        self.observations: list[Observation | ObservationFrame] = []
        self.camera_series = camera_series

    def add_observation(self, observation: Observation | ObservationFrame) -> None:
        if self.camera_series is not None:
            raise ValueError("Saved observation series cannot accept Tracker objects")
        self.observations.append(observation)

    @property
    def keypoint_names(self) -> tuple[str, ...]:
        """Stage-qualified names encountered anywhere in the recording, in first-seen order."""
        return self.camera_series.point_names if self.camera_series is not None else collected_point_names(self.observations)

    def to_keypoints_array(self, *, names: tuple[str, ...]) -> NDArray[np.float64]:
        """Align each observation to a shared name axis; absent measurements remain NaN."""
        point_selection((), names)
        if self.camera_series is not None:
            if isinstance(self.camera_series, RecordingObservationSeries) and not self.camera_series.delivered.all():
                raise ValueError('Observation frame has not been delivered')
            source, target = point_selection(self.keypoint_names, names)
            coordinates = self.camera_series.tracker_coordinates()
            confidence = self.camera_series.confidence_scores()
            visible_coordinates(coordinates, confidence, in_place=True)
            if names == self.keypoint_names:
                return coordinates
            values = np.full((len(self), len(names), len(TRACKER_COMPONENTS)), np.nan, dtype=np.float64)
            values[:, target] = coordinates[:, source]
            return values
        values = np.full((len(self.observations), len(names), len(TRACKER_COMPONENTS)), np.nan, dtype=np.float64)
        # Source observations arrive as individual objects. Group only their layout
        # metadata, then assemble and mask entire frame/keypoint tensors in NumPy.
        for start in range(0, len(self.observations), 256):
            groups = {}
            for index, observation in enumerate(self.observations[start:start + 256], start):
                points = observation_arrays(observation)
                groups.setdefault(points.point_names, []).append((index, points))
            for source_names, frames in groups.items():
                source, target = point_selection(source_names, names)
                coordinates = np.stack([points.coordinate_values for _, points in frames])
                confidence = np.stack([points.confidence_scores for _, points in frames])
                coordinates = visible_coordinates(coordinates, confidence)
                frame_indices = np.asarray([index for index, _ in frames])
                values[frame_indices[:, None], target] = coordinates[:, source]
        return values

    def to_stage_array(self, stage_name: str, n_points: int | None = None) -> NDArray[np.float64]:
        """Return (frames, n_points, 3) array from a single named stage.

        Undetected points have visibility=0 in the source and NaN xy in the
        returned array. If n_points is given, only the first n_points keypoints
        are returned (useful for charuco, which prefixes charuco corners before
        aruco marker corners).

        Args:
            stage_name: Key in Observation.stages (e.g., "charuco", "body").
            n_points: If set, clamp output to the first n_points keypoints.
        """
        if self.camera_series is not None:
            if isinstance(self.camera_series, RecordingObservationSeries):
                self.camera_series.require_stage(stage_name)
            names = self.stage_point_names(stage_name)
            if n_points is not None and (n_points < 0 or n_points > len(names)):
                raise ValueError("Stage selection exceeds its declared keypoint names")
            names = names if n_points is None else names[:n_points]
            indices = list(self.camera_series.stage_indices[stage_name][:len(names)])
            coordinates = self.camera_series.tracker_coordinates(point_indices=indices)
            confidence = self.camera_series.confidence_scores()[:, indices]
            return visible_coordinates(coordinates, confidence, in_place=True)
        arrays: list[NDArray[np.float64]] = []
        for obs in self.observations:
            stage = obs.stages.get(stage_name)
            if stage is None or stage.keypoints is None:
                raise ValueError(
                    f"ObservationBuffer.to_stage_array: stage {stage_name!r} missing "
                    f"from observation at frame {obs.frame_number}"
                )
            kpts = stage.keypoints
            if n_points is not None and (n_points < 0 or n_points > len(kpts.names)):
                raise ValueError("Stage selection exceeds its declared keypoint names")
            selected_names = kpts.names if n_points is None else kpts.names[:n_points]
            if arrays and selected_names != first_names:
                raise ValueError("Stage keypoint order changed within the recording")
            first_names = selected_names
            xyz = kpts.xyz if n_points is None else kpts.xyz[:n_points]
            vis = kpts.visibility if n_points is None else kpts.visibility[:n_points]
            xyz_out = visible_coordinates(xyz, vis).astype(np.float64, copy=False)
            arrays.append(xyz_out)
        return np.stack(arrays)

    @property
    def frame_numbers(self) -> tuple[int, ...]:
        return self.camera_series.frame_numbers if self.camera_series is not None else tuple(
            observation.frame_number for observation in self.observations)

    def stage_point_names(self, stage_name: str) -> tuple[str, ...]:
        if self.camera_series is not None:
            names = tuple(name.partition('.')[2] for name in self.keypoint_names if name.partition('.')[0] == stage_name)
            if not names:
                raise ValueError(f"Missing observation stage {stage_name!r}")
            return names
        return self.observations[0].stages[stage_name].keypoints.names

    def clear(self) -> None:
        self.observations.clear()
        self.camera_series = None

    def __len__(self) -> int:
        return len(self.camera_series) if self.camera_series is not None else len(self.observations)


def recording_observation_buffers(frames, cameras: tuple[str, ...]) -> dict[str, ObservationBuffer]:
    if isinstance(frames, ObservationFrames):
        if set(cameras) != set(frames.camera_series):
            raise ValueError('Observation sources differ from requested cameras')
        return {camera: ObservationBuffer(frames.camera_series[camera]) for camera in cameras}
    buffers = {camera: ObservationBuffer() for camera in cameras}
    for frame in frames:
        for camera in cameras:
            buffers[camera].add_observation(frame[camera])
    return buffers
