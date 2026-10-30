"""Dense observation publication retains exact semantics and columnar validation."""
from dataclasses import replace
from unittest.mock import patch

import numpy as np
import pyarrow as pa
import pytest
from skellytracker.core.data_primitives.observation import Observation, StageObservation
from skellytracker.core.data_primitives.bounding_box import BoundingBox
from skellytracker.core.data_primitives.keypoints import Keypoints
from skellycam.core.recorders.videos.recording_info import RecordingInfo

from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata
from freemocap.core.recording.data_descriptors.recording_descriptor import Channel, RecordingMetadata, RunDescriptor, SensorGroup, Source
from freemocap.core.recording.sample_encoding.arrow_schema import SampleValidator
from freemocap.core.recording.sample_encoding.channel_series import SeriesSampling
from freemocap.core.recording.sample_encoding.observation_samples import TimedObservation, box_batches, box_series_batches, timing_batches, timing_series_batches
from freemocap.core.tracking.observation_series import RecordingObservationSeries, ObservationFrames
from freemocap.core.recording.result_processing.observation_inputs import ObservationGroup, ObservationRecordingRequest, TrackerRecordingDefinition, DetectorRecordingDefinition
from freemocap.core.recording.result_processing.observation_publication import publish_posthoc_observations


def channels():
    boxes = Channel(kind='BOXES_2D', stage=ProcessingStage.OBSERVATIONS, sensor_group='cameras', source='detector',
        reference_frame='camera:image', names=('body', 'hand'),
        components={'detector_ran': '1', 'confidence': '1', 'y2': 'px', 'x2': 'px', 'y1': 'px', 'x1': 'px'})
    timing = Channel(kind='TIMESTAMPS', stage=ProcessingStage.TIMING, sensor_group='cameras', source='clock',
        reference_frame=None, names=('capture',), components={'timestamp_s': 's'})
    return boxes, timing


def observations(count=5):
    return [Observation(frame_number=i, image_size=(48, 64), stages={
        'body': StageObservation(name='body', detector_ran=i % 2 == 0,
            keypoints=Keypoints(names=('wrist',), xyz=np.array([[1., 2., 9.]]), visibility=np.ones(1)),
            bounding_boxes=[BoundingBox(1., 2., 10., 20., .9)] if i % 3 else [],
            children={'hand': StageObservation(name='hand', bounding_boxes=[BoundingBox(np.nan, 3., 5., 8., .7)])})})
        for i in range(count)]


def series_for(items):
    series = RecordingObservationSeries(camera_id='camera', image_size=(48, 64),
        frame_numbers=tuple(item.frame_number for item in items), timestamps_s=tuple(i / 30 for i in range(len(items))))
    for i, item in enumerate(items):
        series.store(i, item)
    series.finalize()
    return series


def metadata_for(boxes, timing, count):
    return RecordingMetadata(recording_id='columnar', selected_run_id=0, runs={0: RunDescriptor(
        sensor_groups={'cameras': SensorGroup(clock_description='capture', sample_count=count)},
        sources={'detector': Source(kind='tracker', definition={}), 'clock': Source(kind='timing', definition={})},
        reference_frames={'camera:image': {}}, models={}, processing={}, channels=(boxes, timing))})


def test_dense_boxes_and_clocks_match_native_adapter_and_use_only_columnar_validation():
    boxes, timing = channels()
    items = observations()
    series = series_for(items)
    sampling = SeriesSampling(frame_numbers=series.frame_numbers, timestamps_s=tuple(series.timestamps_s), run_id=0, batch_size=13)
    actual_boxes = list(box_series_batches(series=series, sampling=sampling, channel=boxes))
    native_boxes = list(box_batches(samples=(TimedObservation(item, i / 30) for i, item in enumerate(items)),
        channel=boxes, run_id=0, batch_size=13))
    assert pa.Table.from_batches(actual_boxes).equals(pa.Table.from_batches(native_boxes))
    assert all(batch.num_rows % 12 == 0 for batch in actual_boxes)
    direct_times = list(timing_series_batches(sampling=sampling, channel=timing))
    iterable_times = list(timing_batches(samples=zip(series.frame_numbers, series.timestamps_s), channel=timing, run_id=0, batch_size=2))
    assert pa.Table.from_batches(direct_times).equals(pa.Table.from_batches(iterable_times))
    validator = SampleValidator(metadata=metadata_for(boxes, timing, len(items)))
    with patch.object(SampleValidator, '_accept_rows', side_effect=AssertionError('Ordinary publication must validate columns')):
        for batch in (*actual_boxes, *direct_times):
            validator.accept(batch=batch)
        validator.finish()
    assert validator.scalar_rows == 0 and validator.columnar_rows == len(items) * 13
    # Missing box keeps every component null, including detector provenance.
    values = pa.Table.from_batches(actual_boxes)['value'].to_numpy().reshape(len(items), 2, 6)
    assert np.isnan(values[0, 0]).all()
    assert values[1, 0, 0] == 0 and values[2, 0, 0] == 1


