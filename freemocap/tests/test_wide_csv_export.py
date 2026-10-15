"""Scientific exports preserve context, order, missingness and exact saved values."""
from concurrent.futures import CancelledError
import csv
import json

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from freemocap.core.recording.data_descriptors.recording_descriptor import RecordingMetadata
from freemocap.core.recording.exports import arrays, publication, wide_csv
from freemocap.core.recording.exports.requests import ScientificExportRequest
from freemocap.core.recording.parquet_storage.recording_view import recording_view
from freemocap.core.recording.sample_encoding.arrow_schema import DESCRIPTOR_KEY, SAMPLE_SCHEMA
from freemocap.system.recording_structure.recording_structure import RecordingStructure


@pytest.fixture
def scientific_recording(tmp_path):
    structure = RecordingStructure(base_directory=tmp_path, recording_name='recording')
    structure.full_path.mkdir()
    channels = [dict(sensor_group='a', source='points', reference_frame='world', kind='RAW_KEYPOINTS_3D',
        names=['point.a', 'point%a'], components={'z': 'mm', 'y': 'mm', 'x': 'mm'}, stage='triangulation'),
        dict(sensor_group='a', source='points', reference_frame='world', kind='ROTATIONS_WORLD',
        names=['segment'], components={'w': '1', 'x': '1', 'y': '1', 'z': '1'}, stage='reconstruction'),
        dict(sensor_group='b', source='clock', reference_frame=None, kind='TIMESTAMPS',
        names=['clock'], components={'timestamp': 's'}, stage='timing')]
    run = dict(sensor_groups={g: dict(clock_description=g, sample_count=2) for g in ('a', 'b')},
        sources={'points': dict(kind='tracker', definition={}), 'clock': dict(kind='timing', definition={})},
        reference_frames={'world': dict(units='mm')}, models={}, processing={}, channels=channels,
        static_channels=[dict(channel=dict(sensor_group='a', source='points', reference_frame='world', kind='SEGMENT_LENGTHS',
            names=['segment'], components={'length': 'mm'}, stage='scale_fit'), values={'segment': {'length': 12.345678901234567}})])
    metadata = RecordingMetadata(recording_id='recording', selected_run_id=3, runs={0: run, 3: run})
    rows = []
    for rid in (0, 3):
        for c in channels:
            for frame, time in ((10, 0.125), (42, 0.987654321)):
                for ni, name in enumerate(c['names']):
                    for ci, (component, units) in enumerate(c['components'].items()):
                        if c['kind'] == 'RAW_KEYPOINTS_3D' and frame == 42 and ni == 1 and ci == 0:
                            continue
                        value = None if frame == 10 and ci == 0 else rid + ni + ci + 1.2345678901234567
                        if c['kind'] == 'ROTATIONS_WORLD':
                            value = 1. if component == 'w' else 0.
                        rows.append(dict(run_id=rid, sensor_group=c['sensor_group'], source=c['source'], reference_frame=c['reference_frame'],
                            channel=c['kind'], name=name, component=component, units=units, frame_number=frame,
                            timestamp_s=time + (5 if c['sensor_group'] == 'b' else 0), value=value))
    table = pa.Table.from_pylist(rows, schema=SAMPLE_SCHEMA).replace_schema_metadata({DESCRIPTOR_KEY: metadata.model_dump_json().encode()})
    pq.write_table(table, structure.data_parquet_path)
    return structure, rows


def export(structure, **kwargs):
    if 'wide_csv' not in kwargs:
        with recording_view(structure.data_parquet_path) as view:
            kwargs['wide_csv'] = tuple(item[0] for item in arrays.available_channels(view.metadata.runs[3]))
    return wide_csv.export_scientific(structure=structure, request=ScientificExportRequest(formats=('wide_csv',), **kwargs))


