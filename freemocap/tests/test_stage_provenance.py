"""Settings survive real publication, restart, retention and failed replacement."""

from datetime import datetime, timezone

import pytest
import numpy as np
from pydantic import ValidationError

from freemocap.core.pipeline.posthoc import saved_stage_processing as processing
from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
from freemocap.core.pipeline.posthoc.stage_execution_plan import StageExecutionPlan
from freemocap.core.pipeline.posthoc.task_progress_reporter import TaskProgressReporter
from freemocap.core.reconstruction.posthoc_filtering import PosthocFilterConfig
from freemocap.core.recording.data_descriptors.stage_provenance import (
    StageProvenanceSet, stage_provenance, set_stage_provenance,
)
from freemocap.core.recording.parquet_storage import parquet_writer
from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
from freemocap.core.recording.parquet_storage.checkpoint_publication import publish_checkpoint
from freemocap.core.recording.result_processing.provenance import ProvenanceContext, provenance_signature
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.tests.test_saved_reconstruction import saved_request


def config(cutoff=4.0, start='filtering'):
    return PosthocMocapPipelineConfig(base_run_id=3, sensor_group='mocap', start_stage=start,
        filter_config=PosthocFilterConfig(cutoff=cutoff), skeleton_fit_enabled=False)


def process(request, settings):
    processing.run_saved_numerical_stages(structure=request.structure, config=settings,
        reporter=TaskProgressReporter.noop())
    return read_metadata(path=request.structure.data_parquet_path)


def test_unknown_history_is_not_backfilled_and_versions_fail_loudly(saved_request):
    metadata = read_metadata(path=saved_request.structure.data_parquet_path)
    assert not stage_provenance(metadata.runs[3].processing, 'mocap').stages
    with pytest.raises(ValidationError):
        StageProvenanceSet.model_validate(dict(version=2, stages={}))


def test_typed_identity_rejects_missing_input_and_naive_time():
    context = ProvenanceContext('attempt', datetime.now(timezone.utc), {'core': 'test'})
    with pytest.raises(ValidationError, match='input signatures'):
        context.record(settings={}, defaults=None, inputs={}, sources=('human',))
    naive = ProvenanceContext('attempt', datetime(2026, 9, 30), {'core': 'test'})
    with pytest.raises(ValidationError, match='timezone'):
        naive.record(settings={}, defaults=None, inputs={'points': 'content'}, sources=('human',))


def test_numpy_backed_geometry_has_stable_content_identity():
    geometry = {'camera_matrix': np.eye(3), 'translation': np.zeros(3)}
    assert provenance_signature(geometry) == provenance_signature({key: value.copy() for key, value in geometry.items()})
    changed = dict(geometry, translation=np.ones(3))
    assert provenance_signature(changed) != provenance_signature(geometry)


def test_restart_retains_actual_filter_and_historical_unknowns(saved_request):
    first = process(saved_request, config())
    entries = stage_provenance(first.runs[3].processing, 'mocap').stages
    filtering = entries[ProcessingStage.FILTERING]
    assert filtering.effective_settings['cutoff'] == 4.0
    assert filtering.default_settings['cutoff'] == 6.0
    assert filtering.base_run_id == 3 and filtering.base_descriptor_signature
    assert ProcessingStage.OBSERVATIONS not in entries
    assert 'export_to_blender' not in filtering.effective_settings
    second = process(saved_request, config(cutoff=2.0, start='reconstruction'))
    updated = stage_provenance(second.runs[3].processing, 'mocap').stages
    assert updated[ProcessingStage.FILTERING] == filtering
    assert updated[ProcessingStage.SCALE_FIT] == entries[ProcessingStage.SCALE_FIT]
    assert updated[ProcessingStage.RECONSTRUCTION].attempt_id != entries[ProcessingStage.RECONSTRUCTION].attempt_id


def test_keep_then_overwrite_preserves_settings_with_retained_result(saved_request):
    first = process(saved_request, config())
    plan = StageExecutionPlan(3, 4, ('mocap',), (), ())
    with parquet_writer.recording_write_lock(structure=saved_request.structure):
        kept = publish_checkpoint(structure=saved_request.structure, metadata=first,
            plan=plan, result=first.runs[3], computed_batches=())
    assert kept.selected_run_id == 4
    assert kept.runs[4] == first.runs[3]
    changed = process(saved_request, config(cutoff=2.0))
    assert changed.runs[4] == first.runs[3]
    assert stage_provenance(changed.runs[3].processing, 'mocap').stages['filtering'].effective_settings['cutoff'] == 2.0


def test_failed_replacement_retains_old_settings_and_bytes(saved_request, monkeypatch):
    before = process(saved_request, config())
    content = saved_request.structure.data_parquet_path.read_bytes()
    def fail(**kwargs):
        raise OSError('injected replace failure')
    monkeypatch.setattr(parquet_writer, 'replace_recording_file', fail)
    with pytest.raises(OSError, match='replace failure'):
        process(saved_request, config(cutoff=2.0))
    assert saved_request.structure.data_parquet_path.read_bytes() == content
    assert read_metadata(path=saved_request.structure.data_parquet_path) == before


def test_legacy_model_refresh_removes_superseded_provenance(saved_request):
    from freemocap.tests.refresh_recording_reconstruction import refresh_reconstruction
    from freemocap.core.recording.result_processing.saved_reconstruction import read_saved_reconstruction
    bundle = read_saved_reconstruction(saved_request).numerical_input.bundles[0]
    before = process(saved_request, config())
    filtering = stage_provenance(before.runs[3].processing, 'mocap').stages['filtering']
    refresh_reconstruction(saved_request.structure, bundle)
    after = read_metadata(path=saved_request.structure.data_parquet_path)
    entries = stage_provenance(after.runs[3].processing, 'mocap').stages
    assert entries['filtering'] == filtering
    assert not {'scale_fit', 'reconstruction', 'biomechanics', 'skeleton_fit'} & entries.keys()


def test_checkpoint_rejects_relabelled_upstream_provenance(saved_request):
    before = process(saved_request, config())
    run = before.runs[3]
    entries = dict(stage_provenance(run.processing, 'mocap').stages)
    entries[ProcessingStage.FILTERING] = entries[ProcessingStage.FILTERING].model_copy(update={'effective_settings': {'cutoff': 99.0}})
    changed = run.model_copy(update={'processing': set_stage_provenance(run.processing, 'mocap', entries)})
    with parquet_writer.recording_write_lock(structure=saved_request.structure):
        with pytest.raises(ValueError, match='preserve reusable stage provenance'):
            publish_checkpoint(structure=saved_request.structure, metadata=before,
                plan=StageExecutionPlan(3, 4, ('mocap',), (), ()), result=changed, computed_batches=())
