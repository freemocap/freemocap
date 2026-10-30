"""Fresh recording retention preserves Tracker values without retaining its objects."""
from copy import deepcopy
from dataclasses import replace
from unittest.mock import patch

import numpy as np
import pytest
import pyarrow as pa
from skellytracker.core.data_primitives.observation import Observation, StageObservation
from skellytracker.core.data_primitives.keypoints import Keypoints
from skellytracker.core.data_primitives.bounding_box import BoundingBox

from freemocap.core.tracking.observation_series import RecordingObservationSeries, ObservationFrames
from freemocap.core.tracking.observation_arrays import observation_arrays, ambiguous_instances
from freemocap.core.tracking.observation_buffer import ObservationBuffer
from freemocap.core.pipeline.dataflow.scientific_recording import ObservationCollection
from freemocap.core.pipeline.dataflow.camera_join import ProducerOutcome


def series(count=3):
    return RecordingObservationSeries(camera_id='camera', image_size=(720, 1280),
        frame_numbers=tuple(range(count)), timestamps_s=tuple(i / 30 for i in range(count)))


def observation(index=0):
    child = StageObservation(name='hand', keypoints=Keypoints(names=('tip', 'wrist'),
        xyz=np.array([[4., 5., 17.], [8., 9., 23.]]), visibility=np.array([.6, 0.])),
        bounding_boxes=[BoundingBox(1., 2., 8., 9., .8)], detector_ran=False)
    return Observation(frame_number=index, image_size=(720, 1280), timestamp=None,
        stages={'parent_key': StageObservation(name='body', children={'child_key': child},
            keypoints=Keypoints(names=('hip',), xyz=np.array([[1., 2., 7.]]), visibility=np.array([1.])))})


def test_stable_recording_layout_reuses_storage_and_owns_source_values():
    stored = series()
    source = observation()
    expected = deepcopy(source)
    stored.store(0, source)
    coordinates, confidence, boxes = stored.coordinate_values, stored.confidence_values, stored.box_values
    source.stages['parent_key'].keypoints.xyz[:] = -999.
    source.stages['parent_key'].children['child_key'].bounding_boxes[0].x1 = 100.
    for frame in (1, 2):
        incoming = observation(frame)
        incoming.timestamp = 100. + frame
        stored.store(frame, incoming)
    assert stored.coordinate_values is coordinates and stored.confidence_values is confidence and stored.box_values is boxes
    assert len(stored.layouts) == 1
    actual = observation_arrays(stored[0])
    np.testing.assert_array_equal(actual.coordinate_values, observation_arrays(expected).coordinate_values)
    assert np.shares_memory(actual.coordinate_values, stored.coordinate_values)
    assert stored[0].timestamp is None and stored[2].timestamp == 102.
    restored = stored.annotation_frame(0)
    assert restored.stages.keys() == expected.stages.keys()
    assert restored.stages['parent_key'].children.keys() == {'child_key'}
    child = restored.stages['parent_key'].children['child_key']
    assert stored.stage_names == ('body',)  # Preserve the existing top-level publication declaration.
    assert child.detector_ran is False and child.bounding_boxes[0].x1 == 1.
    child.keypoints.xyz[:] = -777.
    np.testing.assert_array_equal(observation_arrays(stored[0]).coordinate_values, observation_arrays(expected).coordinate_values)
    with patch.object(Observation, '__init__', side_effect=AssertionError('No Tracker materialization')):
        buffered = ObservationBuffer(stored).to_keypoints_array(names=stored.point_names)
    assert buffered.shape == (3, 3, 3)
    assert buffered[0, 1, 2] == 17. and np.isnan(buffered[:, 2]).all()
    assert stored.coordinate_values[0, 2, 2] == 23.


