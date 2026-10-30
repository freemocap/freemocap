"""Timestamp-aware Butterworth filtering of measured 3D trajectories.

Missing points and timestamp gaps split trajectories. Runs too short for the
filter's padding retain their measured values and are counted in the report.
No missing observation is filled or made eligible for scale fitting.
"""

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field
from scipy.signal import butter, sosfiltfilt
from freemocap.core.reconstruction.trajectory_gap_filling import GapFillingReport, fill_trajectory_gaps


class PosthocFilterConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    enabled: bool = True
    method: Literal["butter_low_pass"] = "butter_low_pass"
    cutoff: float = Field(default=6.0, gt=0)
    order: int = Field(default=4, ge=1, le=10)


class PosthocFilterReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    algorithm_version: Literal[1] = 1
    config: PosthocFilterConfig
    sampling_rate_hz: float | None
    filtered_runs: int = Field(ge=0)
    preserved_short_runs: int = Field(ge=0)
    gap_filling: GapFillingReport | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class FilteredRecording:
    points: NDArray[np.float64]
    report: PosthocFilterReport


def prepare_recording_points(*, points: NDArray[np.float64], timestamps_s: NDArray[np.float64], config: PosthocFilterConfig) -> FilteredRecording:
    completed, gaps = fill_trajectory_gaps(points=points, timestamps_s=timestamps_s)
    filtered = filter_recording_points(points=completed, timestamps_s=timestamps_s, config=config)
    return FilteredRecording(points=filtered.points, report=filtered.report.model_copy(update={"gap_filling": gaps}))


def validate_filter_timing(*, timestamps_s: NDArray[np.float64], config: PosthocFilterConfig) -> float:
    if timestamps_s.ndim != 1 or not np.isfinite(timestamps_s).all():
        raise ValueError("Filtering requires a finite timestamp vector")
    intervals = np.diff(timestamps_s)
    if intervals.size == 0 or np.any(intervals <= 0):
        raise ValueError("Enabled filtering requires at least two strictly increasing recording timestamps")
    rate = 1.0 / float(np.median(intervals))
    if config.enabled and (config.cutoff >= rate / 2 or np.isclose(config.cutoff, rate / 2, rtol=1e-12, atol=0)):
        raise ValueError(
            f"Filter cutoff {config.cutoff:g} Hz must be below recording Nyquist frequency {rate / 2:g} Hz "
            f"({rate:g} frames/s). Set the low-pass cutoff below {rate / 2:g} Hz or disable filtering, then run processing again."
        )
    return rate


def _interpolate_trajectories(*, target_times: NDArray[np.float64], source_times: NDArray[np.float64],
                            values: NDArray[np.float64]) -> NDArray[np.float64]:
    """Apply one linear interpolation plan across every trajectory/component.

    Values have time as their first axis. Preserve exact source knots, including
    endpoints, rather than evaluating a slope at those positions.
    """
    right = np.searchsorted(source_times, target_times, side="left")
    right = np.clip(right, 1, len(source_times) - 1)
    left = right - 1
    expansion = (slice(None),) + (None,) * (values.ndim - 1)
    slopes = (values[right] - values[left]) / (source_times[right] - source_times[left])[expansion]
    result = values[left] + slopes * (target_times - source_times[left])[expansion]
    exact_left = target_times == source_times[left]
    exact_right = target_times == source_times[right]
    result[exact_left] = values[left[exact_left]]
    result[exact_right] = values[right[exact_right]]
    return result


def _compatible_runs(valid: NDArray[np.bool_], time_breaks: NDArray[np.int64], pad_length: int):
    """Group complete valid intervals, without scanning each point in Python."""
    starts = valid.copy()
    starts[1:] &= ~valid[:-1]
    stops = valid.copy()
    stops[:-1] &= ~valid[1:]
    starts[time_breaks] = valid[time_breaks]
    stops[time_breaks - 1] = valid[time_breaks - 1]
    point_indices, start_indices = np.nonzero(starts.T)
    _, stop_indices = np.nonzero(stops.T)
    stop_indices = stop_indices + 1
    eligible = stop_indices - start_indices > pad_length
    short_runs = int(np.count_nonzero(~eligible))
    intervals = np.column_stack((start_indices[eligible], stop_indices[eligible]))
    unique_intervals, group_indices = np.unique(intervals, axis=0, return_inverse=True)
    order = np.argsort(group_indices, kind="stable")
    points = point_indices[eligible][order]
    counts = np.bincount(group_indices, minlength=len(unique_intervals))
    boundaries = np.concatenate(([0], np.cumsum(counts)))
    return unique_intervals, points, boundaries, short_runs


def filter_recording_points(
    *, points: NDArray[np.float64], timestamps_s: NDArray[np.float64], config: PosthocFilterConfig,
) -> FilteredRecording:
    if points.ndim != 3 or points.shape[2] != 3 or points.shape[0] == 0:
        raise ValueError("Filtering requires points shaped (frames, keypoints, 3)")
    if timestamps_s.shape != (points.shape[0],) or not np.isfinite(timestamps_s).all():
        raise ValueError("Filtering requires one finite timestamp per frame")
    intervals = np.diff(timestamps_s)
    if np.any(intervals <= 0):
        raise ValueError("Filtering timestamps must be strictly increasing")
    if np.isinf(points).any():
        raise ValueError("Filtering points cannot contain infinity")
    valid = np.isfinite(points).all(axis=2)
    if np.any(np.isfinite(points).any(axis=2) != valid):
        raise ValueError("Each point must have three finite coordinates or three missing coordinates")
    if not config.enabled:
        return FilteredRecording(points=points, report=PosthocFilterReport(
            config=config, sampling_rate_hz=None, filtered_runs=0, preserved_short_runs=0,
        ))
    rate = validate_filter_timing(timestamps_s=timestamps_s, config=config)
    interval = 1.0 / rate
    # Match the SOS forward/backward filter's odd-padding length for a Butterworth design.
    pad_length = 3 * (config.order + 1)
    output = points.copy()
    time_breaks = np.flatnonzero(intervals > 1.5 * interval) + 1
    run_intervals, point_indices, boundaries, short_runs = _compatible_runs(valid, time_breaks, pad_length)
    coefficients = {}
    for group_index, (start, stop) in enumerate(run_intervals):
        selected_points = point_indices[boundaries[group_index]:boundaries[group_index + 1]]
        times = timestamps_s[start:stop]
        values = points[start:stop, selected_points]
        # Every point in this group has exactly the same measured support and
        # clock. Interpolate/filter their dense time x point x component tensor.
        count = max(stop - start, int(np.ceil((times[-1] - times[0]) * rate)) + 1)
        grid = np.linspace(times[0], times[-1], num=count)
        grid_rate = (count - 1) / float(times[-1] - times[0])
        uniform = _interpolate_trajectories(target_times=grid, source_times=times, values=values)
        sections = coefficients.get(grid_rate)
        if sections is None:
            sections = butter(N=config.order, Wn=config.cutoff, fs=grid_rate, btype="lowpass", output="sos")
            coefficients[grid_rate] = sections
        filtered = sosfiltfilt(sos=sections, x=uniform, axis=0, padlen=pad_length)
        if not np.isfinite(filtered).all():
            raise ValueError("Butterworth filtering produced nonfinite coordinates")
        output[start:stop, selected_points] = _interpolate_trajectories(
            target_times=times, source_times=grid, values=filtered)
    return FilteredRecording(points=output, report=PosthocFilterReport(
        config=config, sampling_rate_hz=rate, filtered_runs=len(point_indices), preserved_short_runs=short_runs,
    ))
