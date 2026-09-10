"""Bounded matching samples built from explicitly associated observation points."""

from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from skellytracker.core.data_primitives.observation import Observation


def select_matching_point_names(*, frames: list[dict[str, Observation]], minimum_visibility: float) -> tuple[str, ...]:
    """Prefer confidently observed cross-view points within the matching budget."""
    scores: dict[str, float] = {}
    for observations in frames:
        shared: dict[str, list[float]] = {}
        for observation in observations.values():
            points = observation.to_keypoints()
            for index, name in enumerate(points.names):
                visibility = float(points.visibility[index])
                if np.isfinite(visibility) and visibility >= minimum_visibility and np.isfinite(points.xy[index]).all():
                    shared.setdefault(name, []).append(visibility)
        for name, visibility in shared.items():
            if len(visibility) >= 2:
                scores[name] = scores.get(name, 0.0) + min(visibility)
    return tuple(sorted(scores, key=lambda name: (-scores[name], name)))[:64]


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
            points = observation.to_keypoints()
            if len(set(points.names)) != len(points.names):
                raise ValueError("Matching observation has duplicate qualified point names")
            indices = {name: index for index, name in enumerate(points.names)}
            for target, name in enumerate(self.point_names):
                index = indices.get(name)
                if index is not None and np.isfinite(points.visibility[index]) and points.visibility[index] >= self.minimum_visibility:
                    if np.isfinite(points.xy[index]).all():
                        pixels[source_index, target] = points.xy[index]
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
