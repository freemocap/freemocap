"""Re-admit the accepted reference predictions through fresh recording storage."""
import json
import os
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from skellytracker.core.data_primitives.observation import Observation

from freemocap.core.pipeline.dataflow.camera_join import CameraFrameKey, ProducerOutcome
from freemocap.core.pipeline.dataflow.tracker_adapter import TrackedCameraFrame
from freemocap.core.pipeline.dataflow.video_sources import VideoSourceFinished
from freemocap.core.pipeline.dataflow.saved_observation_source import load_saved_observation_source
from freemocap.core.pipeline.dataflow.scientific_recording import ObservationCollection
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.tracking.observation_buffer import recording_observation_buffers
from freemocap.core.recording.parquet_storage.recording_view import recording_view
from freemocap.core.reconstruction.posthoc_reconstruction import triangulate_observation_buffers
from freemocap.core.reconstruction.posthoc_timing import PosthocTimingReport
from freemocap.core.tasks.triangulation.helpers.triangulation_config import TriangulationConfig
from freemocap.tools.datasets.catalog import TEST_DATA
from freemocap.tools.datasets.preparation import file_digest
from freemocap.tests.reference_paths import prepared_root


@pytest.fixture(scope='module')
def reference_predictions():
    if not os.environ.get('FREEMOCAP_PROVENANCE_PREPARED_ROOT'):
        pytest.skip('Set the prepared reference-data root')
    root = prepared_root() / TEST_DATA.name
    recording = Path(json.loads((root / 'ready.json').read_text(encoding='utf-8'))['recording'])
    assert recording.resolve().is_relative_to((root / 'current').resolve())
    parquet = recording / f'{recording.name}_data.parquet'
    original_digest = file_digest(parquet)
    sources, saved, _ = load_saved_observation_source(path=str(recording),
        config=PosthocMocapPipelineConfig(start_stage='triangulation', export_to_blender=False))
    assert saved.frame_count == 222 and len(saved.cameras) == 3
    events = [TrackedCameraFrame(CameraFrameKey('tensor-retention', sources.sensor_group, camera, index),
        float(series.timestamps_s[index]), series.annotation_frame(index))
        for index in range(saved.frame_count) for camera, series in saved.frames.camera_series.items()]
    fresh = ObservationCollection(sources=sources, execution_id='tensor-retention')
    for event in events:
        fresh.accept(event)
    for camera in fresh.cameras:
        fresh.accept(VideoSourceFinished(execution_id='tensor-retention', sensor_group=sources.sensor_group,
            camera_id=camera, outcome=ProducerOutcome.SUCCEEDED, loaded_frames=fresh.frame_count, error_message=None))
    fresh.require_complete()
    yield parquet, sources, saved, fresh, events
    assert file_digest(parquet) == original_digest


def test_every_reference_prediction_and_timing_survives_fresh_tensor_retention(reference_predictions):
    _, sources, saved, fresh, _ = reference_predictions
    saved_buffers = recording_observation_buffers(saved.frames, saved.cameras)
    with patch.object(Observation, '__init__', side_effect=AssertionError('No Tracker reconstruction in tensor consumers')):
        buffers = recording_observation_buffers(fresh.frames, fresh.cameras)
        for camera in fresh.cameras:
            series = fresh.frames.camera_series[camera]
            assert len(series.layouts) == 1 and not buffers[camera].observations
            assert buffers[camera].frame_numbers == saved_buffers[camera].frame_numbers
            np.testing.assert_array_equal(buffers[camera].to_keypoints_array(names=series.point_names),
                saved_buffers[camera].to_keypoints_array(names=series.point_names))
            np.testing.assert_array_equal(series.confidence_values, saved.frames.camera_series[camera].confidence_scores())
            np.testing.assert_array_equal(series.timestamps_s, saved.frames.camera_series[camera].timestamps_s)
    assert fresh.join is not None and saved.join is None


def test_reference_fresh_and_saved_triangulation_are_numerically_identical(reference_predictions):
    parquet, sources, saved, fresh, _ = reference_predictions
    with recording_view(parquet) as view:
        geometry = {camera.id: camera for camera in view.metadata.runs[view.metadata.selected_run_id].camera_geometry[sources.sensor_group]}
    def triangulate(collection):
        return triangulate_observation_buffers(observation_buffers=recording_observation_buffers(collection.frames, collection.cameras),
            camera_geometry=geometry, triangulation_config=TriangulationConfig(), max_reprojection_error_px=None,
            timing=PosthocTimingReport())
    with patch.object(Observation, '__init__', side_effect=AssertionError('No Tracker reconstruction before triangulation')):
        expected, actual = triangulate(saved), triangulate(fresh)
    assert expected.keypoint_names == actual.keypoint_names and expected.sources == actual.sources
    for name in ('points_3d', 'per_camera_weights', 'reprojection_error'):
        np.testing.assert_array_equal(getattr(actual.reconstruction, name), getattr(expected.reconstruction, name))
    for name in ('errors', 'observed', 'reconstructed', 'weights'):
        np.testing.assert_array_equal(getattr(actual.reconstruction.diagnostics, name), getattr(expected.reconstruction.diagnostics, name))
