"""Tall exports preserve saved values and survive interruption without touching source."""

from concurrent.futures import CancelledError
import csv
import json
import os

import pyarrow as pa
import pyarrow.csv as arrow_csv
import pyarrow.parquet as pq
import pytest
from filelock import FileLock, Timeout

from freemocap.core.recording.exports import publication, tall_csv
from freemocap.core.recording.exports.tall_csv import TallCsvRequest, export_tall_csv
from freemocap.core.recording.parquet_storage.shared_file import replace_recording_file
from freemocap.core.recording.sample_encoding.arrow_schema import SAMPLE_SCHEMA, DESCRIPTOR_KEY
from freemocap.tests.test_saved_reconstruction import saved_request  # noqa: F401


def export(request, **kwargs):
    return export_tall_csv(structure=request.structure, request=TallCsvRequest(**kwargs))


def read_csv(path, schema=SAMPLE_SCHEMA):
    return arrow_csv.read_csv(path, convert_options=arrow_csv.ConvertOptions(
        column_types={f.name: f.type for f in schema}, strings_can_be_null=True, null_values=[''],
        quoted_strings_can_be_null=False)).cast(schema)


def test_exact_rows_metadata_static_and_default_replacement(saved_request):
    path = saved_request.structure.data_parquet_path
    table = pq.read_table(path)
    # Exercise round-trip floats and nulls in the same column.
    values = [None if i % 3 == 0 else (1.2345678901234567 if i % 2 else -1e-200) for i in range(table.num_rows)]
    table = table.set_column(table.schema.get_field_index('value'), 'value', pa.array(values, pa.float64()))
    pq.write_table(table, path)
    original = path.read_bytes()
    result = export(saved_request)
    assert result.run_id == 3
    assert result.files[0].name == 'recording.tall.csv'
    assert result.files[0].read_bytes().startswith(b'\xef\xbb\xbf')
    assert read_csv(result.files[0]).equals(table.replace_schema_metadata(None))
    manifest = publication.verified_manifest(result.manifest_path)
    assert manifest.snapshots[result.source_sha256]['recording_descriptor'] == json.loads(table.schema.metadata[DESCRIPTOR_KEY])
    assert manifest.artifacts[result.files[0].name].rows == table.num_rows
    assert read_csv(result.files[1], tall_csv.STATIC_SCHEMA).schema.names == tall_csv.STATIC_SCHEMA.names
    export(saved_request)
    assert path.read_bytes() == original
    assert not list(result.manifest_path.parent.glob('.staging-*'))


def test_unknown_run_and_stale_revision_do_not_create_exports(saved_request):
    for request in (TallCsvRequest(run_id=99), TallCsvRequest(expected_revision='stale')):
        with pytest.raises(ValueError):
            export_tall_csv(structure=saved_request.structure, request=request)
    assert not saved_request.structure.exports_dir.exists()


def test_retained_exports_never_overwritten_by_default_or_keep(saved_request):
    result = export(saved_request, keep=True)
    before = {p: p.read_bytes() for p in (*result.files, result.manifest_path)}
    assert result.files[0].parent.name == 'run-3'
    assert result.files[0].name == 'recording.run-3.tall.csv'
    with pytest.raises(FileExistsError):
        export(saved_request, keep=True)
    export(saved_request)
    assert all(p.read_bytes() == contents for p, contents in before.items())


def test_cancellation_and_write_failure_preserve_previous_exports(saved_request, monkeypatch):
    result = export(saved_request)
    before = {p: p.read_bytes() for p in (*result.files, result.manifest_path)}
    stopped = False
    def progress(_):
        nonlocal stopped
        stopped = True
    with pytest.raises(CancelledError):
        export_tall_csv(structure=saved_request.structure, request=TallCsvRequest(),
            progress=progress, cancelled=lambda: stopped)
    def fail(*args, **kwargs):
        raise OSError('injected staging failure')
    monkeypatch.setattr(tall_csv, 'read_static_channels', fail)
    with pytest.raises(OSError, match='staging failure'):
        export(saved_request)
    assert all(p.read_bytes() == contents for p, contents in before.items())
    assert not list(result.manifest_path.parent.glob('.staging-*'))


@pytest.mark.parametrize('keep', [False, True])
def test_partial_publication_is_detectable_and_recoverable(saved_request, monkeypatch, keep):
    replace = publication.os.replace
    def fail(source, destination):
        if str(destination).endswith('.metadata.json'):
            raise OSError('injected metadata replacement failure')
        return replace(source, destination)
    monkeypatch.setattr(publication.os, 'replace', fail)
    with pytest.raises(OSError, match='replacement failure'):
        export(saved_request, keep=keep)
    root = saved_request.structure.exports_dir
    directory = root / 'run-3' if keep else root
    manifest = directory / ('recording.run-3.metadata.json' if keep else 'recording.metadata.json')
    with pytest.raises(ValueError, match='incomplete'):
        publication.verified_manifest(manifest)
    monkeypatch.setattr(publication.os, 'replace', replace)
    tall_csv.recover_tall_export(structure=saved_request.structure, retained_run_id=3 if keep else None)
    assert len(publication.verified_manifest(manifest).artifacts) == 2
    assert not (directory / '.publication.json').exists()


