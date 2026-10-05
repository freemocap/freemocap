"""Observations and rigid geometry must remain distinct through reconstruction and IO."""

from dataclasses import replace
from itertools import combinations
from types import SimpleNamespace

import numpy as np
import pytest
from numpy.testing import assert_allclose, assert_array_equal
from skellyforge.core.math.geometry.rotation_quaternion import RotationQuaternion
from skellyforge.core.math.geometry.spatial_vectors import Point
from skellyforge.core.skeleton.pose.hydration import hydrate_skeleton

from freemocap.core.skeletons.reconstruct_skeleton import reconstruct_skeleton
from freemocap.core.skeletons.reconstruction_state import FrozenModelScale, build_reconstruction_states, streaming_model_scale_source
from freemocap.core.skeletons.standard_human_skeleton import build_standard_human_bundle
from freemocap.core.streaming.producers.keypoints_producer import KeypointsProducer
from freemocap.core.streaming.producers.segment_producer import SegmentProducer
from freemocap.core.streaming.producers.producer_contexts import FrameContext
from freemocap.core.types.channel_kind import ChannelKind
from freemocap.tests.test_model_scale_in_the_loop import _standing_keypoints


def state_for(bundle, fit=None):
    return build_reconstruction_states(bundles=(bundle,), scale_source_for=(
        streaming_model_scale_source(window_frames=30) if fit is None else lambda _: FrozenModelScale(fit)
    ))[bundle.model_id]


@pytest.mark.parametrize('tracker', ['rtmpose', 'mediapipe'])
def test_noisy_observations_are_preserved_and_geometry_uses_owning_pose(tracker):
    bundle = build_standard_human_bundle(detector_type=tracker)
    points = _standing_keypoints()
    points['left_elbow'] += [13, 29, -17]
    before = {name: value.copy() for name, value in points.items()}
    mapped = bundle.landmark_mapping.apply(tracker_positions=points)
    state = state_for(bundle)
    result = reconstruct_skeleton(bundle=bundle, state=state, filtered_keypoints=points, compute_center_of_mass=False)
    assert result is not None and result.landmarks
    assert set(result.mapped_keypoints) <= set(bundle.skeleton.landmarks)
    assert result.segment_origins.keys() == result.segment_rotations_world.keys()
    for name in points:
        assert_array_equal(points[name], before[name])
    for name in mapped:
        assert_array_equal(result.mapped_keypoints[name], mapped[name])
    assert any(not np.allclose(result.landmarks[name], mapped[name]) for name in mapped.keys() & result.landmarks.keys())
    fit = state.scale_source.current_fit()
    measured_state = state_for(bundle)
    measured = measured_state.roll_resolver.resolve_pose(pose=hydrate_skeleton(
        skeleton=bundle.skeleton,
        observed={name: Point.from_array(values=value) for name, value in mapped.items()},
        require_all=False))
    assert_allclose(result.segment_origins[bundle.rest_pose.root_segment_name],
                    measured.segment_poses[bundle.rest_pose.root_segment_name].origin.array)
    for name, rotation in result.segment_rotations_world.items():
        # Quaternion signs may differ while representing the same orientation.
        assert_allclose(abs(np.dot(rotation, measured.segment_poses[name].orientation.as_array())), 1., atol=1e-12)
    for joint in bundle.skeleton.joints.values():
        if joint.child.name in result.segment_origins:
            assert_allclose(result.segment_origins[joint.child.name], result.landmarks[joint.connect_at.name], atol=1e-9)
    for name, position in result.landmarks.items():
        landmark = bundle.skeleton.landmarks[name]
        rotation = RotationQuaternion.from_array(array=result.segment_rotations_world[landmark.segment])
        assert_allclose(position, result.segment_origins[landmark.segment] + rotation.rotate_vector(
            vector=fit.segment_scales[landmark.segment] * landmark.local_position.array))
    with_com = reconstruct_skeleton(bundle=bundle, state=state_for(bundle), filtered_keypoints=points, compute_center_of_mass=True)
    for name in result.landmarks:
        assert_array_equal(result.landmarks[name], with_com.landmarks[name])
    # A frozen recording fit preserves within-segment distances as observations change.
    frozen = state_for(bundle, fit)
    for displacement in (0, 90, -45):
        points['left_elbow'] = before['left_elbow'] + [0, displacement, 0]
        frame = reconstruct_skeleton(bundle=bundle, state=frozen, filtered_keypoints=points, compute_center_of_mass=False)
        for segment in bundle.skeleton.segments.values():
            for a, b in combinations(segment.landmarks, 2):
                if a in frame.landmarks and b in frame.landmarks:
                    expected = fit.segment_scales[segment.name] * np.linalg.norm(
                        segment.landmarks[a].local_position.array - segment.landmarks[b].local_position.array)
                    assert_allclose(np.linalg.norm(frame.landmarks[a] - frame.landmarks[b]), expected, atol=1e-9)