def test_sparse_reordered_and_late_stages_preserve_missingness_and_box_counts():
    stored = series()
    stored.store(0, Observation(frame_number=0, image_size=stored.image_size))
    source = observation(1)
    source.stages['parent_key'].children['child_key'].bounding_boxes.append(BoundingBox(5., 6., 9., 10., .4))
    stored.store(1, source)
    reordered = observation(2)
    hand = reordered.stages['parent_key'].children['child_key']
    hand.keypoints = Keypoints(names=hand.keypoints.names[::-1], xyz=hand.keypoints.xyz[::-1], visibility=hand.keypoints.visibility[::-1])
    stored.store(2, reordered)
    assert stored.annotation_frame(0).stages == {}
    assert not ambiguous_instances(source)
    assert ambiguous_instances(stored[1]) == ambiguous_instances(source)
    assert not ambiguous_instances(stored[2])
    np.testing.assert_array_equal(stored.coordinate_values[1], stored.coordinate_values[2])
    values = ObservationBuffer(stored).to_keypoints_array(names=stored.point_names)
    assert np.isnan(values[0]).all()
    with pytest.raises(ValueError, match='missing'):
        ObservationBuffer(stored).to_stage_array('hand')
    with pytest.raises(ValueError, match='Duplicate'):
        stored.store(1, source)
    with pytest.raises(IndexError):
        stored.store(-1, source)


def test_missing_keypoints_are_distinct_from_missing_stage_and_empty_keypoints():
    stored = series()
    first = Observation(frame_number=0, image_size=stored.image_size, stages={'body': StageObservation(name='body')})
    second = Observation(frame_number=1, image_size=stored.image_size,
        stages={'body': StageObservation(name='body', keypoints=Keypoints.empty(()))})
    stored.store(0, first)
    stored.store(1, second)
    assert stored.annotation_frame(0).stages['body'].keypoints is None
    assert stored.annotation_frame(1).stages['body'].keypoints.names == ()
    with pytest.raises(ValueError, match='not been delivered'):
        stored[2]
    with pytest.raises(ValueError, match='not been delivered'):
        ObservationBuffer(stored).to_keypoints_array(names=())


def test_completion_restores_chronological_authored_order_independent_of_delivery():
    from freemocap.core.tracking.observation_arrays import recording_point_names
    first, second = series(2), series(2)
    def prediction(frame, name, value):
        return Observation(frame_number=frame, image_size=first.image_size, stages={'body': StageObservation(name='body',
            keypoints=Keypoints(names=(name,), xyz=np.array([[value, value + 1., value + 2.]]), visibility=np.ones(1)))})
    originals = [{'a': prediction(0, 'early_a', 10.), 'b': prediction(0, 'early_b', 20.)},
                 {'a': prediction(1, 'late_a', 30.), 'b': prediction(1, 'late_b', 40.)}]
    # Both camera streams deliver the later layout first.
    for frame in (1, 0):
        first.store(frame, originals[frame]['a'])
        second.store(frame, originals[frame]['b'])
        # Exercise cached annotation selections before layout growth/finalization.
        np.testing.assert_array_equal(first.annotation_frame(frame).stages['body'].keypoints.xyz,
                                      originals[frame]['a'].stages['body'].keypoints.xyz)
    frames = ObservationFrames({'a': first, 'b': second})
    frames.finalize()
    assert frames.point_names == recording_point_names(originals)
    assert frames.point_names == ('body.early_a', 'body.early_b', 'body.late_a', 'body.late_b')
    assert first.point_names == ('body.early_a', 'body.late_a')
    np.testing.assert_array_equal(first.coordinate_values[:, :, 0], [[10., np.nan], [np.nan, 30.]])
    assert first.annotation_frame(1).stages['body'].keypoints.names == ('late_a',)
    for frame in (0, 1):
        np.testing.assert_array_equal(first.annotation_frame(frame).stages['body'].keypoints.xyz,
                                      originals[frame]['a'].stages['body'].keypoints.xyz)
    coordinate_values = first.coordinate_values
    frames.finalize()
    assert first.coordinate_values is coordinate_values
    with pytest.raises(ValueError, match='Completed'):
        first.store(0, originals[0]['a'])


