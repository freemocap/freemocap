"""Filtering respects time, measured support, and rigid coordinate changes."""

import numpy as np
import pytest
from numpy.typing import NDArray
from pydantic import ValidationError

from freemocap.core.reconstruction.posthoc_filtering import PosthocFilterConfig, filter_recording_points
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig


def signal(*, times: NDArray[np.float64]) -> NDArray[np.float64]:
    return np.column_stack((
        50 * np.sin(2 * np.pi * times) + 5 * np.sin(2 * np.pi * 12 * times),
        25 * np.cos(2 * np.pi * times),
        np.full(times.shape, 1000.),
    ))[:, None, :]


@pytest.mark.parametrize("irregular", [False, True])
def test_filter_removes_fast_jitter_without_changing_slow_motion_or_timing(irregular: bool) -> None:
    times = np.arange(600, dtype=np.float64) / 60
    if irregular:
        times += .002 * np.sin(np.arange(600))
    points = signal(times=times)
    original = points.copy()
    result = filter_recording_points(points=points, timestamps_s=times, config=PosthocFilterConfig(cutoff=5))
    truth = 50 * np.sin(2 * np.pi * times)
    interior = slice(60, -60)
    error_before = np.sqrt(np.mean((points[interior, 0, 0] - truth[interior]) ** 2))
    error_after = np.sqrt(np.mean((result.points[interior, 0, 0] - truth[interior]) ** 2))
    assert error_after < error_before / 10
    assert result.report.filtered_runs == 1
    assert result.report.preserved_short_runs == 0
    assert result.report.sampling_rate_hz == pytest.approx(60, rel=.01)
    np.testing.assert_array_equal(points, original)
    np.testing.assert_allclose(result.points[:, 0, 2], 1000., atol=1e-8)


def test_missing_observations_and_timestamp_gaps_separate_runs() -> None:
    times = np.arange(240, dtype=np.float64) / 60
    times[120:] += 10
    points = signal(times=times)
    points[70:90] = np.nan
    result = filter_recording_points(points=points, timestamps_s=times, config=PosthocFilterConfig())
    changed = points.copy()
    changed[90:120] += 10000
    changed[120:] -= 10000
    other = filter_recording_points(points=changed, timestamps_s=times, config=PosthocFilterConfig())
    np.testing.assert_array_equal(np.isnan(result.points), np.isnan(points))
    np.testing.assert_array_equal(result.points[:70], other.points[:70])
    np.testing.assert_allclose(other.points[90:120] - 10000, result.points[90:120], atol=1e-8)
    np.testing.assert_allclose(other.points[120:] + 10000, result.points[120:], atol=1e-8)
    assert result.report.filtered_runs == 3


def test_short_runs_are_reported_and_disabled_filter_is_identity() -> None:
    times = np.arange(20, dtype=np.float64) / 30
    points = signal(times=times)
    points[5:12] = np.nan
    result = filter_recording_points(points=points, timestamps_s=times, config=PosthocFilterConfig())
    np.testing.assert_array_equal(result.points, points)
    assert result.report.preserved_short_runs == 2
    assert result.report.filtered_runs == 0
    disabled = filter_recording_points(points=points, timestamps_s=times, config=PosthocFilterConfig(enabled=False))
    assert disabled.points is points
    assert disabled.report.sampling_rate_hz is None


def test_filter_is_equivariant_under_rigid_scene_transform() -> None:
    times = np.arange(300, dtype=np.float64) / 60
    points = signal(times=times)
    points[140:145] = np.nan
    angle = .7
    rotation = np.array([[np.cos(angle), -np.sin(angle), 0], [np.sin(angle), np.cos(angle), 0], [0, 0, 1]])
    offset = np.array([125., -80., 42.])
    base = filter_recording_points(points=points, timestamps_s=times, config=PosthocFilterConfig())
    transformed = filter_recording_points(points=points @ rotation.T + offset, timestamps_s=times, config=PosthocFilterConfig())
    np.testing.assert_allclose(transformed.points, base.points @ rotation.T + offset, atol=1e-8)


@pytest.mark.parametrize("cutoff", [15., 30.])
def test_nyquist_validation_uses_recording_timestamps(cutoff: float) -> None:
    times = np.arange(30, dtype=np.float64) / 30
    with pytest.raises(ValueError, match="Nyquist"):
        filter_recording_points(points=signal(times=times), timestamps_s=times, config=PosthocFilterConfig(cutoff=cutoff))


@pytest.mark.parametrize("settings", [
    {"cutoff": 0}, {"cutoff": float("nan")}, {"order": 0}, {"order": 11},
    {"order": 2.5}, {"method": "unknown"}, {"sampling_rate": 30},
])
def test_invalid_api_filter_settings_fail(settings: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        PosthocMocapPipelineConfig.model_validate({"filterConfig": settings})


def test_invalid_timestamps_and_partial_coordinates_fail() -> None:
    times = np.array([0., .1, .05])
    points = signal(times=times)
    with pytest.raises(ValueError, match="strictly increasing"):
        filter_recording_points(points=points, timestamps_s=times, config=PosthocFilterConfig())
    times = np.arange(3, dtype=np.float64) / 30
    points[1, 0, 1] = np.nan
    with pytest.raises(ValueError, match="three finite"):
        filter_recording_points(points=points, timestamps_s=times, config=PosthocFilterConfig())


def test_filter_configuration_survives_api_roundtrip() -> None:
    config = PosthocMocapPipelineConfig.model_validate({"filterConfig": {"enabled": True, "cutoff": 4.5, "order": 3}})
    restored = PosthocMocapPipelineConfig.model_validate_json(config.model_dump_json(by_alias=True, round_trip=True))
    assert restored.filter_config == config.filter_config