def test_observations_survive_unsolved_pose_and_missing_scale_without_stale_points():
    bundle = build_standard_human_bundle(detector_type='rtmpose')
    state = state_for(bundle)
    def reconstruct(points):
        return reconstruct_skeleton(bundle=bundle, state=state, filtered_keypoints=points, compute_center_of_mass=False)
    complete = reconstruct(_standing_keypoints())
    partial = reconstruct({'left_wrist': np.array([1., 2., 3.])})
    assert partial is not None and partial.mapped_keypoints
    assert not partial.landmarks and not partial.segment_origins and not partial.segment_rotations_world
    assert reconstruct({}) is None
    again = reconstruct(_standing_keypoints())
    assert again.landmarks.keys() == complete.landmarks.keys()
    state.scale_source = FrozenModelScale(None)
    no_scale = reconstruct(_standing_keypoints())
    assert no_scale.mapped_keypoints
    assert not no_scale.landmarks and not no_scale.segment_origins and not no_scale.segment_rotations_world


def test_missing_ancestor_suppresses_descendants_without_hiding_other_branches(monkeypatch):
    import importlib
    module = importlib.import_module('freemocap.core.skeletons.reconstruct_skeleton')
    bundle = build_standard_human_bundle(detector_type='rtmpose')
    points = _standing_keypoints()
    mapped = bundle.landmark_mapping.apply(tracker_positions=points)
    measured = hydrate_skeleton(skeleton=bundle.skeleton,
        observed={name: Point.from_array(values=value) for name, value in mapped.items()}, require_all=False)
    full_state = state_for(bundle)
    complete = reconstruct_skeleton(bundle=bundle, state=full_state, filtered_keypoints=points, compute_center_of_mass=False)
    parents = bundle.rest_pose.parents
    root = bundle.rest_pose.root_segment_name
    # Choose an observed intermediate segment with an observed child.
    missing = next(parent for child, parent in parents.items()
        if parent != root and parent in complete.segment_origins and child in complete.segment_origins)
    for absent in (missing, root):
        pose = replace(measured, segment_poses={name: value for name, value in measured.segment_poses.items() if name != absent})
        monkeypatch.setattr(module, 'hydrate_skeleton', lambda **kwargs: pose)
        result = reconstruct_skeleton(bundle=bundle, state=state_for(bundle, full_state.scale_source.current_fit()),
            filtered_keypoints=points, compute_center_of_mass=False)
        expected = set()
        for name in complete.segment_origins:
            ancestor = name
            while ancestor is not None and ancestor != absent:
                ancestor = parents[ancestor]
            if ancestor is None:
                expected.add(name)
        assert set(result.segment_origins) == expected
        assert result.mapped_keypoints.keys() == complete.mapped_keypoints.keys()
        if absent != root:
            assert expected and expected != set(complete.segment_origins)


