"""Resume actual canonical recordings without media access or upstream computation."""

from concurrent.futures import CancelledError
from types import SimpleNamespace
from unittest.mock import Mock
from pathlib import Path
import shutil
from freemocap.core.pipeline.performance_report import PerformanceReport

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from freemocap.core.pipeline.posthoc import saved_stage_processing as processing
from freemocap.core.pipeline.posthoc.task_progress_reporter import TaskProgressReporter
from freemocap.core.reconstruction.posthoc_filtering import PosthocFilterConfig
from freemocap.core.recording.parquet_storage.parquet_reader import read_batches, read_metadata
from freemocap.core.recording.result_processing.saved_reconstruction import read_saved_channel
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.types.channel_kind import ChannelKind
from freemocap.tests.test_saved_reconstruction import saved_request


def rows(request):
    return pa.Table.from_batches(list(read_batches(path=request.structure.data_parquet_path,
        run_id=request.run_id, sensor_groups=(request.sensor_group,)))).to_pylist()


def test_filter_then_reconstruct_preserves_raw_and_timing(saved_request, monkeypatch):
    before = rows(saved_request)
    config = PosthocMocapPipelineConfig(start_stage='filtering', base_run_id=3,
        sensor_group='mocap', skeleton_fit_enabled=False)
    processing.run_saved_numerical_stages(structure=saved_request.structure, config=config,
        reporter=TaskProgressReporter.noop())
    after = rows(saved_request)
    assert [row for row in after if row['channel'] == 'RAW_KEYPOINTS_3D'] == before
    metadata = read_metadata(path=saved_request.structure.data_parquet_path)
    channel = next(c for c in metadata.runs[3].channels if c.kind == ChannelKind.KEYPOINTS_3D)
    points = read_saved_channel(structure=saved_request.structure, run_id=3, metadata=metadata, channel=channel)
    assert points.frames == (10, 11)
    assert points.timestamps_s == (1.0, 1.07)
    assert np.isnan(points.values).all()
    fits = metadata.runs[3].scale_fits
    monkeypatch.setattr(processing, 'prepare_recording_points', Mock(side_effect=AssertionError('Filtering must be reused')))
    processing.run_saved_numerical_stages(structure=saved_request.structure,
        config=config.model_copy(update={'start_stage': 'scale_fit'}), reporter=TaskProgressReporter.noop())
    assert read_metadata(path=saved_request.structure.data_parquet_path).runs[3].scale_fits == fits
    monkeypatch.setattr(processing, 'reconstruct_skeletons_for_recording', Mock(side_effect=AssertionError('Scale must be reused')))
    processing.run_saved_numerical_stages(structure=saved_request.structure,
        config=config.model_copy(update={'start_stage': 'reconstruction'}), reporter=TaskProgressReporter.noop())
    assert read_metadata(path=saved_request.structure.data_parquet_path).runs[3].scale_fits == fits
    assert [row for row in rows(saved_request) if row['channel'] == 'RAW_KEYPOINTS_3D'] == before


def test_cancelled_resume_preserves_previous_file(saved_request):
    before = saved_request.structure.data_parquet_path.read_bytes()
    with pytest.raises(CancelledError):
        processing.run_saved_numerical_stages(structure=saved_request.structure,
            config=PosthocMocapPipelineConfig(start_stage='filtering', base_run_id=3),
            reporter=TaskProgressReporter.noop(), cancelled=lambda: True)
    assert saved_request.structure.data_parquet_path.read_bytes() == before


def test_missing_input_does_not_fall_back_to_tracking(saved_request):
    before = saved_request.structure.data_parquet_path.read_bytes()
    with pytest.raises(ValueError, match='KEYPOINTS_3D'):
        processing.run_saved_numerical_stages(structure=saved_request.structure,
            config=PosthocMocapPipelineConfig(start_stage='reconstruction', base_run_id=3),
            reporter=TaskProgressReporter.noop())
    assert saved_request.structure.data_parquet_path.read_bytes() == before


def test_saved_worker_never_starts_detection(monkeypatch, tmp_path):
    from freemocap.core.pipeline.posthoc import mocap_pipeline
    from skellycam.core.recorders.videos.recording_info import RecordingInfo
    worker = Mock()
    monkeypatch.setattr(processing, 'run_saved_numerical_stages', worker)
    detector = Mock(side_effect=AssertionError('Saved processing must not open videos or detectors'))
    monkeypatch.setattr(mocap_pipeline, 'detect_mocap_recording', detector)
    request = Mock(spec=mocap_pipeline.MocapWorkerRequest, config=PosthocMocapPipelineConfig(start_stage='filtering'),
        recording=RecordingInfo(recording_name='recording', recording_directory=str(tmp_path)),
        ipc=SimpleNamespace(should_continue=True), report=Mock())
    mocap_pipeline.run_mocap_pipeline(request=request)
    worker.assert_called_once()
    detector.assert_not_called()


