"""Dense smoothing preserves the scalar recurrence through gaps and axis changes."""

import numpy as np
import pytest

from skellyforge.core.data_tensors.channel_values import ChannelValues
from freemocap.core.pipeline.realtime.realtime_keypoint_filter import RealtimeKeypointFilter
from freemocap.core.tasks.mocap.realtime_filtering.one_euro_filter import OneEuroFilter1D


@pytest.mark.parametrize("component_count", [1, 2, 3, 5])
def test_dense_filter_matches_scalar_recurrence(component_count):
    random = np.random.default_rng(541)
    entity_names = tuple(f"tracked_point_{index}" for index in range(7))
    component_names = tuple(f"signal_component_{index}" for index in range(component_count))
    values = np.cumsum(random.normal(size=(80, len(entity_names), component_count)), axis=0)
    times = np.cumsum(random.uniform(0.01, 0.15, len(values)))
    present = random.random(values.shape[:2]) > 0.2
    present[:8, -1] = False  # A late arrival must have no pre-existing filter state.
    present[20:30, 2] = False  # Exhaust prediction, then recover using elapsed source time.
    present[40:45] = False
    settings = dict(min_cutoff=0.7, beta=0.013, d_cutoff=1.4)
    dense = RealtimeKeypointFilter(dims=component_count, gap_duration_s=0.0, **settings)
    scalar_filters = {}
    prediction_counts = {}
    retained_outputs = []
    for frame_index, timestamp in enumerate(times):
        expected, predicted_names = {}, set()
        for entity_index, name in enumerate(entity_names):
            if present[frame_index, entity_index]:
                sample = values[frame_index, entity_index]
                if name not in scalar_filters:
                    scalar_filters[name] = tuple(OneEuroFilter1D(t0=float(timestamp), x0=float(value), **settings)
                                                 for value in sample)
                    expected[name] = sample.copy()
                else:
                    expected[name] = np.array([scalar(t=float(timestamp), x=float(value))
                                              for scalar, value in zip(scalar_filters[name], sample, strict=True)])
                prediction_counts[name] = 0
            else:
                scalar_filters.pop(name, None)
        # Reorder the incoming axis to catch state accidentally indexed by arrival position.
        order = random.permutation(len(entity_names))
        incoming = ChannelValues(tuple(entity_names[index] for index in order),
                                 values[frame_index, order].copy(), present[frame_index, order].copy(),
                                 component_names=component_names)
        result = dense.filter(t=float(timestamp), raw_keypoints=incoming)
        assert set(result.positions) == set(expected)
        assert result.predicted_names == frozenset(predicted_names)
        for name, expected_value in expected.items():
            np.testing.assert_allclose(result.positions[name], expected_value, atol=1e-12, rtol=1e-12)
        retained_outputs.append((result.positions, result.positions.data_values.copy(),
                                 result.positions.entry_present.copy()))
    dense.reset()
    for published, expected_values, expected_presence in retained_outputs:
        np.testing.assert_array_equal(published.data_values, expected_values)
        np.testing.assert_array_equal(published.entry_present, expected_presence)
    empty = ChannelValues((), np.empty((0, component_count)), component_names=component_names)
    assert not dense.filter(t=0.0, raw_keypoints=empty).positions


def test_filter_rejects_component_reordering_without_advancing_state():
    component_names = ("horizontal_position", "vertical_position")
    first = ChannelValues(("tracked_point",), np.array([[1., 2.]]), component_names=component_names)
    second = ChannelValues(("tracked_point",), np.array([[4., 7.]]), component_names=component_names)
    dense = RealtimeKeypointFilter(dims=len(component_names))
    control = RealtimeKeypointFilter(dims=len(component_names))
    dense.filter(t=0.0, raw_keypoints=first)
    control.filter(t=0.0, raw_keypoints=first)
    reversed_components = ChannelValues(first.names, second.data_values[:, ::-1],
                                       component_names=component_names[::-1])
    with pytest.raises(ValueError, match="[Cc]omponent"):
        dense.filter(t=0.1, raw_keypoints=reversed_components)
    actual = dense.filter(t=0.1, raw_keypoints=second)
    expected = control.filter(t=0.1, raw_keypoints=second)
    np.testing.assert_array_equal(actual.positions.data_values, expected.positions.data_values)
