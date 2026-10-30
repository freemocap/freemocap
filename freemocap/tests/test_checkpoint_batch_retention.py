"""Checkpoint copying decodes each group once and preserves validation failures."""

from collections import Counter
from concurrent.futures import CancelledError
from dataclasses import replace

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
from freemocap.core.pipeline.posthoc.stage_execution_plan import StageExecutionPlan, retained_run
from freemocap.core.recording.parquet_storage.checkpoint_publication import checkpoint_batches, publish_checkpoint
from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
from freemocap.core.recording.sample_encoding.arrow_schema import DESCRIPTOR_KEY, SAMPLE_SCHEMA, SampleValidator
from freemocap.tests.test_selective_parquet_read import observe_reads, write_channel_groups
from freemocap.tests.test_wide_csv_export import scientific_recording  # noqa: F401


@pytest.fixture
def checkpoint_recording(scientific_recording):
    structure, original = scientific_recording
    rows = []
    for row in original:
        # The export fixture deliberately omits a scalar. Checkpoint publication
        # requires complete channel coverage, including explicit null values.
        if (row['channel'], row['frame_number'], row['name'], row['component']) == (
            'RAW_KEYPOINTS_3D', 42, 'point%a', 'y'
        ):
            rows.append({**row, 'component': 'z', 'value': None})
        rows.append(row)
    rows.extend({**row, 'run_id': 8} for row in tuple(rows) if row['run_id'] == 3)
    metadata = read_metadata(path=structure.data_parquet_path)
    metadata = metadata.model_copy(update={'runs': {**metadata.runs, 8: metadata.runs[3]}})
    schema = SAMPLE_SCHEMA.with_metadata({DESCRIPTOR_KEY: metadata.model_dump_json().encode()})
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), structure.data_parquet_path)
    return structure, metadata, rows


def checkpoint_plan(target=9):
    return StageExecutionPlan(base_run_id=3, target_run_id=target, sensor_groups=('a',),
        execute=(ProcessingStage.RECONSTRUCTION,), invalidate=(ProcessingStage.RECONSTRUCTION,))


def computed_rotations(rows, target):
    return [dict(row, run_id=target) for row in rows
            if row['run_id'] == 3 and row['channel'] == 'ROTATIONS_WORLD']


@pytest.mark.parametrize('target', [3, 8, 9])
@pytest.mark.parametrize('statistics', [False, True])
@pytest.mark.parametrize('mixed', [False, True])
def test_retention_matches_exact_rows_with_one_decode_per_group(
    checkpoint_recording, monkeypatch, target, statistics, mixed,
):
    structure, metadata, rows = checkpoint_recording
    if mixed:
        # Mixed external groups retain trajectory order, while exercising row
        # masks and scalar validation rather than only single-channel batches.
        schema = pq.read_schema(structure.data_parquet_path)
        pq.write_table(pa.Table.from_pylist(rows, schema=schema), structure.data_parquet_path,
                       row_group_size=7, write_statistics=statistics)
    else:
        write_channel_groups(structure, rows, statistics=statistics)
    plan = checkpoint_plan(target)
    computed = computed_rotations(rows, target)
    expected = [row for row in rows if row['run_id'] != target]
    expected += [dict(row, run_id=target) for row in rows
                 if row['run_id'] == 3 and row['channel'] != 'ROTATIONS_WORLD']
    expected += computed
    calls = observe_reads(monkeypatch)
    opens = []
    original_open = pq.ParquetFile.__init__

    def open_file(self, *args, **kwargs):
        opens.append(args)
        original_open(self, *args, **kwargs)

    monkeypatch.setattr(pq.ParquetFile, '__init__', open_file)
    batches = list(checkpoint_batches(structure=structure, metadata=metadata, plan=plan,
        result=metadata.runs[3], computed_batches=(pa.RecordBatch.from_pylist(computed, schema=SAMPLE_SCHEMA),)))
    actual = [row for batch in batches for row in batch.to_pylist()]
    assert Counter(tuple(row[name] for name in SAMPLE_SCHEMA.names) for row in actual) == Counter(
        tuple(row[name] for name in SAMPLE_SCHEMA.names) for row in expected)
    assert len(opens) == 1
    decoded = [call['row_groups'][0] for call in calls]
    assert len(decoded) == len(set(decoded))
    assert all(batch.schema.metadata is None for batch in batches)
    published = metadata.model_copy(update={'runs': {**metadata.runs, target: metadata.runs[3]}})
    validator = SampleValidator(metadata=published)
    for batch in batches:
        validator.accept(batch=batch)
    validator.finish()
    if not mixed:
        assert validator.scalar_rows == 0


