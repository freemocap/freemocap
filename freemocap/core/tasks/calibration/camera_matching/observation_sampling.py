"""Bounded matching samples built from explicitly associated observation points."""

from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from skellytracker.core.data_primitives.observation import Observation
from freemocap.core.tracking.observation_arrays import (
    aligned_coordinates, collected_point_names, observation_arrays, point_selection,
)


def select_matching_point_names(*, frames: list[dict[str, Observation]], minimum_visibility: float) -> tuple[str, ...]:
    """Prefer confidently observed cross-view points within the matching budget."""
    names = collected_point_names(observation for frame in frames for observation in frame.values())
    scores = np.zeros(len(names), dtype=np.float64)
    eligible = np.zeros(len(names), dtype=bool)
    for observations in frames:
        if len(observations) < 2:
            continue
        confidence = np.full((len(observations), len(names)), np.inf)
        for camera_index, observation in enumerate(observations.values()):
            points = observation_arrays(observation)
            source, target = point_selection(points.point_names, names)
            valid = (np.isfinite(points.confidence_scores) & (points.confidence_scores >= minimum_visibility)
                     & np.isfinite(points.image_coordinates).all(axis=-1))
            confidence[camera_index, target[valid[source]]] = points.confidence_scores[source[valid[source]]]
        shared = np.isfinite(confidence).sum(axis=0) >= 2
        eligible |= shared
        scores[shared] += confidence[:, shared].min(axis=0)
    selected = np.flatnonzero(eligible)
    # The existing matching budget ranks evidence; it does not reorder tensor axes.
    order = np.lexsort((np.asarray(names)[selected], -scores[selected]))
    return tuple(names[index] for index in selected[order[:64]])


@dataclass(frozen=True, slots=True)
class MatchingSampleLayout:
    """Point names must identify the same instance and landmark across sources."""

    source_ids: tuple[str, ...]
    point_names: tuple[str, ...]
    image_sizes: tuple[tuple[int, int], ...]
    minimum_visibility: float

    def __post_init__(self) -> None:
        if not 0.0 < self.minimum_visibility <= 1.0:
            raise ValueError("Matching visibility threshold must be in (0, 1]")
        if len(self.source_ids) < 2 or len(set(self.source_ids)) != len(self.source_ids):
            raise ValueError("Matching samples require distinct sources")
        if not self.point_names or len(set(self.point_names)) != len(self.point_names):
            raise ValueError("Matching sample points must be nonempty and unique")
        if len(self.image_sizes) != len(self.source_ids) or any(min(size) <= 0 for size in self.image_sizes):
            raise ValueError("Each matching source requires positive (width, height)")

    def extract(self, *, observations: Mapping[str, Observation]) -> NDArray[np.float64]:
        if set(observations) != set(self.source_ids):
            raise ValueError("Matching observation sources differ from sample layout")
        if len({observation.frame_number for observation in observations.values()}) != 1:
            raise ValueError("Matching requires observations from one synchronized frame")
        pixels = np.full((len(self.source_ids), len(self.point_names), 2), np.nan, dtype=np.float64)
        for source_index, source in enumerate(self.source_ids):
            observation = observations[source]
            if observation.image_size[::-1] != self.image_sizes[source_index]:
                raise ValueError(f"Matching image dimensions changed for source {source}")
            pixels[source_index] = aligned_coordinates(observation_arrays(observation),
                point_names=self.point_names, image_only=True, minimum_visibility=self.minimum_visibility,
                require_all=False)
            pixels[source_index, ~np.isfinite(pixels[source_index]).all(axis=-1)] = np.nan
        return pixels


class MatchingSampleWindow:
    """Rolling numeric samples, independent of image buffers and worker execution.

    Detector thresholds and cross-view instance association are caller responsibilities.
    The timestamp is elapsed monotonic time, not a camera's capture clock.
    """

    def __init__(self, *, layout: MatchingSampleLayout, capacity: int, interval_seconds: float) -> None:
        if capacity < 2 or not np.isfinite(interval_seconds) or interval_seconds < 0.0:
            raise ValueError("Matching window requires capacity >=2 and a finite nonnegative interval")
        self.layout = layout
        self._samples: deque[NDArray[np.float64]] = deque(maxlen=capacity)
        self._interval_seconds = interval_seconds
        self._last_sample_time = float("-inf")
        self._last_seen_time = float("-inf")

    def append(self, *, observations: Mapping[str, Observation], elapsed_seconds: float) -> bool:
        if not np.isfinite(elapsed_seconds) or elapsed_seconds < self._last_seen_time:
            raise ValueError("Matching sample time must be finite and monotonic")
        self._last_seen_time = elapsed_seconds
        if elapsed_seconds - self._last_sample_time < self._interval_seconds:
            return False
        self._samples.append(self.layout.extract(observations=observations))
        self._last_sample_time = elapsed_seconds
        return True

    def snapshot(self) -> NDArray[np.float64]:
        if not self._samples:
            return np.empty((len(self.layout.source_ids), 0, len(self.layout.point_names), 2), dtype=np.float64)
        return np.stack(tuple(self._samples), axis=1)

    def clear(self) -> None:
        self._samples.clear()


def sample_recorded_observations(
    *, layout: MatchingSampleLayout, frames: list[dict[str, Observation]], maximum_frames: int,
) -> NDArray[np.float64]:
    """Evenly sample recorded observations without decoding images or rerunning inference."""
    if maximum_frames < 2:
        raise ValueError("Recorded matching requires a sample budget of at least two frames")
    window = MatchingSampleWindow(layout=layout, capacity=maximum_frames, interval_seconds=0.0)
    indices = np.linspace(0, len(frames) - 1, min(maximum_frames, len(frames)), dtype=int)
    for index in indices:
        window.append(observations=frames[index], elapsed_seconds=float(index))
    return window.snapshot()
