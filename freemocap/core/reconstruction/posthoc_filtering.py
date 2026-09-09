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


@dataclass(frozen=True, slots=True, kw_only=True)
class FilteredRecording:
    points: NDArray[np.float64]
    report: PosthocFilterReport


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
    if intervals.size == 0:
        raise ValueError("Enabled filtering requires at least two recording timestamps")
    interval = float(np.median(intervals))
    rate = 1.0 / interval
    if config.cutoff >= rate / 2 or np.isclose(config.cutoff, rate / 2, rtol=1e-12, atol=0):
        raise ValueError(f"Filter cutoff {config.cutoff:g} Hz must be below recording Nyquist frequency {rate / 2:g} Hz")
    # Match the SOS forward/backward filter's odd-padding length for a Butterworth design.
    pad_length = 3 * (config.order + 1)
    output = points.copy()
    filtered_runs = 0
    short_runs = 0
    time_breaks = np.flatnonzero(intervals > 1.5 * interval) + 1
    for point_index in range(points.shape[1]):
        boundaries = np.unique(np.concatenate((
            [0, len(timestamps_s)], np.flatnonzero(np.diff(valid[:, point_index])) + 1, time_breaks,
        )))
        for start, stop in zip(boundaries[:-1], boundaries[1:], strict=True):
            if not valid[start, point_index]:
                continue
            if stop - start <= pad_length:
                short_runs += 1
                continue
            times = timestamps_s[start:stop]
            values = points[start:stop, point_index]
            # Filter on a uniform grid within measured support, then return to observed times.
            count = max(stop - start, int(np.ceil((times[-1] - times[0]) * rate)) + 1)
            grid = np.linspace(times[0], times[-1], num=count)
            grid_rate = (count - 1) / float(times[-1] - times[0])
            uniform = np.column_stack([np.interp(x=grid, xp=times, fp=values[:, axis]) for axis in range(3)])
            sections = butter(N=config.order, Wn=config.cutoff, fs=grid_rate, btype="lowpass", output="sos")
            filtered = sosfiltfilt(sos=sections, x=uniform, axis=0, padlen=pad_length)
            if not np.isfinite(filtered).all():
                raise ValueError("Butterworth filtering produced nonfinite coordinates")
            output[start:stop, point_index] = np.column_stack([
                np.interp(x=times, xp=grid, fp=filtered[:, axis]) for axis in range(3)
            ])
            filtered_runs += 1
    return FilteredRecording(points=output, report=PosthocFilterReport(
        config=config, sampling_rate_hz=rate, filtered_runs=filtered_runs, preserved_short_runs=short_runs,
    ))