def test_streaming_keeps_all_products_and_segment_origins_independent():
    bundle = build_standard_human_bundle(detector_type='rtmpose')
    points = _standing_keypoints()
    result = reconstruct_skeleton(bundle=bundle, state=state_for(bundle), filtered_keypoints=points, compute_center_of_mass=False)
    # A segment can reference another segment's landmark for its observation origin.
    # Publishing translations must never look those names up in the landmark output.
    result = replace(result, segment_origins={name: value + [11, 22, 33] for name, value in result.segment_origins.items()})
    context = FrameContext(frame_number=5, timestamp=1.25, aggregator_output=SimpleNamespace(
        keypoints_arrays=points, reconstructions={bundle.model_id: result}))
    blocks = {block.kind: block for block in KeypointsProducer().fill(context, bundle) + SegmentProducer().fill(context, bundle)}
    for kind, names, expected, width in (
        (ChannelKind.KEYPOINTS_3D, bundle.tracker_keypoint_names, points, 4),
        (ChannelKind.MAPPED_KEYPOINTS_3D, tuple(bundle.skeleton.landmarks), result.mapped_keypoints, 4),
        (ChannelKind.LANDMARKS_3D, tuple(bundle.skeleton.landmarks), result.landmarks, 4),
        (ChannelKind.SEGMENT_ORIGINS, tuple(bundle.skeleton.segments), result.segment_origins, 3),
    ):
        values = np.frombuffer(blocks[kind].data, dtype='<f4').reshape(-1, width)
        for index, name in enumerate(names):
            if name in expected:
                assert_allclose(values[index, :3], expected[name], atol=1e-4)
            else:
                assert np.isnan(values[index, :3]).all()


def test_three_products_roundtrip_retained_runs_export_and_invalidation(tmp_path):
    import pyarrow.parquet as pq
    from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
    from freemocap.core.pipeline.posthoc.stage_execution_plan import StageExecutionPlan, retained_run
    from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
    from freemocap.core.recording.exports.tall_csv import TallCsvRequest, export_tall_csv
    from freemocap.system.recording_structure.recording_structure import RecordingStructure
    from freemocap.tests.playback_parquet_fixture import create_fixture
    from freemocap.tests.test_tall_csv_export import read_csv

    create_fixture(tmp_path)
    structure = RecordingStructure(base_directory=tmp_path, recording_name='recording')
    metadata = read_metadata(path=structure.data_parquet_path)
    for run_id, run in metadata.runs.items():
        channels = {c.kind: c for c in run.channels if c.kind in (
            ChannelKind.RAW_KEYPOINTS_3D, ChannelKind.MAPPED_KEYPOINTS_3D, ChannelKind.LANDMARKS_3D)}
        assert len(channels) == 3
        assert channels[ChannelKind.RAW_KEYPOINTS_3D].source != channels[ChannelKind.MAPPED_KEYPOINTS_3D].source
        assert channels[ChannelKind.MAPPED_KEYPOINTS_3D].names == channels[ChannelKind.LANDMARKS_3D].names
        for channel in channels.values():
            table = pq.read_table(structure.data_parquet_path, filters=[('run_id', '=', run_id), ('channel', '=', channel.kind)])
            assert set(table['frame_number'].to_pylist()) == {0, 1}
            assert table['value'].null_count > 0
            assert set(table['units'].to_pylist()) == {'px'}
        result = export_tall_csv(structure=structure, request=TallCsvRequest(run_id=run_id, keep=True))
        expected = pq.read_table(structure.data_parquet_path, filters=[('run_id', '=', run_id)]).replace_schema_metadata(None)
        assert read_csv(result.files[0]).equals(expected)
        retained = retained_run(base=run, plan=StageExecutionPlan(run_id, run_id, ('mocap',),
            (ProcessingStage.RECONSTRUCTION,), (ProcessingStage.RECONSTRUCTION, ProcessingStage.BIOMECHANICS, ProcessingStage.SKELETON_FIT)))
        assert not any(c.kind in (ChannelKind.MAPPED_KEYPOINTS_3D, ChannelKind.LANDMARKS_3D) for c in retained.channels)
        assert any(c.kind == ChannelKind.RAW_KEYPOINTS_3D for c in retained.channels)