@pytest.mark.parametrize('corruption', ['channel', 'source', 'reference_frame'])
def test_undeclared_retained_rows_fail_publication_atomically(checkpoint_recording, corruption):
    structure, metadata, rows = checkpoint_recording
    rows[0] = {**rows[0], corruption: 'undeclared'}
    write_channel_groups(structure, rows)
    original = structure.data_parquet_path.read_bytes()
    with pytest.raises(ValueError, match='Undeclared channel'):
        publish_checkpoint(structure=structure, metadata=metadata, plan=checkpoint_plan(),
            result=metadata.runs[3], computed_batches=())
    assert structure.data_parquet_path.read_bytes() == original
    assert not list(structure.full_path.glob('*.parquet.tmp'))


def test_unknown_stored_runs_and_groups_remain_excluded(checkpoint_recording):
    structure, metadata, rows = checkpoint_recording
    extra = [dict(rows[0], run_id=99), dict(rows[0], sensor_group='unknown')]
    write_channel_groups(structure, [*extra, *rows])
    batches = list(checkpoint_batches(structure=structure, metadata=metadata, plan=checkpoint_plan(),
        result=metadata.runs[3], computed_batches=()))
    actual = [row for batch in batches for row in batch.to_pylist()]
    assert all(row['run_id'] != 99 and row['sensor_group'] != 'unknown' for row in actual)


@pytest.mark.parametrize('unknown', ['run', 'group', 'empty'])
def test_invalid_requested_runs_and_groups_still_fail(checkpoint_recording, unknown):
    structure, metadata, _ = checkpoint_recording
    run = metadata.runs[0]
    if unknown == 'run':
        runs = {**metadata.runs, 99: run}
    else:
        groups = {'unknown': run.sensor_groups['a']} if unknown == 'group' else {}
        runs = {**metadata.runs, 0: run.model_copy(update={'sensor_groups': groups})}
    supplied = metadata.model_copy(update={'runs': runs})
    with pytest.raises(KeyError if unknown == 'run' else ValueError):
        list(checkpoint_batches(structure=structure, metadata=supplied, plan=checkpoint_plan(),
            result=metadata.runs[3], computed_batches=()))


def test_empty_reuse_keeps_static_metadata_without_decoding_base(checkpoint_recording, monkeypatch):
    structure, metadata, rows = checkpoint_recording
    write_channel_groups(structure, rows)
    plan = replace(checkpoint_plan(3), sensor_groups=('a', 'b'),
        invalidate=(ProcessingStage.TIMING, ProcessingStage.TRIANGULATION, ProcessingStage.RECONSTRUCTION))
    result = retained_run(base=metadata.runs[3], plan=plan)
    assert result.channels == () and result.static_channels
    calls = observe_reads(monkeypatch)
    batches = list(checkpoint_batches(structure=structure, metadata=metadata, plan=plan,
        result=result, computed_batches=()))
    assert {row['run_id'] for batch in batches for row in batch.to_pylist()} == {0, 8}
    assert [call['row_groups'] for call in calls] == [[0], [1], [2], [6], [7], [8]]


def test_cancelled_read_does_not_decode(checkpoint_recording, monkeypatch):
    structure, metadata, _ = checkpoint_recording
    calls = observe_reads(monkeypatch)
    with pytest.raises(CancelledError):
        list(checkpoint_batches(structure=structure, metadata=metadata, plan=checkpoint_plan(),
            result=metadata.runs[3], computed_batches=(), cancelled=lambda: True))
    assert calls == []


@pytest.mark.parametrize('failure', ['wrong_run', 'wrong_channel', 'producer'])
def test_computed_failures_leave_recording_unchanged(checkpoint_recording, failure):
    structure, metadata, rows = checkpoint_recording
    write_channel_groups(structure, rows)
    original = structure.data_parquet_path.read_bytes()

    def computed():
        if failure == 'producer':
            raise OSError('Numerical producer failed')
        values = computed_rotations(rows, 9)
        values[0] = dict(values[0], **({'run_id': 3} if failure == 'wrong_run' else {'channel': 'TIMESTAMPS'}))
        yield pa.RecordBatch.from_pylist(values, schema=SAMPLE_SCHEMA)

    with pytest.raises(OSError if failure == 'producer' else ValueError,
                       match='producer failed|planned target channels'):
        publish_checkpoint(structure=structure, metadata=metadata, plan=checkpoint_plan(),
            result=metadata.runs[3], computed_batches=computed())
    assert structure.data_parquet_path.read_bytes() == original
    assert not list(structure.full_path.glob('*.parquet.tmp'))
