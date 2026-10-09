"""Acceptance on fresh production dataset outputs, then real detector-free replay.

Set FREEMOCAP_PROVENANCE_PREPARED_ROOT to the isolated --prepared-root from
`python -B -m freemocap.tools.datasets process-all`. No inference is mocked for
the producer run. This suite copies its outputs and exercises the real worker.
"""

from concurrent.futures import CancelledError
import hashlib
import json
import os
from pathlib import Path
import shutil

import pyarrow.parquet as pq
import pytest

from freemocap.core.pipeline.posthoc.saved_stage_processing import run_saved_numerical_stages, select_group
from freemocap.core.pipeline.posthoc.task_progress_reporter import TaskProgressReporter
from freemocap.core.recording.data_descriptors.stage_provenance import stage_provenance
from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
from freemocap.core.reconstruction.posthoc_filtering import PosthocFilterConfig
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.system.recording_structure.recording_structure import RecordingStructure


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.parametrize('name,frames,cutoff', [('freemocap_test_data', 222, 1.0), ('freemocap_sample_data', 1108, 4.0)])
def test_fresh_outputs_then_filter_restart_preserve_provenance(tmp_path, name, frames, cutoff):
    configured = os.environ.get('FREEMOCAP_PROVENANCE_PREPARED_ROOT')
    if not configured:
        pytest.skip('Set FREEMOCAP_PROVENANCE_PREPARED_ROOT to fresh process-all outputs')
    root = Path(configured) / name
    from freemocap.tools.datasets.workflow import checked_ready
    marker = checked_ready(root)
    assert marker is not None
    assert marker['workflow']['start_stage'] == 'observations', 'Acceptance requires full fresh processing'
    assert marker['result']['mocap_task']['status'] == 'complete'
    source = Path(marker['recording']) / f'{name}_data.parquet'
    original_hash = digest(source)
    assert original_hash == marker['result']['validation']['parquet_sha256']
    structure = RecordingStructure(base_directory=tmp_path, recording_name=name)
    structure.full_path.mkdir()
    shutil.copy2(source, structure.data_parquet_path)
    metadata = read_metadata(path=structure.data_parquet_path)
    run_id = metadata.selected_run_id
    base = metadata.runs[run_id]
    group = select_group(base, None)
    assert base.sensor_groups[group].sample_count == frames
    entries = stage_provenance(base.processing, group).stages
    assert set(entries) == {'timing', 'observations', 'triangulation', 'filtering', 'scale_fit',
                            'reconstruction', 'biomechanics'}
    assert entries['filtering'].effective_settings['enabled'] == (frames == 1108)
    assert entries['filtering'].default_settings['cutoff'] == 6.0
    filters = [('run_id', '=', run_id), ('channel', 'in', ['OVERLAY_2D', 'RAW_KEYPOINTS_3D', 'TIMESTAMPS'])]
    upstream = pq.read_table(structure.data_parquet_path, filters=filters).replace_schema_metadata(None)
    config = PosthocMocapPipelineConfig(start_stage='filtering', base_run_id=run_id, sensor_group=group,
        filter_config=PosthocFilterConfig(cutoff=cutoff))
    run_saved_numerical_stages(structure=structure, config=config, reporter=TaskProgressReporter.noop())
    after = read_metadata(path=structure.data_parquet_path)
    updated = stage_provenance(after.runs[run_id].processing, group).stages
    for stage in ('timing', 'observations', 'triangulation'):
        assert updated[stage] == entries[stage]
    assert updated['filtering'].effective_settings['cutoff'] == cutoff
    assert updated['filtering'].default_settings['cutoff'] == 6.0
    assert upstream.equals(pq.read_table(structure.data_parquet_path, filters=filters).replace_schema_metadata(None))
    assert not structure.videos_synchronized_dir.exists(), 'Replay must not need videos'
    before_cancel = digest(structure.data_parquet_path)
    with pytest.raises(CancelledError):
        run_saved_numerical_stages(structure=structure, config=config,
            reporter=TaskProgressReporter.noop(), cancelled=lambda: True)
    assert digest(structure.data_parquet_path) == before_cancel
    assert digest(source) == original_hash, 'Consumer acceptance modified producer output'
