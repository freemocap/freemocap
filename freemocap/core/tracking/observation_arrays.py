"""Array access to Tracker stages without reconstructing named Keypoints objects.

Only immutable identity plans are cached. Observation values remain borrowed and
are read afresh, so updating a Tracker buffer never leaves stale cached results.
"""
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from skellytracker.core.data_primitives.observation import Observation, StageObservation
from skellytracker.core.data_primitives.keypoints import Keypoints

from freemocap.core.data_tensors import AxisDefinition

# This is the installed Keypoints schema, not a generic tensor dimension rule.
TRACKER_COMPONENTS = ("x", "y", "z")


@lru_cache(maxsize=256)
def qualified_point_names(stage_name: str, point_names: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(f"{stage_name}.{name}" for name in point_names)


def stage_keypoints(stages: dict[str, StageObservation]) -> Iterator[tuple[tuple[str, ...], Keypoints]]:
    """Follow Tracker's authored stage tree; numerical rows are never iterated."""
    for stage in stages.values():
        if stage.keypoints is not None:
            yield qualified_point_names(stage.name, stage.keypoints.names), stage.keypoints
        yield from stage_keypoints(stage.children)


@lru_cache(maxsize=256)
def _combined_names(stage_names: tuple[tuple[str, ...], ...]) -> tuple[str, ...]:
    names = tuple(name for group in stage_names for name in group)
    return AxisDefinition("entity_identity", names).identifiers


def observation_point_names(observation: Observation) -> tuple[str, ...]:
    return _combined_names(tuple(names for names, _ in stage_keypoints(observation.stages)))


def collected_point_names(observations: Iterable[Observation]) -> tuple[str, ...]:
    """Merge distinct authored layouts once, preserving first occurrence order."""
    layouts = dict.fromkeys(observation_point_names(observation) for observation in observations)
    return tuple(dict.fromkeys(name for names in layouts for name in names))


@lru_cache(maxsize=256)
def point_selection(source_names: tuple[str, ...], target_names: tuple[str, ...],
                    require_all: bool = True) -> tuple[np.ndarray, np.ndarray]:
    """Prepare source/target positions once per distinct declared name pair."""
    AxisDefinition("entity_identity", source_names)
    AxisDefinition("entity_identity", target_names)
    targets = {name: index for index, name in enumerate(target_names)}
    if require_all and set(source_names) - targets.keys():
        raise ValueError("Observation contains an undeclared keypoint missing from the target point axis")
    pairs = tuple((index, targets[name]) for index, name in enumerate(source_names) if name in targets)
    indices = np.asarray(pairs, dtype=np.intp).reshape(-1, 2)
    # Immutable backing prevents a caller from changing a shared selection plan.
    return tuple(np.frombuffer(indices[:, axis].tobytes(), dtype=np.intp) for axis in (0, 1))


@dataclass(frozen=True, slots=True)
class ObservationArrays:
    point_names: tuple[str, ...]
    coordinate_values: np.ndarray
    confidence_scores: np.ndarray

    def __post_init__(self) -> None:
        if self.coordinate_values.shape != (len(self.point_names), len(TRACKER_COMPONENTS)):
            raise ValueError("Tracker coordinates disagree with their declared names/components")
        if self.confidence_scores.shape != (len(self.point_names),):
            raise ValueError("Tracker confidence disagrees with its declared names")

    @property
    def image_coordinates(self) -> np.ndarray:
        return self.coordinate_values[:, :TRACKER_COMPONENTS.index("z")]


def observation_arrays(observation: Observation) -> ObservationArrays:
    parts = tuple(stage_keypoints(observation.stages))
    names = _combined_names(tuple(names for names, _ in parts))
    if not parts:
        return ObservationArrays(names, np.empty((0, len(TRACKER_COMPONENTS))), np.empty(0))
    if len(parts) == 1:
        points = parts[0][1]
        return ObservationArrays(names, points.xyz, points.visibility)
    return ObservationArrays(names, np.concatenate([points.xyz for _, points in parts]),
                             np.concatenate([points.visibility for _, points in parts]))


def aligned_coordinates(points: ObservationArrays, *, point_names: tuple[str, ...],
                        image_only: bool = False, minimum_visibility: float | None = None,
                        require_all: bool = True) -> np.ndarray:
    """Align a whole frame with prepared integer selections and numerical masks."""
    source, target = point_selection(points.point_names, point_names, require_all)
    coordinates = points.image_coordinates if image_only else points.coordinate_values
    result = np.full((len(point_names), coordinates.shape[-1]), np.nan, dtype=np.float64)
    if minimum_visibility is not None:
        confidence = points.confidence_scores[source]
        selected = np.isfinite(confidence) & (confidence >= minimum_visibility)
        source, target = source[selected], target[selected]
    result[target] = coordinates[source]
    return result