def test_source_replacement_during_export_keeps_one_snapshot(saved_request):
    path = saved_request.structure.data_parquet_path
    old_hash = publication.digest(path)
    old_table = pq.read_table(path)
    replacement = path.with_suffix('.replacement')
    metadata = dict(old_table.schema.metadata)
    descriptor = json.loads(metadata[DESCRIPTOR_KEY])
    descriptor['recording_info']['replacement'] = True
    metadata[DESCRIPTOR_KEY] = json.dumps(descriptor).encode()
    pq.write_table(old_table.replace_schema_metadata(metadata), replacement)
    def replace(_):
        if replacement.exists():
            replace_recording_file(source=replacement, destination=path)
    result = export_tall_csv(structure=saved_request.structure, request=TallCsvRequest(), progress=replace)
    assert result.source_sha256 == old_hash != publication.digest(path)
    assert read_csv(result.files[0]).equals(old_table.replace_schema_metadata(None))
    assert 'replacement' not in publication.verified_manifest(result.manifest_path).snapshots[old_hash]['recording_descriptor']['recording_info']


def test_duplicate_rows_rejected_before_publication(saved_request):
    path = saved_request.structure.data_parquet_path
    table = pq.read_table(path)
    pq.write_table(pa.concat_tables([table, table]), path)
    with pytest.raises(ValueError):
        export(saved_request)
    assert not (saved_request.structure.exports_dir / 'recording.tall.csv').exists()


def test_export_lock_and_hash_verification(saved_request):
    result = export(saved_request)
    with FileLock(saved_request.structure.exports_dir / '.exports.lock', timeout=0):
        with pytest.raises(Timeout):
            export(saved_request)
    with result.files[0].open('ab') as stream:
        stream.write(b'changed')
    with pytest.raises(ValueError, match='missing or changed'):
        publication.verified_manifest(result.manifest_path)


def test_multiple_runs_clocks_quoted_labels_and_static_values(tmp_path):
    from freemocap.core.recording.data_descriptors.recording_descriptor import RecordingMetadata
    from freemocap.system.recording_structure.recording_structure import RecordingStructure
    structure = RecordingStructure(base_directory=tmp_path, recording_name='recording')
    structure.full_path.mkdir()
    names = ['001', 'NA', 'é,"quoted"\nlabel']
    channels = [dict(sensor_group=group, source='clock', reference_frame=None, kind='TIMESTAMPS',
                    names=names, components={'timestamp': 's'}, stage='timing') for group in ('a', 'b')]
    run = dict(sensor_groups={group: dict(clock_description=group, sample_count=2) for group in ('a', 'b')},
        sources={'clock': dict(kind='timing', definition={})}, reference_frames={}, models={}, processing={},
        channels=channels, static_channels=[dict(channel=dict(sensor_group='a', source='clock', reference_frame=None,
            kind='SEGMENT_LENGTHS', names=['limb'], components={'length': 'mm'}, stage='scale_fit'),
            values={'limb': {'length': 12.345678901234567}})])
    metadata = RecordingMetadata(recording_id='recording', selected_run_id=7, runs={3: run, 7: run})
    rows = [dict(timestamp_s=time, frame_number=frame, sensor_group=group, source='clock',
        reference_frame=None, channel='TIMESTAMPS', name=name, component='timestamp', value=time,
        units='s', run_id=rid) for rid in (3, 7) for group in ('a', 'b')
        for frame, time in ((10, 0.1 if group == 'a' else 0.2), (41, 1.23 if group == 'a' else 2.57)) for name in names]
    table = pa.Table.from_pylist(rows, schema=SAMPLE_SCHEMA).replace_schema_metadata({DESCRIPTOR_KEY: metadata.model_dump_json().encode()})
    pq.write_table(table, structure.data_parquet_path)
    for rid in (None, 3):
        result = export_tall_csv(structure=structure, request=TallCsvRequest(run_id=rid))
        assert result.run_id == (7 if rid is None else rid)
        expected = [row for row in rows if row['run_id'] == result.run_id]
        with result.files[0].open(encoding='utf-8-sig', newline='') as stream:
            parsed = list(csv.DictReader(stream))
        assert [row['name'] for row in parsed] == [row['name'] for row in expected]
        assert all(row['reference_frame'] == '' for row in parsed)
        assert read_csv(result.files[0]).equals(pa.Table.from_pylist(expected, schema=SAMPLE_SCHEMA))
        static = read_csv(result.files[1], tall_csv.STATIC_SCHEMA)
        assert static.num_rows == 1
        assert static['value'][0].as_py() == 12.345678901234567


def test_header_only_empty_run(tmp_path):
    from freemocap.core.recording.data_descriptors.recording_descriptor import RecordingMetadata
    from freemocap.system.recording_structure.recording_structure import RecordingStructure
    structure = RecordingStructure(base_directory=tmp_path, recording_name='empty')
    structure.full_path.mkdir()
    metadata = RecordingMetadata(recording_id='empty', selected_run_id=0, runs={0: dict(
        sensor_groups={}, sources={}, reference_frames={}, models={}, processing={}, channels=[])})
    pq.write_table(pa.Table.from_batches([], schema=SAMPLE_SCHEMA).replace_schema_metadata(
        {DESCRIPTOR_KEY: metadata.model_dump_json().encode()}), structure.data_parquet_path)
    result = export_tall_csv(structure=structure, request=TallCsvRequest())
    assert read_csv(result.files[0]).num_rows == 0
    assert read_csv(result.files[1], tall_csv.STATIC_SCHEMA).num_rows == 0