def test_root_instance_ambiguity_matches_original_and_restored_observations():
    stored = series(2)
    for frame in (0, 1):
        incoming = observation(frame)
        root = incoming.stages['parent_key']
        child = root.children['child_key']
        child.bounding_boxes.append(BoundingBox(5., 6., 9., 10., .4))
        if frame == 1:
            root.bounding_boxes = [BoundingBox(1., 2., 8., 9., .8), BoundingBox(5., 6., 9., 10., .4)]
        stored.store(frame, incoming)
        assert ambiguous_instances(incoming) is bool(frame)
        assert ambiguous_instances(stored[frame]) == ambiguous_instances(incoming)
        assert ambiguous_instances(stored.annotation_frame(frame)) == ambiguous_instances(incoming)


def test_stage_extraction_rejects_reordered_authored_stage_names():
    stored = series(2)
    first, second = observation(0), observation(1)
    points = second.stages['parent_key'].children['child_key'].keypoints
    second.stages['parent_key'].children['child_key'].keypoints = Keypoints(
        names=points.names[::-1], xyz=points.xyz[::-1], visibility=points.visibility[::-1])
    stored.store(0, first)
    stored.store(1, second)
    with pytest.raises(ValueError, match='order changed'):
        ObservationBuffer(stored).to_stage_array('hand')


def test_failed_admission_does_not_count_delivery_or_poison_retry():
    from freemocap.tests.test_dataflow_scientific_recording import ScientificRecordingTests
    fixture = ScientificRecordingTests()
    fixture.setUp()
    try:
        collection = ObservationCollection(sources=fixture.sources, execution_id='run')
        original = fixture.events[0]
        bad = deepcopy(original)
        bad.observation.stages['body'].keypoints.xyz = np.ones((2, 3))
        with pytest.raises(ValueError, match='declared names'):
            collection.accept(bad)
        assert not collection.frames.camera_series[original.frame_key.camera].delivered.any()
        collection.accept(original)
        with pytest.raises(ValueError, match='Duplicate'):
            collection.accept(original)
        foreign = replace(fixture.events[3], frame_key=replace(fixture.events[3].frame_key, execution='foreign'))
        with pytest.raises(ValueError, match='Foreign'):
            collection.accept(foreign)
        assert not collection.frames.camera_series[foreign.frame_key.camera].delivered[foreign.frame_key.frame]
        collection.accept(replace(fixture.outcomes[0], outcome=ProducerOutcome.FAILED))
        with pytest.raises(ValueError, match='terminal'):
            collection.accept(fixture.events[3])
        assert not collection.frames.camera_series[foreign.frame_key.camera].delivered[foreign.frame_key.frame]
        with pytest.raises(ValueError, match='complete successful'):
            collection.require_complete()
    finally:
        fixture.doCleanups()


def test_fresh_box_and_point_publication_matches_original_tracker_objects():
    from freemocap.core.recording.sample_encoding.observation_samples import TimedObservation, box_batches, observation_batches
    from freemocap.core.recording.data_descriptors.recording_descriptor import Channel
    from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
    from freemocap.core.types.channel_kind import ChannelKind
    stored = series()
    sources = [observation(i) for i in range(3)]
    for i, source in enumerate(sources):
        stored.store(i, source)
    for kind, names, components, convert in (
        (ChannelKind.OVERLAY_2D, stored.point_names, {'x': 'px', 'y': 'px', 'visibility': '1'}, observation_batches),
        (ChannelKind.BOXES_2D, ('body', 'hand'), {'x1': 'px', 'y1': 'px', 'x2': 'px', 'y2': 'px', 'confidence': '1', 'detector_ran': '1'}, box_batches),
    ):
        channel = Channel(kind=kind, stage=ProcessingStage.OBSERVATIONS, sensor_group='cameras', source='tracker',
            reference_frame='camera:image', names=names, components=components)
        def publish(values):
            return pa.Table.from_batches(list(convert(samples=[TimedObservation(value, index / 30) for index, value in enumerate(values)],
                channel=channel, run_id=0, batch_size=1024)))
        with patch.object(Observation, '__init__', side_effect=AssertionError('No Tracker reconstruction during publication')):
            actual = publish(stored)
        assert actual.equals(publish(sources))
