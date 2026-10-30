"""Saved image predictions retain tensors through the actual scientific consumers."""
from dataclasses import replace
from unittest.mock import patch

import numpy as np
import pytest
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.timestamps.recording_timing_reader import RecordingTiming, TimingMethod
from skellytracker.core.data_primitives.observation import Observation, StageObservation

from freemocap.core.pipeline.dataflow.saved_observation_source import load_saved_observation_source
from freemocap.core.pipeline.dataflow.scientific_recording import triangulate_completed_observations
from freemocap.core.reconstruction.recording_timing import RecordingGroupTiming
from freemocap.core.reconstruction.posthoc_reconstruction import triangulate_observation_buffers
from freemocap.core.reconstruction.posthoc_timing import PosthocTimingReport
from freemocap.core.recording.result_processing.observation_inputs import (
    ObservationGroup, ObservationRecordingRequest, TrackerRecordingDefinition,
)
from freemocap.core.recording.result_processing.observation_publication import publish_posthoc_observations
from freemocap.core.recording.result_processing.saved_observations import read_saved_observations
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.tasks.triangulation.helpers.triangulation_config import TriangulationConfig
from freemocap.core.tracking.observation_arrays import observation_arrays, recording_point_names
from freemocap.core.tracking.observation_buffer import recording_observation_buffers
from freemocap.core.tracking.observation_series import ObservationFrames
from freemocap.system.recording_structure.recording_structure import RecordingStructure
from freemocap.tests.calibration.test_posthoc_matching import recorded_request


@pytest.fixture
def saved_predictions(tmp_path):
    original = recorded_request()
    # Nonzero IDs, gaps and camera clock offsets must survive both saved adapters.
    frame_ids = tuple(7 + 3 * i for i in range(len(original.frames)))
    times = tuple(.2 + i * .037 for i in range(len(frame_ids)))
    for index, frame in enumerate(original.frames):
        for camera_index, observation in enumerate(frame.values()):
            observation.frame_number = frame_ids[index]
            points = observation.stages['subject'].keypoints
            # Confidence policy includes zero confidence, missing xy, and valid xy with low visibility.
            if index in (2, 4, 8):
                points.visibility[index % len(points.names)] = (0., .4, .1)[(2, 4, 8).index(index)]
                if index == 4:
                    points.xyz[index % len(points.names), :2] = np.nan
    videos = {camera: video.model_copy(update=dict(start_frame=frame_ids[0], end_frame=frame_ids[-1] + 1,
                             frame_count=frame_ids[-1] + 1)) for camera, video in original.videos.items()}
    original = replace(original, videos=videos)
    timing = RecordingGroupTiming(cameras={camera: RecordingTiming(
        tuple(t + camera_index * .001 for t in times), TimingMethod.INFERRED_FROM_FPS)
        for camera_index, camera in enumerate(videos)}, synchronized=RecordingTiming(times, TimingMethod.INFERRED_FROM_FPS))
    config = PosthocMocapPipelineConfig(detector_type='mediapipe', charuco_tracking_enabled=False,
        start_stage='triangulation', sensor_group='saved-cameras', export_to_blender=False)
    info = RecordingInfo(recording_name='saved', recording_directory=str(tmp_path))
    tracker = TrackerRecordingDefinition(name='keypoint_model:test',
        point_names=recording_point_names(original.frames), configuration=config.model_dump(mode='json'))
    request = ObservationRecordingRequest(recording=info,
        group=ObservationGroup(name='saved-cameras', frames=original.frames, videos=videos),
        tracker=tracker, models=(), reconstructions=(), spatial_series=(), filtering=None,
        reprojection=None, camera_geometry=(), resolved_timing=timing)
    publish_posthoc_observations(request)
    structure = RecordingStructure(base_directory=tmp_path, recording_name='saved')
    return original, structure, config, tracker, timing