def test_completed_tracking_and_triangulation_survive_reconstruction_failure(tmp_path, monkeypatch):
    from freemocap.core.tasks.mocap import posthoc_mocap_task as task
    from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata
    from freemocap.core.recording.result_processing.saved_observations import read_saved_observations
    from freemocap.core.recording.result_processing.observation_inputs import camera_group_name
    from skellycam.core.recorders.videos.recording_info import RecordingInfo
    from skellytracker.core.data_primitives.observation import Observation, StageObservation
    from skellytracker.core.data_primitives.keypoints import Keypoints
    info = RecordingInfo(recording_name='recording', recording_directory=str(tmp_path))
    frames = [{'cam': Observation(frame_number=index, image_size=(48, 64), stages={
        'body': StageObservation(name='body', keypoints=Keypoints(names=('left_wrist',),
            xyz=np.array([[10. + index, 20., 0.]]), visibility=np.ones(1)))})} for index in range(3)]
    video = VideoMetadata(file_path=tmp_path / 'missing.mp4', width=64, height=48, fps=30.,
        frame_count=3, end_frame=3, fourcc='mp4v', duration_seconds=.1)
    reconstruct = task.reconstruct_skeletons_for_recording
    monkeypatch.setattr(task, 'reconstruct_skeletons_for_recording', Mock(side_effect=RuntimeError('test reconstruction failure')))
    with pytest.raises(RuntimeError, match='test reconstruction failure'):
        task.run_posthoc_mocap_task(frame_observations=frames, recording_info=info,
            video_metadata={'cam': video}, task_config=PosthocMocapPipelineConfig(
                detector_type='mediapipe', charuco_tracking_enabled=False), selected_board=None)
    inventory = processing.inspect_saved_stages(str(info.full_recording_path))
    stages = inventory['runs'][0]['groups'][0]['stages']
    assert stages['observations'] and stages['triangulation']
    assert not stages['reconstruction']
    structure = processing.recording_structure(str(info.full_recording_path))
    saved = read_saved_observations(structure=structure, run_id=0, sensor_group=camera_group_name(['cam']))
    for original, restored in zip(frames, saved.frames, strict=True):
        np.testing.assert_array_equal(original['cam'].to_keypoints().xyz[:, :2], restored['cam'].to_keypoints().xyz[:, :2])
    assert saved.timing.synchronized.timestamps_s == (0., 1 / 30, 2 / 30)
    # Resume through the actual worker, with detector startup forbidden and no video file.
    from freemocap.core.pipeline.posthoc import mocap_pipeline
    monkeypatch.setattr(task, 'reconstruct_skeletons_for_recording', reconstruct)
    monkeypatch.setattr(mocap_pipeline, 'detect_mocap_recording', Mock(side_effect=AssertionError('No detection on resume')))
    before = pa.Table.from_batches(list(read_batches(path=structure.data_parquet_path, run_id=0,
        sensor_groups=(camera_group_name(['cam']),)))).to_pylist()
    worker = Mock(spec=mocap_pipeline.MocapWorkerRequest,
        config=PosthocMocapPipelineConfig(start_stage='triangulation', detector_type='rtmpose'),
        recording=info, ipc=SimpleNamespace(should_continue=True), report=Mock(), performance=PerformanceReport(), pipeline_id="test-resume")
    mocap_pipeline.run_mocap_pipeline(request=worker)
    after = pa.Table.from_batches(list(read_batches(path=structure.data_parquet_path, run_id=0,
        sensor_groups=(camera_group_name(['cam']),)))).to_pylist()
    retained_kinds = {'OVERLAY_2D', 'TIMESTAMPS'}
    assert [r for r in after if r['channel'] in retained_kinds] == [r for r in before if r['channel'] in retained_kinds]
    assert processing.inspect_saved_stages(str(info.full_recording_path))['runs'][0]['groups'][0]['stages']['reconstruction']


@pytest.mark.e2e
def test_real_recording_filter_and_reconstruct_without_media(tmp_path):
    name = 'freemocap_test_data'
    source = Path.home() / 'freemocap_data/testing/prepared' / name / 'current/recordings' / name / f'{name}_data.parquet'
    if not source.is_file():
        pytest.skip('Prepare freemocap_test_data through the production pipeline first')
    structure = processing.recording_structure(str(tmp_path / name))
    structure.full_path.mkdir()
    shutil.copy2(source, structure.data_parquet_path)
    metadata = read_metadata(path=structure.data_parquet_path)
    run_id = metadata.selected_run_id
    group = processing.select_group(metadata.runs[run_id], None)
    filters = [('run_id', '=', run_id), ('sensor_group', '=', group), ('channel', '=', 'RAW_KEYPOINTS_3D')]
    raw = pq.read_table(structure.data_parquet_path, filters=filters).replace_schema_metadata(None)
    config = PosthocMocapPipelineConfig(start_stage='filtering', base_run_id=run_id, sensor_group=group,
        filter_config=PosthocFilterConfig(cutoff=1.0))
    for start in ('filtering', 'reconstruction'):
        processing.run_saved_numerical_stages(structure=structure, config=config.model_copy(update={'start_stage': start}),
            reporter=TaskProgressReporter.noop())
        assert raw.equals(pq.read_table(structure.data_parquet_path, filters=filters).replace_schema_metadata(None))
    assert not structure.videos_synchronized_dir.exists()
