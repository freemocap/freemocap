"""Resume actual canonical recordings without media access or upstream computation."""

from freemocap.tests.saved_graph_helpers import run_saved_graph
from freemocap.tests.test_saved_reconstruction import saved_request  # noqa: F401

from concurrent.futures import CancelledError
from unittest.mock import Mock
from pathlib import Path
import shutil

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


def rows(request):
    return pa.Table.from_batches(list(read_batches(path=request.structure.data_parquet_path,
        run_id=request.run_id, sensor_groups=(request.sensor_group,)))).to_pylist()


def test_filter_then_reconstruct_preserves_raw_and_timing(saved_request, monkeypatch):
    before = rows(saved_request)
    config = PosthocMocapPipelineConfig(start_stage='filtering', base_run_id=3,
        sensor_group='mocap')
    run_saved_graph(structure=saved_request.structure, config=config,
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
    monkeypatch.setattr('freemocap.core.pipeline.dataflow.saved_spatial_pipeline.prepare_recording_points', Mock(side_effect=AssertionError('Filtering must be reused')))
    run_saved_graph(structure=saved_request.structure,
        config=config.model_copy(update={'start_stage': 'scale_fit'}), reporter=TaskProgressReporter.noop())
    assert read_metadata(path=saved_request.structure.data_parquet_path).runs[3].scale_fits == fits
    monkeypatch.setattr('freemocap.core.pipeline.dataflow.saved_spatial_pipeline.fit_skeletons_for_recording', Mock(side_effect=AssertionError('Scale must be reused')))
    run_saved_graph(structure=saved_request.structure,
        config=config.model_copy(update={'start_stage': 'reconstruction', 'anchor_segment_name': 'skull'}), reporter=TaskProgressReporter.noop())
    assert read_metadata(path=saved_request.structure.data_parquet_path).runs[3].scale_fits == fits
    # The human setting must not overwrite an independently tracked board's anchor.
    assert read_metadata(path=saved_request.structure.data_parquet_path).runs[3].models['charuco_board'].anchor_segment_name is None
    assert [row for row in rows(saved_request) if row['channel'] == 'RAW_KEYPOINTS_3D'] == before


def test_cancelled_resume_preserves_previous_file(saved_request):
    before = saved_request.structure.data_parquet_path.read_bytes()
    with pytest.raises(CancelledError):
        run_saved_graph(structure=saved_request.structure,
            config=PosthocMocapPipelineConfig(start_stage='filtering', base_run_id=3),
            reporter=TaskProgressReporter.noop(), cancelled=lambda: True)
    assert saved_request.structure.data_parquet_path.read_bytes() == before


def test_missing_input_does_not_fall_back_to_tracking(saved_request):
    before = saved_request.structure.data_parquet_path.read_bytes()
    with pytest.raises(RuntimeError, match='KEYPOINTS_3D'):
        run_saved_graph(structure=saved_request.structure,
            config=PosthocMocapPipelineConfig(start_stage='reconstruction', base_run_id=3),
            reporter=TaskProgressReporter.noop())
    assert saved_request.structure.data_parquet_path.read_bytes() == before






@pytest.mark.e2e
@pytest.mark.parametrize('name', ['freemocap_test_data', 'freemocap_sample_data'])
def test_real_recording_filter_and_reconstruct_without_media(tmp_path, name, record_property):
    import os
    import hashlib
    from time import perf_counter

    def digest(path):
        with path.open('rb') as stream:
            return hashlib.file_digest(stream, 'sha256').hexdigest()

    prepared = Path(os.environ.get('FREEMOCAP_PROVENANCE_PREPARED_ROOT', Path.home() / 'freemocap_data/testing/prepared'))
    source = prepared / name / 'current/recordings' / name / f'{name}_data.parquet'
    if not source.is_file():
        pytest.skip(f'Prepare {name} through the production pipeline first')
    original_digest = digest(source)
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
    previous_output = None
    for index, start in enumerate(('filtering', 'scale_fit', 'reconstruction', 'reconstruction')):
        before = read_metadata(path=structure.data_parquet_path).runs[run_id]
        settings = {'start_stage': start}
        if start == 'reconstruction':
            settings['anchor_segment_name'] = 'skull'
        started = perf_counter()
        run_saved_graph(structure=structure, config=config.model_copy(update=settings),
            reporter=TaskProgressReporter.noop())
        record_property(f'{index}_{start}_seconds', perf_counter() - started)
        assert raw.equals(pq.read_table(structure.data_parquet_path, filters=filters).replace_schema_metadata(None))
        after = read_metadata(path=structure.data_parquet_path).runs[run_id]
        assert after.sensor_groups == before.sensor_groups
        assert after.reference_frames == before.reference_frames
        if start == 'reconstruction':
            assert after.scale_fits == before.scale_fits
            assert after.models['standard_human'].anchor_segment_name == 'skull'
            output = pq.read_table(structure.data_parquet_path, filters=[
                ('run_id', '=', run_id), ('channel', 'in', ['LANDMARKS_3D', 'ROTATIONS_WORLD'])
            ]).replace_schema_metadata(None)
            assert output.num_rows > 0
            if previous_output is not None:
                assert output.equals(previous_output), 'Identical rerun changed numerical output'
            previous_output = output
    assert not structure.videos_synchronized_dir.exists()
    assert digest(source) == original_digest, 'Replay modified the reference recording'
