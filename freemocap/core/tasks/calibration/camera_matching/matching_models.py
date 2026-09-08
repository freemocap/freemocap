"""Typed inputs and diagnostics for camera assignment fitness."""

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field

from freemocap.core.tasks.calibration.shared.camera_model import CameraModel


class MatchingFailurePolicy(StrEnum):
    CONTINUE = "continue"
    STOP = "stop"


class CameraMatchingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    automatically_match: bool = True
    failure_policy: MatchingFailurePolicy = MatchingFailurePolicy.CONTINUE
    minimum_frames: int = Field(default=6, ge=2)
    minimum_points_per_frame: int = Field(default=6, ge=2)
    minimum_valid_fraction: float = Field(default=0.9, gt=0.0, le=1.0)
    minimum_ray_angle_degrees: float = Field(default=1.0, gt=0.0, lt=90.0)
    maximum_median_error: float = Field(default=2.0, gt=0.0)
    maximum_p90_error: float = Field(default=5.0, gt=0.0)
    maximum_search_nodes: int = Field(default=250_000, ge=1)
    minimum_score_gap: float = Field(default=0.05, gt=0.0, le=1.0)


class GeometryFitnessStatus(StrEnum):
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True, slots=True)
class GeometryFitnessRequest:
    """Qualified, instance-associated pixels ordered to match existing camera models.

    Pixels have shape (cameras, frames, points, xy), in calibration image coordinates.
    NaN pairs represent absent or rejected detections. Input adaptation must establish
    cross-view point identity and detector validity before constructing this request.
    """

    cameras: tuple[CameraModel, ...]
    pixels: NDArray[np.float64]
    config: CameraMatchingConfig

    def __post_init__(self) -> None:
        if len(self.cameras) < 2 or len({camera.id for camera in self.cameras}) != len(self.cameras):
            raise ValueError("Fitness requires at least two distinct calibrated cameras")
        if self.pixels.ndim != 4 or self.pixels.shape[0] != len(self.cameras) or self.pixels.shape[-1] != 2:
            raise ValueError("Fitness pixels must have shape (cameras, frames, points, 2)")
        if np.isinf(self.pixels).any():
            raise ValueError("Fitness pixels must be finite or absent (NaN)")
        if np.any(np.isnan(self.pixels).any(axis=-1) != np.isnan(self.pixels).all(axis=-1)):
            raise ValueError("An absent observation requires both pixel coordinates to be NaN")
        if any(min(camera.image_size) <= 0 for camera in self.cameras):
            raise ValueError("Fitness requires positive calibration image dimensions")


@dataclass(frozen=True, slots=True)
class CameraFitness:
    camera_id: str
    observed_points: int
    qualifying_frames: int
    valid_fraction: float
    median_error: float
    p90_error: float


@dataclass(frozen=True, slots=True)
class GeometryFitness:
    status: GeometryFitnessStatus
    cameras: tuple[CameraFitness, ...]
    mean_cost: float | None = None


@dataclass(frozen=True, slots=True)
class PairAssignmentCosts:
    """Candidate-independent supported edges, each with a camera-by-camera cost matrix."""

    source_count: int
    camera_count: int
    edges: tuple[tuple[int, int], ...]
    costs: NDArray[np.float64]

    def __post_init__(self) -> None:
        if self.source_count < 2 or self.camera_count < self.source_count:
            raise ValueError("Assignment requires at least two sources and enough cameras")
        if self.costs.shape != (len(self.edges), self.camera_count, self.camera_count):
            raise ValueError("Pair cost shape does not match edges and camera count")
        if not self.edges or len(set(self.edges)) != len(self.edges):
            raise ValueError("Assignment requires unique supported source pairs")
        if any(not 0 <= i < j < self.source_count for i, j in self.edges):
            raise ValueError("Source pair indexes must be ordered and within the source set")
        if np.isnan(self.costs).any() or (self.costs < 0).any():
            raise ValueError("Pair costs must be nonnegative; infinity denotes incompatibility")
        reached = {0}
        while True:
            expanded = reached | {node for edge in self.edges if reached.intersection(edge) for node in edge}
            if expanded == reached:
                break
            reached = expanded
        if len(reached) != self.source_count:
            raise ValueError("Disconnected evidence cannot resolve a complete camera assignment")


@dataclass(frozen=True, slots=True)
class ScoredAssignment:
    camera_indices: tuple[int, ...]
    mean_cost: float


@dataclass(frozen=True, slots=True)
class AssignmentSearchResult:
    best: ScoredAssignment | None
    runner_up: ScoredAssignment | None
    complete: bool
    expanded_nodes: int


class CameraMatchingStatus(StrEnum):
    INITIAL_ACCEPTED = "initial_accepted"
    MATCHED = "matched"
    DISABLED = "disabled"
    INSUFFICIENT = "insufficient"
    AMBIGUOUS = "ambiguous"
    POOR = "poor"
    SEARCH_LIMIT = "search_limit"


@dataclass(frozen=True, slots=True)
class CameraMatchingRequest:
    """Bounded, associated samples; alternating frames are held out from search.

    Source image sizes use (width, height). Pixels already pass detector validity
    and cross-view instance association checks. No filename parsing occurs here.
    """

    source_ids: tuple[str, ...]
    image_sizes: tuple[tuple[int, int], ...]
    cameras: tuple[CameraModel, ...]
    pixels: NDArray[np.float64]
    initial_assignment: tuple[int, ...] | None
    config: CameraMatchingConfig

    def __post_init__(self) -> None:
        if len(self.source_ids) < 2 or len(set(self.source_ids)) != len(self.source_ids):
            raise ValueError("Matching requires at least two uniquely labeled sources")
        if len(self.image_sizes) != len(self.source_ids) or any(min(size) <= 0 for size in self.image_sizes):
            raise ValueError("Each source requires positive image dimensions")
        if len(self.cameras) < len(self.source_ids) or len({camera.id for camera in self.cameras}) != len(self.cameras):
            raise ValueError("Matching requires enough uniquely identified calibration cameras")
        if self.pixels.ndim != 4 or self.pixels.shape[0] != len(self.source_ids) or self.pixels.shape[-1] != 2:
            raise ValueError("Matching pixels require shape (sources, frames, points, 2)")
        if np.isinf(self.pixels).any() or np.any(np.isnan(self.pixels).any(axis=-1) != np.isnan(self.pixels).all(axis=-1)):
            raise ValueError("Matching pixels require finite xy pairs or absent NaN pairs")
        if self.initial_assignment is not None:
            if (len(self.initial_assignment) != len(self.source_ids)
                    or len(set(self.initial_assignment)) != len(self.source_ids)
                    or any(not 0 <= index < len(self.cameras) for index in self.initial_assignment)):
                raise ValueError("Initial assignment must map every source to a distinct existing camera")

    def fitness_request(self, *, assignment: tuple[int, ...], validation: bool) -> GeometryFitnessRequest:
        return GeometryFitnessRequest(
            cameras=tuple(self.cameras[index] for index in assignment),
            pixels=self.pixels[:, int(validation)::2],
            config=self.config,
        )

    def compatible(self, *, source: int, camera: int) -> bool:
        return self.image_sizes[source] == self.cameras[camera].image_size


@dataclass(frozen=True, slots=True)
class CameraMatchingResult:
    """Selected assignment can remain provisional; status determines verified fitness."""

    status: CameraMatchingStatus
    assignment: tuple[int, ...] | None
    fitness: GeometryFitness | None
    search: AssignmentSearchResult | None
