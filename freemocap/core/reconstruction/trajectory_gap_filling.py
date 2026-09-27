"""Complete sampled trajectories without manufacturing never-observed tracks."""
import numpy as np
from typing import Literal
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict


TRAJECTORY_SUPPORT_SECONDS = 0.100
TIME_COMPARISON_TOLERANCE_SECONDS = 1e-12


class GapFillingReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    algorithm_version: Literal[2] = 2
    trajectory_support_seconds: float = TRAJECTORY_SUPPORT_SECONDS
    # (keypoint index, start frame index, exclusive stop); indices use the saved grid.
    filled_spans: tuple[tuple[int, int, int], ...] = ()
    discarded_spans: tuple[tuple[int, int, int], ...] = ()
    unsupported_keypoint_indices: tuple[int, ...] = ()
    method: Literal["timestamp_linear_interior_nearest_endpoint"] = "timestamp_linear_interior_nearest_endpoint"

    def measured_support(self, points: NDArray[np.float64]) -> NDArray[np.bool_]:
        support = np.isfinite(points).all(axis=-1)
        for point, start, stop in (*self.filled_spans, *self.discarded_spans):
            if not (0 <= point < support.shape[1] and 0 <= start < stop <= len(support)):
                raise ValueError("Gap-filling provenance does not match the recording grid")
            support[start:stop, point] = False
        return support


    def original_support(self, points: NDArray[np.float64]) -> NDArray[np.bool_]:
        support = self.measured_support(points)
        for point, start, stop in self.discarded_spans:
            support[start:stop, point] = True
        return support


def _spans(point: int, mask: NDArray[np.bool_]) -> list[tuple[int, int, int]]:
    boundaries = np.flatnonzero(np.diff(np.r_[False, mask, False]))
    return [(point, int(start), int(stop)) for start, stop in boundaries.reshape(-1, 2)]


def fill_trajectory_gaps(
    *, points: NDArray[np.float64], timestamps_s: NDArray[np.float64],
) -> tuple[NDArray[np.float64], GapFillingReport]:
    if points.ndim != 3 or points.shape[-1] != 3 or len(points) == 0:
        raise ValueError("Expected nonempty (frames, keypoints, 3) trajectories")
    if timestamps_s.shape != (len(points),) or not np.isfinite(timestamps_s).all() or np.any(np.diff(timestamps_s) <= 0):
        raise ValueError("Expected finite strictly increasing trajectory timestamps")
    valid = np.isfinite(points).all(axis=-1)
    if np.isinf(points).any() or np.any(np.isfinite(points).any(axis=-1) != valid):
        raise ValueError("Each point must have three finite or three missing coordinates")
    output = points.copy()
    spans = []
    unsupported = []
    discarded = []
    for point in range(points.shape[1]):
        available = valid[:, point].copy()
        indices = np.flatnonzero(available)
        # Consecutive samples form a run at any frame rate. Missing runs bridge
        # only when their bracketing valid timestamps are at most 100 ms apart.
        breaks = np.flatnonzero((np.diff(indices) > 1) &
            (np.diff(timestamps_s[indices]) > TRAJECTORY_SUPPORT_SECONDS + TIME_COMPARISON_TOLERANCE_SECONDS)) + 1
        for run in np.split(indices, breaks):
            if len(run) < 2 or timestamps_s[run[-1]] - timestamps_s[run[0]] < TRAJECTORY_SUPPORT_SECONDS - TIME_COMPARISON_TOLERANCE_SECONDS:
                available[run] = False
        rejected = valid[:, point] & ~available
        discarded.extend(_spans(point, rejected))
        if not available.any():
            unsupported.append(point)
            output[:, point] = np.nan
            continue  # Authored rest geometry completes the model, not the keypoint stream.
        missing = ~available
        for axis in range(3):
            output[missing, point, axis] = np.interp(
                timestamps_s[missing], timestamps_s[available], points[available, point, axis])
        spans.extend(_spans(point, missing))
    return output, GapFillingReport(filled_spans=tuple(spans), discarded_spans=tuple(discarded), unsupported_keypoint_indices=tuple(unsupported))