def test_arrays_and_csv_match_source_rows_with_split_tables(scientific_recording, monkeypatch):
    structure, rows = scientific_recording
    original = structure.data_parquet_path.read_bytes()
    monkeypatch.setattr(wide_csv, 'MAX_ROWS', 1)
    monkeypatch.setattr(wide_csv, 'MAX_VALUE_COLUMNS', 2)
    result = export(structure)
    manifest = publication.verified_manifest(result.manifest_path)
    snapshot = manifest.snapshots[result.source_sha256]
    assert result.run_id == 3
    assert len(snapshot['channels']) == 4
    source = {(r['sensor_group'], r['source'], r['reference_frame'], r['channel'], r['frame_number'], r['name'], r['component']): r
              for r in rows if r['run_id'] == 3}
    for artifact in manifest.artifacts.values():
        description = snapshot['channels'][artifact.details['context_key']]
        context = description['context']
        with (result.manifest_path.parent / artifact.filename).open(encoding='utf-8-sig', newline='') as stream:
            parsed = list(csv.DictReader(stream))
        assert len(parsed) == artifact.rows
        if context['static']:
            assert description['shape'] == [1, 1]
            assert float(next(iter(parsed[0].values()))) == 12.345678901234567
            continue
        if context['channel'] == 'RAW_KEYPOINTS_3D':
            assert description['components'] == ['x', 'y', 'z']
        for row in parsed:
            for heading in artifact.columns[2:]:
                name, component = heading.rsplit('.', 1)
                column = dict(header=heading, name=name, component=component,
                    units=description['units'][description['components'].index(component)])
                key = tuple(context[k] for k in ('sensor_group', 'source', 'reference_frame', 'channel'))
                expected = source.get((*key, int(row['frame_number']), column['name'], column['component']))
                value = row[column['header']]
                if expected is None:
                    assert value == ''
                else:
                    assert float(row['timestamp_s']) == expected['timestamp_s']
                    assert column['units'] == expected['units']
                    assert value == 'NaN' if expected['value'] is None else float(value) == expected['value']
    assert structure.data_parquet_path.read_bytes() == original


def test_selection_replacement_retention_and_failure(scientific_recording, monkeypatch):
    structure, _ = scientific_recording
    first = export(structure)
    with recording_view(structure.data_parquet_path) as view:
        channel = arrays.available_channels(view.metadata.runs[3])[0][0]
    original = {path: path.read_bytes() for path in first.files}
    selected = export(structure, wide_csv=(channel,))
    assert len(selected.files) == 1
    assert all(path.read_bytes() == original[path] for path in first.files if path not in selected.files)
    retained = export(structure, wide_csv=(channel,), run_id=0, keep=True)
    with pytest.raises(FileExistsError):
        export(structure, run_id=0, keep=True)
    before = {p: p.read_bytes() for p in (*selected.files, selected.manifest_path, *retained.files)}
    def fail(*args, **kwargs):
        raise OSError('Disk full')
    monkeypatch.setattr(wide_csv, 'validate_table', fail)
    with pytest.raises(OSError, match='Disk full'):
        export(structure)
    assert all(p.read_bytes() == contents for p, contents in before.items())
    assert not list(structure.exports_dir.glob('.staging-*'))


def test_cancel_duplicates_unknown_and_stale(scientific_recording):
    structure, _ = scientific_recording
    for options in (dict(expected_revision='stale'), dict(run_id=99), dict(wide_csv=())):
        with pytest.raises(ValueError):
            export(structure, **options)
    with pytest.raises(CancelledError):
        wide_csv.export_scientific(structure=structure, request=ScientificExportRequest(formats=('wide_csv',), data=('RAW_KEYPOINTS_3D',)), cancelled=lambda: True)
    table = pq.read_table(structure.data_parquet_path)
    pq.write_table(pa.concat_tables([table, table]), structure.data_parquet_path)
    with pytest.raises(ValueError, match='Duplicate'):
        export(structure)
    assert not list(structure.exports_dir.glob('*.wide.csv'))


def test_partial_publication_recovers(scientific_recording, monkeypatch):
    from freemocap.core.recording.exports.tall_csv import recover_tall_export
    structure, _ = scientific_recording
    replace = publication.os.replace
    def fail(source, target):
        if str(target).endswith('_recording_info.json'):
            raise OSError('publication interrupted')
        return replace(source, target)
    monkeypatch.setattr(publication.os, 'replace', fail)
    with pytest.raises(OSError):
        export(structure)
    monkeypatch.setattr(publication.os, 'replace', replace)
    recover_tall_export(structure=structure, retained_run_id=3)
    assert len(publication.verified_manifest(structure.exports_dir / 'run-3' / 'recording.run-3_recording_info.json').artifacts) == 4


def test_empty_context_and_ordered_array_shape(scientific_recording, tmp_path):
    structure, _ = scientific_recording
    with recording_view(structure.data_parquet_path) as view:
        for item, shape in zip(arrays.available_channels(view.metadata.runs[3]), [(2, 2, 3), (2, 1, 4), (2, 1, 1), (1, 1)], strict=True):
            with arrays.ordered_arrays(view, 3, item, scratch=tmp_path) as data:
                assert data.values.shape == shape
                if item[0].channel == 'RAW_KEYPOINTS_3D':
                    assert data.present[0, 0, 2] and np.isnan(data.values[0, 0, 2])
                    assert not data.present[1, 1, 2] and np.isnan(data.values[1, 1, 2])
    table = pq.read_table(structure.data_parquet_path)
    pq.write_table(table.slice(0, 0), structure.data_parquet_path)
    result = export(structure)
    manifest = publication.verified_manifest(result.manifest_path)
    assert [a.rows for a in manifest.artifacts.values()] == [0, 0, 0, 1]


