"""Exercise the common production temporal pipeline, not copied filter formulas."""
import numpy as np
import pytest
from pydantic import ValidationError
from skellyforge.core.data_tensors.channel_values import ChannelValues, SPATIAL_COMPONENTS
from skellytracker.core.data_primitives.keypoints import Keypoints
from skellytracker.core.data_primitives.observation import Observation, StageObservation
from freemocap.core.pipeline.realtime.temporal_pipeline import TemporalPipeline
from freemocap.core.tasks.mocap.realtime_filtering.realtime_filter_config import RealtimeFilterConfig, OneEuroConfig


def points(value):
    return ChannelValues(('tracked_point',), np.array([[float(value), 0., 0.]]), component_names=SPATIAL_COMPONENTS)


def test_velocity_gate_does_not_overwrite_smoothing():
    pipeline = TemporalPipeline(RealtimeFilterConfig())
    samples = [pipeline.process(timestamp_s=frame/30., points=points(100 + 5*(-1)**frame)).positions.data_values[0, 0]
               for frame in range(120)]
    assert np.std(samples[30:]) < 1


def test_rejected_spike_does_not_enter_smoothing_state():
    pipeline = TemporalPipeline(RealtimeFilterConfig(max_velocity_mm_per_s=100.))
    pipeline.process(timestamp_s=0., points=points(0))
    rejected = pipeline.process(timestamp_s=.03, points=points(5000))
    assert rejected.predicted_mask.all()
    assert not rejected.observed_positions
    returned = pipeline.process(timestamp_s=.06, points=points(0))
    np.testing.assert_array_equal(returned.positions.data_values, [[0, 0, 0]])


def test_disabled_smoothing_and_gate_pass_finite_values():
    pipeline = TemporalPipeline(RealtimeFilterConfig(spatial_smoothing=OneEuroConfig(enabled=False), velocity_gate_enabled=False))
    for frame in range(4):
        input_points = points(frame*10000)
        result = pipeline.process(timestamp_s=frame/30., points=input_points)
        np.testing.assert_array_equal(result.positions.data_values, input_points.data_values)


def test_coefficients_update_without_discarding_history_and_reset_forgets_history():
    pipeline = TemporalPipeline(RealtimeFilterConfig())
    pipeline.process(timestamp_s=0., points=points(0))
    state = pipeline.spatial_filter
    pipeline.configure(RealtimeFilterConfig(spatial_smoothing=OneEuroConfig(min_cutoff=.2, beta=0.)))
    assert pipeline.spatial_filter is state
    assert state.min_cutoff == .2
    result = pipeline.process(timestamp_s=.1, points=points(10))
    assert 0 < result.positions.data_values[0, 0] < 5
    pipeline.reset()
    result = pipeline.process(timestamp_s=.2, points=points(10))
    assert result.positions.data_values[0, 0] == 10


def test_image_gate_precedes_smoothing_preserves_raw_and_recovers():
    pipeline = TemporalPipeline(RealtimeFilterConfig(image_smoothing=OneEuroConfig(beta=.0001)))
    for index, (value, confidence) in enumerate(((0., 1.), (10000., .1), (2., 1.))):
        raw = Observation(frame_number=index, image_size=(640, 480), stages={'body': StageObservation(name='body',
            keypoints=Keypoints(('tracked_point',), np.array([[value, value, 17.]]), np.array([confidence])))})
        output = pipeline.image_observation(camera_id='camera_one', observation=raw, timestamp_s=index/30., confidence_threshold=.4)
        assert raw.stages['body'].keypoints.xyz[0, 0] == value
        assert output.stages['body'].keypoints.xyz[0, 2] == 17.
        assert output.stages['body'].keypoints.visibility[0] == confidence
        if index == 1:
            assert np.isnan(output.stages['body'].keypoints.xy).all()
        if index == 2:
            assert np.isfinite(output.stages['body'].keypoints.xy).all()
            assert output.stages['body'].keypoints.xy.max() <= 2.


@pytest.mark.parametrize('changes', [{'min_cutoff':0}, {'beta':-1}, {'d_cutoff':float('nan')}, {'typo':1}])
def test_invalid_filter_parameters_are_rejected(changes):
    with pytest.raises(ValidationError):
        OneEuroConfig(**changes)