def test_saved_predictions_share_one_view_and_keep_declared_axes(saved_predictions):
    original, structure, config, _, timing = saved_predictions
    from freemocap.core.recording.result_processing import saved_observations as reader
    with patch.object(reader, 'recording_view', wraps=reader.recording_view) as opened, \
         patch.object(Observation, '__init__', side_effect=AssertionError('No Tracker objects on saved reads')), \
         patch.object(StageObservation, '__init__', side_effect=AssertionError('No Tracker stages on saved reads')):
        saved = read_saved_observations(structure=structure, run_id=0, sensor_group=config.sensor_group)
    assert opened.call_count == 1
    assert isinstance(saved.frames, ObservationFrames)
    assert saved.frames.frame_numbers == tuple(frame[next(iter(original.videos))].frame_number for frame in original.frames)
    assert saved.timing == timing
    for camera, series in saved.frames.camera_series.items():
        arrays = series.channel_arrays
        assert saved.frames[np.int64(1)][camera].sample_index == 1
        with pytest.raises(TypeError):
            series[1.5]
        assert arrays.components == ('x', 'y', 'visibility')
        assert arrays.names == recording_point_names(original.frames)
        assert series.time_series.data_tensor.data_values is arrays.values
        assert series.time_series.sample_timing.source_identity.camera_id == camera
        np.testing.assert_array_equal(series.time_series.sample_timing.sample_ids, arrays.frames)
        assert not arrays.values.flags.writeable and not arrays.present.flags.writeable
        assert arrays.present.all()
        for index, frame in enumerate(original.frames):
            expected = observation_arrays(frame[camera])
            np.testing.assert_array_equal(arrays.values[index, :, :2], expected.image_coordinates)
            np.testing.assert_array_equal(arrays.values[index, :, 2], expected.confidence_scores)
            assert saved.frames[index][camera].timestamp == timing.cameras[camera].timestamps_s[index]


def test_saved_matching_triangulation_and_integrity_without_tracker_materialization(saved_predictions):
    original, structure, config, tracker, _ = saved_predictions
    matching = original.evaluate()
    geometry = original.resolve(result=matching)
    expected = triangulate_observation_buffers(
        observation_buffers=recording_observation_buffers(original.frames, tuple(original.videos)),
        camera_geometry=geometry, triangulation_config=TriangulationConfig(), max_reprojection_error_px=None,
        timing=PosthocTimingReport())
    with patch.object(Observation, '__init__', side_effect=AssertionError('No Tracker object reconstruction')), \
         patch.object(StageObservation, '__init__', side_effect=AssertionError('No Tracker stage reconstruction')):
        sources, collection, effective = load_saved_observation_source(path=str(structure.full_path), config=config)
        assert collection.join is None
        assert collection.frame_count == len(original.frames)
        assert sources.saved_frame_numbers == collection.frames.frame_numbers
        buffers = recording_observation_buffers(collection.frames, collection.cameras)
        assert all(not buffer.observations for buffer in buffers.values())
        actual = triangulate_completed_observations(collection=collection, calibration_cameras=original.cameras,
            matching_config=original.config, triangulation_config=TriangulationConfig())
    assert actual.matching_result.assignment == matching.assignment
    assert actual.matching_result.status == matching.status
    assert actual.triangulation.diagnostic_point_names == expected.diagnostic_point_names
    for name in ('points_3d', 'per_camera_weights', 'reprojection_error'):
        np.testing.assert_allclose(getattr(actual.triangulation.reconstruction, name),
                                   getattr(expected.reconstruction, name), rtol=0., atol=0., equal_nan=True)
    camera = collection.cameras[0]
    source_values = collection.frames.camera_series[camera].channel_arrays.values
    completed_values = actual.observations.frames.camera_series[camera].channel_arrays.values
    assert not np.shares_memory(source_values, completed_values)
    source_values.flags.writeable = True
    source_values[0, 0, 0] += 8
    assert actual._payload_digest() == actual._integrity_digest
    # Completed payload still detects deliberate mutation, including numerical buffers.
    completed_values.flags.writeable = True
    completed_values[0, 0, 0] += 3
    with pytest.raises(ValueError, match='payload changed'):
        actual.save(recording_info=RecordingInfo(recording_name='saved', recording_directory=str(structure.base_directory)),
                    tracker_definition=tracker)


def test_annotation_adapts_only_requested_frame(saved_predictions):
    _, structure, config, _, _ = saved_predictions
    saved = read_saved_observations(structure=structure, run_id=0, sensor_group=config.sensor_group)
    series = next(iter(saved.frames.camera_series.values()))
    adapted = series.annotation_frame(5)
    assert isinstance(adapted, Observation)
    assert adapted.frame_number == series.frame_numbers[5]
    np.testing.assert_array_equal(observation_arrays(adapted).coordinate_values, series.tracker_coordinates(5))
    adapted.stages['subject'].keypoints.xyz[0, 0] += 5
    assert not np.shares_memory(adapted.stages['subject'].keypoints.xyz, series.channel_arrays.values)


