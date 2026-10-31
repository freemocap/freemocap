"""Time-domain recovery, missing-parent retention and fitting evidence regressions."""
import numpy as np
import pytest
from skellyforge.core.data_tensors.channel_values import ChannelValues, SPATIAL_COMPONENTS
from freemocap.core.pipeline.realtime.temporal_pipeline import TemporalPipeline
from freemocap.core.tasks.mocap.realtime_filtering.realtime_filter_config import RealtimeFilterConfig
from freemocap.core.skeletons.pose_continuity import PoseContinuity
from freemocap.core.reconstruction.recording_pose_outputs import RecordingPoseOutputs
from freemocap.core.types.channel_kind import ChannelKind
from freemocap.tests.test_weighted_attachment_outputs import pose_fixture, calculate_channels
from freemocap.tests.test_temporal_pipeline import points


def test_complete_dropout_expires_without_restarting_observation_age():
    pipeline = TemporalPipeline(RealtimeFilterConfig(gap_duration_s=.3))
    pipeline.process(timestamp_s=0., points=points(10))
    empty = ChannelValues.empty(component_names=SPATIAL_COMPONENTS)
    assert pipeline.process(timestamp_s=.2, points=empty).predicted_mask.all()
    assert pipeline.process(timestamp_s=.3, points=empty).retained_mask.all()
    assert not pipeline.process(timestamp_s=.301, points=empty).positions


def test_prediction_is_independent_of_missing_frame_frequency():
    results = []
    for fps in (15, 30, 60):
        pipeline = TemporalPipeline(RealtimeFilterConfig())
        pipeline.process(timestamp_s=0., points=points(0))
        pipeline.process(timestamp_s=.033, points=points(5))
        for timestamp in np.linspace(.05, .25, fps):
            output = pipeline.process(timestamp_s=float(timestamp), points=ChannelValues.empty(component_names=SPATIAL_COMPONENTS))
        results.append(output.positions.data_values)
    np.testing.assert_allclose(results[0], results[1], rtol=0, atol=1e-12)
    np.testing.assert_allclose(results[0], results[2], rtol=0, atol=1e-12)


def test_retaining_chest_preserves_available_limbs_until_duration_expires():
    bundle, fit, poses = pose_fixture()
    continuity = PoseContinuity()
    first = poses.sample_view(slice(0,1))
    continuity.apply(poses=first, observed_present=first.segment_present, timestamp_s=0., duration_s=.3)
    missing = poses.sample_view(slice(1,2))
    recovered, status = continuity.apply(poses=missing, observed_present=missing.segment_present, timestamp_s=.2, duration_s=.3)
    outputs = RecordingPoseOutputs(bundle=bundle, fit=fit, compute_center_of_mass=False)
    channels = calculate_channels(outputs, recovered)
    assert channels[ChannelKind.SEGMENT_ORIGINS].companion_values('entry_presence').all()
    assert status[poses.segment_names.index('thoracic')] == 3
    expired, status = continuity.apply(poses=missing, observed_present=missing.segment_present, timestamp_s=.31, duration_s=.3)
    assert not expired.segment_present[0, poses.segment_names.index('thoracic')]
    assert status[poses.segment_names.index('thoracic')] == 0


def test_generated_keypoints_do_not_update_body_dimensions(monkeypatch):
    from freemocap.core.skeletons.reconstruct_skeleton import reconstruct_skeleton
    from freemocap.core.skeletons.reconstruction_state import build_reconstruction_states, streaming_model_scale_source
    from freemocap.core.skeletons.standard_human_skeleton import build_standard_human_bundle
    from freemocap.tests.test_model_scale_in_the_loop import _standing_keypoints
    bundle = build_standard_human_bundle(detector_type='rtmpose')
    state = build_reconstruction_states(bundles=(bundle,), scale_source_for=streaming_model_scale_source(window_frames=5))[bundle.model_id]
    observed = ChannelValues.from_mapping(_standing_keypoints(), component_names=SPATIAL_COMPONENTS)
    first = reconstruct_skeleton(bundle=bundle, state=state, filtered_keypoints=observed,
        observed_keypoints=observed, timestamp_s=0., segment_retention_s=.3, compute_center_of_mass=True)
    seen = []
    original = type(state.scale_source).observe_tensor
    def observe(source, *, poses):
        seen.append(poses.segment_present.copy())
        original(source, poses=poses)
    monkeypatch.setattr(type(state.scale_source), 'observe_tensor', observe)
    generated = observed.with_values(observed.data_values * 1.5)
    absent = generated.with_values(generated.data_values, np.zeros(len(generated.names), bool))
    second = reconstruct_skeleton(bundle=bundle, state=state, filtered_keypoints=generated,
        observed_keypoints=absent, timestamp_s=.1, segment_retention_s=.3, compute_center_of_mass=True)
    assert not seen[-1].any()
    assert second.fitted_scale_mm == first.fitted_scale_mm
    assert second.generated_support


@pytest.mark.parametrize('value', [float('nan'), 0., -.1])
def test_invalid_or_nonincreasing_time_is_rejected(value):
    pipeline = TemporalPipeline(RealtimeFilterConfig())
    pipeline.process(timestamp_s=0., points=points(0))
    with pytest.raises(ValueError):
        pipeline.process(timestamp_s=value, points=points(1))


def test_temporal_status_survives_wire_encoding():
    import cbor2
    from freemocap.core.streaming.message_model import ChannelBlock, _cbor_value
    from freemocap.core.streaming.channel_helpers import temporal_status_bytes, TEMPORAL_STATUS_LABELS
    pipeline = TemporalPipeline(RealtimeFilterConfig())
    pipeline.process(timestamp_s=0., points=points(10))
    output = pipeline.process(timestamp_s=.2, points=ChannelValues.empty(component_names=SPATIAL_COMPONENTS))
    channel = ChannelBlock(kind=ChannelKind.KEYPOINTS_3D, columns=SPATIAL_COMPONENTS,
        names=output.positions.names, data=output.positions.data_values.astype('<f4').tobytes(),
        sample_status=temporal_status_bytes(names=output.positions.names, status=output.sample_status),
        status_labels=TEMPORAL_STATUS_LABELS)
    decoded = cbor2.loads(cbor2.dumps(_cbor_value(channel)))
    assert decoded['sample_status'] == bytes([3])
    assert decoded['status_labels'][3] == 'retained_value'


def test_pixel_space_does_not_use_millimeter_smoothing_or_motion_gate():
    pipeline = TemporalPipeline(RealtimeFilterConfig(max_velocity_mm_per_s=1.))
    pipeline.process(timestamp_s=0., points=points(0), metric_space=False)
    result = pipeline.process(timestamp_s=.03, points=points(100), metric_space=False)
    assert result.positions.data_values[0, 0] == 100
    assert not result.predicted_mask.any()