def test_duplicate_stage_name_precedence_matches_tracker_tree_traversal():
    boxes, _ = channels()
    item = Observation(frame_number=0, image_size=(48, 64), stages={
        'first': StageObservation(name='body', bounding_boxes=[BoundingBox(1, 2, 3, 4, .1)], children={
            'child1': StageObservation(name='body', bounding_boxes=[BoundingBox(5, 6, 7, 8, .2)]),
            'child2': StageObservation(name='body', detector_ran=True, bounding_boxes=[BoundingBox(9, 10, 11, 12, .3)])}),
        'second': StageObservation(name='body', bounding_boxes=[BoundingBox(13, 14, 15, 16, .4)])})
    series = series_for([item])
    sampling = SeriesSampling(frame_numbers=(0,), timestamps_s=(0.,), run_id=0, batch_size=1)
    actual = pa.Table.from_batches(list(box_series_batches(series=series, sampling=sampling, channel=boxes)))
    native = pa.Table.from_batches(list(box_batches(samples=[TimedObservation(item, 0.)], channel=boxes, run_id=0, batch_size=1)))
    assert actual.equals(native)
    assert actual['value'].to_pylist()[:6] == [1., .2, 8., 7., 6., 5.]


@pytest.mark.parametrize('corruption', ['duplicate', 'missing', 'units', 'infinite', 'timestamps'])
def test_columnar_validation_still_rejects_malformed_publication(corruption):
    boxes, timing = channels()
    series = series_for(observations(2))
    sampling = SeriesSampling(frame_numbers=(0, 1), timestamps_s=(0., 1 / 30), run_id=0)
    batch = next(box_series_batches(series=series, sampling=sampling, channel=boxes))
    if corruption == 'duplicate':
        batch = batch.take(pa.array([*range(batch.num_rows - 1), 0]))
    elif corruption == 'missing':
        batch = batch.slice(0, batch.num_rows - 1)
    else:
        name, replacement = {'units': ('units', 'wrong'), 'infinite': ('value', float('inf')),
                             'timestamps': ('timestamp_s', .001)}[corruption]
        values = batch.column(name).to_pylist()
        values[0] = replacement
        field = batch.schema.field(name)
        batch = batch.set_column(batch.schema.get_field_index(name), field, pa.array(values, type=field.type))
    validator = SampleValidator(metadata=metadata_for(boxes, timing, 2))
    with pytest.raises(ValueError):
        validator.accept(batch=batch)
        for clock in timing_series_batches(sampling=sampling, channel=timing):
            validator.accept(batch=clock)
        validator.finish()


def test_fresh_overwrite_and_retained_publication_never_fall_back_to_scalar_validation(tmp_path):
    items = observations(222)
    series = series_for(items)
    frames = ObservationFrames({'camera': series})
    frames.finalize()
    video = VideoMetadata(file_path=tmp_path / 'camera.mp4', width=64, height=48, fps=30., frame_count=len(items),
        end_frame=len(items), fourcc='mp4v', duration_seconds=len(items) / 30)
    request = ObservationRecordingRequest(recording=RecordingInfo(recording_name='columnar', recording_directory=str(tmp_path)),
        group=ObservationGroup(name='cameras', frames=frames, videos={'camera': video}),
        tracker=TrackerRecordingDefinition(name='keypoint_model:test', point_names=('body.wrist',), configuration={}),
        detector=DetectorRecordingDefinition(name='object_detector:test', box_names=('body', 'hand'), configuration={}),
        reprojection=None, filtering=None, models=(), reconstructions=(), spatial_series=(), camera_geometry=())
    with patch.object(SampleValidator, '_accept_rows', side_effect=AssertionError('Ordinary publication must validate columns')), \
         patch.object(BoundingBox, '__init__', side_effect=AssertionError('No box objects during dense publication')):
        first = publish_posthoc_observations(request)
        overwritten = publish_posthoc_observations(request)
        retained = publish_posthoc_observations(replace(request, reuse_observations=True))
    assert set(first.runs) == set(overwritten.runs) == set(retained.runs) == {0}
