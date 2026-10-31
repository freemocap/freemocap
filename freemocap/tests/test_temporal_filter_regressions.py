"""Temporal filtering acceptance cases; initial expected failures document the audit."""
import numpy as np
import pytest
from skellyforge.core.data_tensors.channel_values import ChannelValues
from freemocap.core.pipeline.realtime.realtime_keypoint_filter import RealtimeKeypointFilter
from freemocap.tests.pipelines.mocks.trajectory_perturbations import TrajectoryPerturbations


@pytest.mark.parametrize('complete', [False, True])
def test_perturbations_are_repeatable_and_do_not_change_reference(complete):
    times = np.arange(120) / 30
    values = np.ones((120, 7, 3))
    scenario = TrajectoryPerturbations(noise_sigma=2.0, complete_dropout=complete)
    first, hidden = scenario.apply(timestamps_s=times, values=values)
    second, _ = scenario.apply(timestamps_s=times, values=values)
    np.testing.assert_array_equal(first, second)
    np.testing.assert_array_equal(values, 1)
    assert hidden.sum() == 9 * (7 if complete else 1)


def test_finite_detection_recovers_after_nan():
    temporal_filter = RealtimeKeypointFilter(dims=2)
    for frame, value in enumerate((0., np.nan, 2., 3.)):
        output = temporal_filter.filter(t=frame / 30,
            raw_keypoints=ChannelValues(('tracked_point',), np.full((1, 2), value), component_names=('x', 'y')))
    assert np.isfinite(output.positions.data_values).all()


def test_gap_availability_depends_on_elapsed_time():
    available = []
    for fps in (15, 30, 60):
        temporal_filter = RealtimeKeypointFilter(dims=3)
        temporal_filter.filter(t=0., raw_keypoints={'tracked_point': np.ones(3)})
        for timestamp in np.arange(1, int(fps * .2) + 1) / fps:
            output = temporal_filter.filter(t=float(timestamp), raw_keypoints={})
        available.append('tracked_point' in output.positions)
    assert available == [True, True, True]
