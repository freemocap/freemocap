"""Dense reconstruction boundaries: declared layouts, ownership and bulk consumers."""
import numpy as np
import pytest
from skellytracker.core.data_primitives.keypoints import Keypoints
from skellyforge.core.data_tensors.channel_values import ChannelValues, SPATIAL_COMPONENTS
from freemocap.core.pipeline.realtime.temporal_pipeline import TemporalPipeline
from freemocap.core.tasks.mocap.realtime_filtering.realtime_filter_config import RealtimeFilterConfig, OneEuroConfig
from skellytracker.core.data_primitives.observation import Observation, StageObservation
from freemocap.core.pipeline.realtime.realtime_keypoint_filter import RealtimeKeypointFilter
from freemocap.core.tasks.mocap.realtime_filtering.one_euro_filter import OneEuroFilter1D
from freemocap.core.recording.result_processing.input_signatures import point_array_signature
from freemocap.core.streaming.channel_helpers import assemble_channel_bytes
from freemocap.core.skeletons.reconstruct_skeleton import reconstruct_skeleton
from freemocap.core.skeletons.reconstruction_state import build_reconstruction_states, streaming_model_scale_source
from freemocap.core.skeletons.standard_human_skeleton import build_standard_human_bundle
from freemocap.tests.test_model_scale_in_the_loop import _standing_keypoints


def test_channel_layout_selection_and_declared_wire_components():
    values = np.arange(6, dtype=np.float64).reshape(2, 3)
    channel = ChannelValues(('second', 'first'), values, component_names=SPATIAL_COMPONENTS)
    assert np.shares_memory(channel.aligned(channel.names), values)
    np.testing.assert_array_equal(channel.aligned(('first', 'second')), values[::-1])
    with pytest.raises(ValueError):
        ChannelValues(channel.names, values, component_names=('x', 'y'))
    with pytest.raises(ValueError):
        assemble_channel_bytes(names=channel.names, positions=channel, columns=('x', 'y'))
    with pytest.raises(ValueError):
        assemble_channel_bytes(names=channel.names, positions=channel, columns=(*SPATIAL_COMPONENTS, 'reprojection_error'))
    packed = assemble_channel_bytes(names=('first', 'absent', 'second'), positions=channel,
        columns=(*SPATIAL_COMPONENTS, 'reprojection_error'), unavailable_components=('reprojection_error',))
    actual = np.frombuffer(packed, '<f4').reshape(3, 4)
    np.testing.assert_array_equal(actual[[0, 2], :3], values[::-1])
    assert np.isnan(actual[:, -1]).all() and np.isnan(actual[1]).all()


def test_masked_fingerprint_matches_explicit_mask_without_changing_chunk_boundaries():
    rng = np.random.default_rng(73)
    values = rng.normal(size=(2103, 7, 3))
    present = rng.random(values.shape[:2]) > .2
    expected = point_array_signature(np.where(present[..., None], values, np.nan))
    assert point_array_signature(values, measured_support=present) == expected


def test_camera_filter_matches_finite_scalar_recurrence_and_preserves_z_visibility():
    names = ('first', 'second')
    state = TemporalPipeline(RealtimeFilterConfig(image_smoothing=OneEuroConfig(beta=.0001)))
    scalar = None
    for frame in range(5):
        xyz = np.array([[10. + frame, 20. - frame, 17.], [40. - frame, 50. + frame, 19.]])
        confidence = np.array([.4, .7])
        keypoints = Keypoints(names=names, xyz=xyz.copy(), visibility=confidence.copy())
        timestamp = frame / 30.
        if scalar is None:
            scalar = [[OneEuroFilter1D(t0=timestamp, x0=float(value), beta=.0001)
                       for value in row[:2]] for row in xyz]
            expected = xyz[:, :2]
        else:
            expected = np.array([[scalar[row][column](t=timestamp, x=float(xyz[row, column]))
                                  for column in range(2)] for row in range(2)])
        observation = Observation(frame_number=frame, image_size=(640, 480),
            stages={'body': StageObservation(name='body', keypoints=keypoints)})
        filtered = state.image_observation(camera_id='camera_one', observation=observation,
            timestamp_s=timestamp, confidence_threshold=.4)
        keypoints = filtered.stages['body'].keypoints
        np.testing.assert_allclose(keypoints.xyz[:, :2], expected, equal_nan=True, rtol=1e-13)
        np.testing.assert_array_equal(keypoints.xyz[:, 2], xyz[:, 2])
        np.testing.assert_array_equal(keypoints.visibility, confidence)