def test_dense_declared_component_order_stage_selection_and_confidence_policy():
    from freemocap.core.recording.parquet_storage.channel_arrays import ChannelArrays
    from freemocap.core.recording.parquet_storage.channel_selection import ChannelSelection
    from freemocap.core.tracking.observation_series import ObservationSeries
    from freemocap.core.tracking.observation_buffer import ObservationBuffer
    from freemocap.core.types.channel_kind import ChannelKind

    frame_count, point_count = 513, 97
    # Extra authored components remain available; numerical consumers select x/y
    # by name rather than treating the stored final dimension as Tracker XYZ.
    names = tuple(f'{"zeta" if i < 47 else "alpha"}.p{point_count-i}' for i in range(point_count))
    values = np.random.default_rng(128).uniform(size=(frame_count, point_count, 4))
    values[17, 3, 2] = 0.
    values[80, 4, 2] = np.nan
    values[510, 8, 3] = np.nan
    present = np.ones(values.shape, dtype=bool)
    present[510, 8, 3] = False
    values.flags.writeable = False
    present.flags.writeable = False
    arrays = ChannelArrays(ChannelSelection(sensor_group='group', source='tracker',
        reference_frame='camera:one:image', channel=ChannelKind.OVERLAY_2D), names,
        ('uncertainty', 'y', 'visibility', 'x'), ('1', 'px', '1', 'px'),
        np.arange(frame_count) * 2 + 5, np.arange(frame_count) * .037 + .002, values, present)
    series = ObservationSeries(camera_id='one', image_size=(720, 1280), channel_arrays=arrays)
    buffer = ObservationBuffer(series)
    target_names = (*names[::-1], 'extra.unobserved')
    expected = np.zeros((frame_count, point_count, 3))
    expected[..., 0], expected[..., 1] = values[..., 3], values[..., 1]
    confidence = values[..., 2]
    expected[~np.isfinite(confidence) | (confidence <= 0)] = np.nan
    with patch.object(Observation, '__init__', side_effect=AssertionError('No dense Tracker reconstruction')):
        actual = buffer.to_keypoints_array(names=target_names)
        np.testing.assert_array_equal(actual[:, :-1], expected[:, ::-1])
        assert np.isnan(actual[:, -1]).all()
        np.testing.assert_array_equal(buffer.to_stage_array('alpha', 4), expected[:, 47:51])
    assert series.stage_names == ('zeta', 'alpha')
    assert buffer.stage_point_names('alpha') == tuple(name.partition('.')[2] for name in names[47:])
    assert series.channel_arrays.values is values
    assert series.time_series.data_tensor.data_values.shape[-1] == 4
    assert series.channel_arrays.present is present
    projected = series.tracker_coordinates()
    with patch.object(ObservationSeries, 'tracker_coordinates', return_value=projected) as projection:
        identity = buffer.to_keypoints_array(names=names)
        assert identity is projected  # No identity gather or second full XYZ allocation.
        projection.assert_called_once_with()
    np.testing.assert_array_equal(identity, expected)
    with patch.object(ObservationSeries, 'tracker_coordinates', wraps=series.tracker_coordinates) as projection:
        buffer.to_stage_array('alpha', 4)
        projection.assert_called_once_with(point_indices=[47, 48, 49, 50])
    assert not values.flags.writeable
    assert values[17, 3, 2] == 0.
    with pytest.raises(ValueError, match='exceeds'):
        buffer.to_stage_array('alpha', 100)
    with pytest.raises(ValueError, match='Missing'):
        buffer.to_stage_array('missing')


def test_saved_admission_checks_source_timing_and_frame_identity(saved_predictions):
    from freemocap.core.pipeline.dataflow.scientific_recording import ObservationCollection
    from freemocap.core.recording.result_processing import saved_observations as reader
    _, structure, config, _, _ = saved_predictions
    with patch.object(reader, 'recording_view', wraps=reader.recording_view) as opened:
        sources, collection, _ = load_saved_observation_source(path=str(structure.full_path), config=config)
    assert opened.call_count == 1
    first = sources.camera_sources[0]
    wrong_timing = replace(first, camera_timing=RecordingTiming(
        tuple(t + .1 for t in first.camera_timing.timestamps_s), first.camera_timing.method))
    with pytest.raises(ValueError, match='timing'):
        ObservationCollection.from_saved(sources=replace(sources,
            camera_sources=(wrong_timing, *sources.camera_sources[1:])), frames=collection.frames)
    frame_ids = list(sources.saved_frame_numbers)
    frame_ids[2] += 1
    with pytest.raises(ValueError, match='frame IDs'):
        ObservationCollection.from_saved(sources=replace(sources, saved_frame_numbers=tuple(frame_ids)), frames=collection.frames)