def test_disk_arrays_close_and_cancel_during_generation_preserves_outputs(scientific_recording, monkeypatch, tmp_path):
    structure, _ = scientific_recording
    monkeypatch.setattr(arrays, 'MAX_RESIDENT_ARRAY_BYTES', 1)
    with recording_view(structure.data_parquet_path) as view:
        item = arrays.available_channels(view.metadata.runs[3])[0]
        with arrays.ordered_arrays(view, 3, item, scratch=tmp_path) as data:
            assert isinstance(data.values, np.memmap)
            assert data.values.shape == (2, 2, 3)
    assert not list(tmp_path.glob('arrays-*'))
    result = export(structure)
    before = {p: p.read_bytes() for p in (*result.files, result.manifest_path)}
    stopped = False
    validate = wide_csv.validate_table
    def cancel_after_first_table(*args):
        nonlocal stopped
        validate(*args)
        stopped = True
    monkeypatch.setattr(wide_csv, 'validate_table', cancel_after_first_table)
    with pytest.raises(CancelledError):
        wide_csv.export_scientific(structure=structure, request=ScientificExportRequest(formats=('wide_csv',), data=('RAW_KEYPOINTS_3D',)), cancelled=lambda: stopped)
    assert all(p.read_bytes() == content for p, content in before.items())
    assert not list(structure.exports_dir.glob('.staging-*'))


def test_replacement_keeps_one_source_snapshot(scientific_recording):
    from freemocap.core.recording.parquet_storage.shared_file import replace_recording_file
    structure, _ = scientific_recording
    path = structure.data_parquet_path
    before = publication.digest(path)
    table = pq.read_table(path)
    metadata = dict(table.schema.metadata)
    descriptor = json.loads(metadata[DESCRIPTOR_KEY])
    descriptor['recording_info']['replacement'] = True
    metadata[DESCRIPTOR_KEY] = json.dumps(descriptor).encode()
    replacement = path.with_suffix('.replacement')
    pq.write_table(table.replace_schema_metadata(metadata), replacement)
    def replace(*_):
        if replacement.exists():
            replace_recording_file(source=replacement, destination=path)
    result = wide_csv.export_scientific(structure=structure, request=ScientificExportRequest(formats=('wide_csv',), data=('RAW_KEYPOINTS_3D',)), progress=replace)
    assert result.source_sha256 == before != publication.digest(path)
    snapshot = publication.verified_manifest(result.manifest_path).snapshots[before]
    assert snapshot['revision'] == result.source_revision
    assert 'recording_descriptor' not in snapshot


def test_readable_names_and_compact_metadata(scientific_recording):
    structure, _ = scientific_recording
    result = export(structure)
    assert {p.name for p in result.files} == {
        'recording.run-3.3d_keypoints_raw--points.csv', 'recording.run-3.rotations_world--points.csv',
        'recording.run-3.timestamps--clock.csv', 'recording.run-3.segment_lengths--points.csv'}
    manifest = publication.verified_manifest(result.manifest_path)
    assert manifest.version == 3
    assert all('value_columns' not in a.details for a in manifest.artifacts.values())
    snapshot = manifest.snapshots[result.source_sha256]
    assert snapshot['reference_frames'] == {'world': {'units': 'mm'}}
    assert 'recording_descriptor' not in snapshot


def test_filename_collisions_are_safe_and_independent_of_selection(scientific_recording):
    structure, _ = scientific_recording
    with recording_view(structure.data_parquet_path) as view:
        run = view.metadata.runs[3]
        original = run.channels[0]
        run = run.model_copy(update={'channels': (
            original.model_copy(update={'source': 'model:Case'}),
            original.model_copy(update={'source': 'model:case'}),
            original.model_copy(update={'source': 'model:../../case'}),
        )})
        names = wide_csv.table_names(run)
        assert len({n.casefold() for n in names.values()}) == len(names)
        assert all('/' not in n and '\\' not in n and '..' not in n for n in names.values())
        assert names == wide_csv.table_names(run.model_copy(update={'channels': tuple(reversed(run.channels))}))


def test_recovery_ignores_old_deletion_instructions(tmp_path):
    import json
    from freemocap.core.recording.exports import publication
    saved = tmp_path / 'existing-result.csv'
    saved.write_bytes(b'original scientific result')
    staging = tmp_path / '.staging-test'
    staging.mkdir()
    journal = tmp_path / '.publication.json'
    journal.write_text(json.dumps(dict(version=1, staging=staging.name, files=[],
        remove=[dict(filename=saved.name, sha256=publication.digest(saved))])))
    publication.finish_publication(tmp_path)
    assert saved.read_bytes() == b'original scientific result'
    assert not journal.exists()
    assert not staging.exists()
