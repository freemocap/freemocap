"""Batched filtering agrees with the previous scalar NumPy/SciPy calculation."""
from unittest.mock import patch

import numpy as np
import pytest
from scipy.signal import butter, sosfiltfilt

from freemocap.core.reconstruction import posthoc_filtering as filtering


def scalar_filter_reference(points, times, config):
    """Independent original per-point algorithm, retained as a numerical oracle."""
    rate = 1. / float(np.median(np.diff(times)))
    valid = np.isfinite(points).all(axis=2)
    breaks = np.flatnonzero(np.diff(times) > 1.5 / rate) + 1
    padding = 3 * (config.order + 1)
    result = points.copy()
    filtered_count = short_count = 0
    for point in range(points.shape[1]):
        bounds = np.unique(np.concatenate(([0, len(times)], np.flatnonzero(np.diff(valid[:, point])) + 1, breaks)))
        for start, stop in zip(bounds[:-1], bounds[1:], strict=True):
            if not valid[start, point]:
                continue
            if stop - start <= padding:
                short_count += 1
                continue
            sample_times = times[start:stop]
            count = max(stop - start, int(np.ceil((sample_times[-1] - sample_times[0]) * rate)) + 1)
            grid = np.linspace(sample_times[0], sample_times[-1], count)
            uniform = np.column_stack([np.interp(grid, sample_times, points[start:stop, point, component]) for component in range(3)])
            sections = butter(N=config.order, Wn=config.cutoff, fs=(count - 1) / float(sample_times[-1] - sample_times[0]),
                             btype='lowpass', output='sos')
            filtered = sosfiltfilt(sections, uniform, axis=0, padlen=padding)
            result[start:stop, point] = np.column_stack([np.interp(sample_times, grid, filtered[:, component]) for component in range(3)])
            filtered_count += 1
    return result, filtered_count, short_count


@pytest.mark.parametrize('order', [1, 4, 7, 10])
@pytest.mark.parametrize('irregular', [False, True])
def test_batched_runs_preserve_scalar_values_missingness_and_counts(order, irregular):
    times = np.arange(320, dtype=np.float64) / 60
    if irregular:
        times += .002 * np.sin(np.arange(len(times)))
    times[160:] += 2
    points = np.random.default_rng(418).normal(size=(320, 11, 3)) * 100 + 1000
    points[50:70, :5] = np.nan
    points[95:110, 3:8] = np.nan  # Different patterns share some of the same intervals.
    points[:, 9] = np.nan
    points[:, 10] = np.nan
    points[1:6, 10] = 42
    original = points.copy()
    config = filtering.PosthocFilterConfig(order=order)
    expected, filtered, short = scalar_filter_reference(points, times, config)
    actual = filtering.filter_recording_points(points=points, timestamps_s=times, config=config)
    np.testing.assert_allclose(actual.points, expected, rtol=0, atol=1e-10)
    np.testing.assert_array_equal(np.isnan(actual.points), np.isnan(points))
    np.testing.assert_array_equal(points, original)
    np.testing.assert_array_equal(actual.points[1:6, 10], points[1:6, 10])
    assert actual.report.filtered_runs == filtered
    assert actual.report.preserved_short_runs == short


def test_shared_intervals_use_one_filter_call_and_exact_rate_coefficients_are_reused():
    times = np.arange(260, dtype=np.float64) / 64  # Exact binary grid rate on both runs.
    points = np.random.default_rng(201).normal(size=(260, 40, 3))
    points[128:132] = np.nan
    with patch.object(filtering, 'butter', wraps=filtering.butter) as design, \
         patch.object(filtering, 'sosfiltfilt', wraps=filtering.sosfiltfilt) as execute:
        result = filtering.filter_recording_points(points=points, timestamps_s=times, config=filtering.PosthocFilterConfig())
    assert design.call_count == 1
    assert execute.call_count == 2
    assert result.report.filtered_runs == 80  # Report counts trajectories, not implementation groups.


@pytest.mark.parametrize('point_count', [0, 1, 17])
def test_all_missing_inputs_need_no_filter_design(point_count):
    points = np.full((50, point_count, 3), np.nan)
    with patch.object(filtering, 'butter', side_effect=AssertionError('No valid runs')):
        result = filtering.filter_recording_points(points=points, timestamps_s=np.arange(50) / 30,
                                                   config=filtering.PosthocFilterConfig())
    np.testing.assert_array_equal(result.points, points)
    assert result.report.filtered_runs == result.report.preserved_short_runs == 0


def test_interpolation_preserves_exact_knots_and_matches_scalar_interpolation():
    times = np.array([0., .021, .06, .09])
    targets = np.sort(np.concatenate((times, [.005, .045, .08])))
    values = np.random.default_rng(1).normal(size=(4, 9, 3))
    result = filtering._interpolate_trajectories(target_times=targets, source_times=times, values=values)
    expected = np.stack([np.column_stack([np.interp(targets, times, values[:, point, axis])
                                         for axis in range(3)]) for point in range(9)], axis=1)
    np.testing.assert_allclose(result, expected, rtol=0, atol=1e-15)
    np.testing.assert_array_equal(result[np.searchsorted(targets, times)], values)