def test_live_tensor_outputs_own_arrays_and_reuse_prepared_geometry(monkeypatch):
    from skellyforge.core.skeleton.pose.pose_tensor import PoseTensor
    def forbid(*args, **kwargs):
        raise AssertionError('Live reconstruction must not construct pose objects')
    monkeypatch.setattr(PoseTensor, 'to_pose', forbid)
    bundle = build_standard_human_bundle(detector_type='rtmpose')
    state = build_reconstruction_states(bundles=(bundle,), scale_source_for=streaming_model_scale_source(window_frames=5))[bundle.model_id]
    points = ChannelValues.from_mapping(_standing_keypoints(), component_names=SPATIAL_COMPONENTS)
    first = reconstruct_skeleton(bundle=bundle, state=state, filtered_keypoints=points, compute_center_of_mass=True)
    retained = first.landmarks.data_values.copy()
    geometry, outputs = state.pose_geometry, state.pose_outputs
    second = reconstruct_skeleton(bundle=bundle, state=state, filtered_keypoints=points.with_values(points.data_values * 1.1), compute_center_of_mass=True)
    assert state.pose_geometry is geometry and state.pose_outputs is outputs
    np.testing.assert_array_equal(first.landmarks.data_values, retained)
    for channel in (first.landmarks, first.segment_rotations_world, first.segment_lengths):
        assert type(channel) is ChannelValues
        assert not channel.data_values.flags.writeable
        assert not channel.entry_present.flags.writeable
        with pytest.raises(ValueError):
            channel.data_values.setflags(write=True)
    assert first.fitted_scale_mm != second.fitted_scale_mm


def test_dense_velocity_gate_matches_scalar_accept_hold_and_timeout():
    from freemocap.core.tasks.mocap.realtime_filtering.realtime_point_gate import RealtimePointGate
    gate = RealtimePointGate(max_velocity_mm_per_s=20., reacquisition_timeout_s=.3)
    accepted, accepted_times, previous = {}, {}, None
    first_result = None
    frames = ({'a': (0., 0., 0.)}, {'a': (1., 0., 0.), 'b': (3., 0., 0.)},
              {'a': (100., 0., 0.)}, {'a': (100., 0., 0.)}, {'a': (100., 0., 0.)},
              {'b': (4., 0., 0.)}, {'a': (101., 0., 0.)})
    for frame, entries in enumerate(frames):
        timestamp = frame * .1
        expected, held = {}, set()
        for name, values in entries.items():
            value = np.asarray(values)
            reject = (name in accepted and timestamp - accepted_times[name] < .3
                      and np.linalg.norm(value - accepted[name]) > 20. * (timestamp - accepted_times[name]))
            if reject:
                held.add(name)
            else:
                accepted[name] = value.copy()
                accepted_times[name] = timestamp
                expected[name] = accepted[name]
        previous = timestamp
        values = ChannelValues.from_mapping(entries, component_names=SPATIAL_COMPONENTS)
        result = gate.gate(t=timestamp, points=values)
        assert result.positions.keys() == expected.keys()
        assert result.held_names == held
        for name in expected:
            np.testing.assert_array_equal(result.positions[name], expected[name])
        if first_result is None:
            first_result = result.positions
    np.testing.assert_array_equal(first_result['a'], [0., 0., 0.])
    gate.reset()
    np.testing.assert_array_equal(gate.gate(t=0., points=values).positions['a'], [101., 0., 0.])
