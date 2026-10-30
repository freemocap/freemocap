"""User selections, combined segment poses and all three file formats."""
import csv
import json
from zipfile import ZipFile

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from freemocap.core.recording.exports.requests import ScientificExportRequest
from freemocap.core.recording.exports.wide_csv import export_scientific
from freemocap.core.recording.exports.publication import verified_manifest, digest
from freemocap.core.recording.result_processing.observation_publication import publish_posthoc_observations
from freemocap.system.recording_structure.recording_structure import RecordingStructure
from freemocap.tests.test_wide_csv_export import scientific_recording  # noqa: F401
from skellyforge.core.data_tensors import read_numpy_dataset
from freemocap.tests.numpy_export_assertions import display_projection

pytest_plugins = ('freemocap.tests.test_reconstruction_checkpoints',)


def test_defaults_numpy_segments_and_capture_preservation(publication, tmp_path):
    structure = RecordingStructure(base_directory=tmp_path, recording_name='recording')
    structure.full_path.mkdir(exist_ok=True)
    capture = {'camera_configs': {'camera': {'exposure': -5}}, 'unknown_user_field': 42}
    structure.recording_info_path.write_text(json.dumps(capture))
    publish_posthoc_observations(publication)
    source_hash = digest(structure.data_parquet_path)
    default = export_scientific(structure=structure, request=ScientificExportRequest(formats=('wide_csv',)))
    assert len(default.files) == 1
    assert default.files[0].parent.name == 'csv'
    assert '3d_landmarks' in default.files[0].name
    assert not list(structure.full_path.rglob('*.yaml'))
    assert not structure.output_dir.exists()
    result = export_scientific(structure=structure, request=ScientificExportRequest(
        formats=('wide_csv', 'npy', 'npz'), data=('LANDMARKS_3D', 'SEGMENT_POSES', 'OVERLAY_2D')))
    assert all(p.parent.name == ('npy' if p.suffix in ('.npy', '.json') else 'csv')
               for p in result.files if p.suffix != '.npz')
    assert not list(structure.exports_dir.glob('*.csv'))
    assert not list(structure.exports_dir.glob('*.npy'))
    manifest = verified_manifest(result.manifest_path)
    snapshot = manifest.snapshots[source_hash]
    assert set(snapshot['numpy_datasets']) == {'npy', 'npz'}
    assert any('2d_overlay--' in p.name and p.name.endswith('--camera.csv') for p in result.files)
    info = json.loads(structure.recording_info_path.read_text())
    assert all(info[key] == value for key, value in capture.items())
    assert info['processed']['parquet_sha256'] == source_hash
    assert info['processed']['export_inventories'] == ['exports/recording_recording_info.json']
    source = {(r['channel'], r['source'], r['reference_frame'], r['frame_number'], r['name'], r['component']): r
              for r in pq.read_table(structure.data_parquet_path).to_pylist()}
    dataset = read_numpy_dataset(structure.exports_dir / 'npy')
    archive_path = next(p for p in result.files if p.suffix == '.npz')
    archived = read_numpy_dataset(archive_path)
    with ZipFile(archive_path) as zipped:
        embedded = json.loads(zipped.read('dataset.json'))
        assert embedded['format'] == 'skellyforge.numpy_dataset'
        assert 'recording_info.json' not in zipped.namelist()
    assert dataset.channel_identities == archived.channel_identities
    for actual, expected in zip((*dataset.time_series, *dataset.static_tensors),
                                (*archived.time_series, *archived.static_tensors), strict=True):
        actual_tensor = actual.data_tensor if hasattr(actual, 'data_tensor') else actual
        expected_tensor = expected.data_tensor if hasattr(expected, 'data_tensor') else expected
        assert actual_tensor.tensor_layout == expected_tensor.tensor_layout
        np.testing.assert_array_equal(actual_tensor.data_values, expected_tensor.data_values)
        np.testing.assert_array_equal(actual_tensor.companion_values('entry_presence'), expected_tensor.companion_values('entry_presence'))
    for series in dataset.time_series:
        tensor = series.data_tensor
        layout = tensor.tensor_layout
        names = layout.axes[layout.axis_index('entity_identity')].identifiers
        components = layout.axes[layout.axis_index('component_identity')].identifiers
        assert layout.channel_kind != 'SEGMENT_POSES'
        if layout.channel_kind == 'OVERLAY_2D':
            assert 'visibility' in components and 'confidence' not in components
        for i, frame in enumerate(series.sample_timing.sample_ids):
            for j, name in enumerate(names):
                for k, component in enumerate(components):
                    row = source.get((layout.channel_kind, layout.source_identity.source_id, layout.reference_id, int(frame), name, component))
                    value = tensor.data_values[i, j, k]
                    assert tensor.companion_values('entry_presence')[i, j, k] == (row is not None)
                    if row is None or row['value'] is None:
                        assert np.isnan(value)
                    else:
                        assert value == row['value']
                        assert series.sample_timing.timestamps_s[i] == row['timestamp_s']
    csv_contexts = set()
    for artifact in manifest.artifacts.values():
        if artifact.format != 'wide_csv':
            continue
        context_key = artifact.details['context_key']
        csv_contexts.add(context_key)
        description = snapshot['channels'][context_key]
        projected = display_projection(dataset, description['context'])
        assert list(projected.components) == description['components']
        assert list(projected.names) == description['names']
        with (result.manifest_path.parent / artifact.filename).open(encoding='utf-8-sig', newline='') as stream:
            for i, row in enumerate(csv.DictReader(stream)):
                assert int(row['frame_number']) == projected.frames[i]
                assert float(row['timestamp_s']) == projected.timestamps[i]
                for heading, value in row.items():
                    if heading in ('frame_number', 'timestamp_s'):
                        continue
                    name, component = heading.rsplit('.', 1)
                    j, k = projected.names.index(name), projected.components.index(component)
                    expected = projected.values[i, j, k]
                    assert value in ('', 'NaN') if np.isnan(expected) else float(value) == expected
    assert len(csv_contexts) == 3
    assert digest(structure.data_parquet_path) == source_hash
    # Replacing only CSV leaves the existing NumPy files bound to their original data.
    numpy_before = {p: p.read_bytes() for p in result.files if p.suffix in ('.npy', '.npz')}
    smaller = export_scientific(structure=structure, request=ScientificExportRequest(formats=('wide_csv',)))
    assert all(p.read_bytes() == content for p, content in numpy_before.items())
    assert sum(a.format == 'wide_csv' for a in verified_manifest(smaller.manifest_path).artifacts.values()) == 1
    assert len(list((structure.exports_dir / 'csv').glob('*.csv'))) == 3
    assert {a.format for a in verified_manifest(smaller.manifest_path).artifacts.values()} == {'wide_csv', 'npy', 'npz'}
    kept = export_scientific(structure=structure, request=ScientificExportRequest(formats=('npz',), keep=True))
    assert kept.files[0].parent.name == 'run-0' and '.run-0.' in kept.files[0].name
    added = export_scientific(structure=structure, request=ScientificExportRequest(formats=('wide_csv',), keep=True))
    assert {a.format for a in verified_manifest(added.manifest_path).artifacts.values()} == {'npz', 'wide_csv'}
    with pytest.raises(FileExistsError):
        export_scientific(structure=structure, request=ScientificExportRequest(formats=('npz',), keep=True))


def test_legacy_wide_inventory_replacement_preserves_unknown_files(publication, tmp_path):
    structure = RecordingStructure(base_directory=tmp_path, recording_name='recording')
    publish_posthoc_observations(publication)
    result = export_scientific(structure=structure, request=ScientificExportRequest(formats=('wide_csv',)))
    old_path = structure.exports_dir / 'recording.wide.metadata.json'
    payload = json.loads(result.manifest_path.read_text())
    old_csv = structure.exports_dir / 'recording.landmarks.deadbeef.r1.c1.wide.csv'
    result.files[0].rename(old_csv)
    artifact = payload['artifacts'].pop(result.files[0].relative_to(structure.exports_dir).as_posix())
    artifact['filename'] = old_csv.name
    payload['artifacts'][old_csv.name] = artifact
    payload['version'] = 2
    old_path.write_text(json.dumps(payload))
    result.manifest_path.unlink()
    note = structure.exports_dir / 'my-analysis.txt'
    note.write_text('keep this')
    updated = export_scientific(structure=structure, request=ScientificExportRequest(formats=('wide_csv',)))
    assert old_path.read_text() == json.dumps(payload)
    assert digest(old_csv) == artifact['sha256']
    assert note.read_text() == 'keep this'
    assert verified_manifest(updated.manifest_path).version == 3


def test_organize_existing_files_preserves_bytes_and_updates_inventory(publication, tmp_path):
    from freemocap.core.recording.exports.organize import organize_exports
    structure = RecordingStructure(base_directory=tmp_path, recording_name='recording')
    publish_posthoc_observations(publication)
    result = export_scientific(structure=structure, request=ScientificExportRequest(formats=('wide_csv', 'npy', 'npz')))
    payload = json.loads(result.manifest_path.read_text())
    flattened = {}
    original_hashes = {}
    for name, artifact in payload['artifacts'].items():
        path = result.manifest_path.parent / name
        original_hashes[path.name] = digest(path)
        if '/' in name:
            path.rename(path.parent.parent / path.name)
        artifact['filename'] = path.name
        flattened[path.name] = artifact
    payload['artifacts'] = flattened
    result.manifest_path.write_text(json.dumps(payload))
    assert len(organize_exports(structure)) == sum(item['format'] in ('wide_csv', 'npy') for item in flattened.values())
    assert organize_exports(structure) == []
    manifest = verified_manifest(result.manifest_path)
    for artifact in manifest.artifacts.values():
        path = result.manifest_path.parent / artifact.filename
        assert digest(path) == original_hashes[path.name]
        assert path.parent.name == ('npy' if artifact.format == 'npy' else 'csv' if artifact.format.endswith('csv') else 'exports')


@pytest.mark.parametrize('name', ['../outside.csv', 'CSV/../outside.csv', '/absolute.csv', 'CSV//file.csv',
                                 'NPY/../../outside.npy', 'CSV\\file.csv', 'CSV/file.csv:stream', 'CSV /file.csv'])
def test_nested_artifact_paths_cannot_escape(name):
    from freemocap.core.recording.exports.publication import ExportArtifact
    with pytest.raises(ValueError):
        ExportArtifact.safe_filename(name)


@pytest.mark.parametrize('mismatch', ['length', 'frame_number', 'timestamp'])
def test_independent_channel_timing_is_preserved_without_alignment(scientific_recording, mismatch):
    from freemocap.core.recording.exports.arrays import available_channels
    from freemocap.core.recording.parquet_storage.recording_view import recording_view
    structure, _ = scientific_recording
    with recording_view(structure.data_parquet_path) as view:
        contexts = tuple(item[0] for item in available_channels(view.metadata.runs[3])[:2])
    request = ScientificExportRequest(formats=('npy', 'npz'), wide_csv=contexts)
    before = export_scientific(structure=structure, request=request)
    table = pq.read_table(structure.data_parquet_path)
    rows = table.to_pylist()
    for row in rows:
        if row['run_id'] == 3 and row['channel'] == 'ROTATIONS_WORLD' and row['frame_number'] == 42:
            if mismatch == 'frame_number':
                row['frame_number'] = 43
            elif mismatch == 'timestamp':
                row['timestamp_s'] += 0.1
    if mismatch == 'length':
        rows = [r for r in rows if not (r['run_id'] == 3 and r['channel'] == 'ROTATIONS_WORLD' and r['frame_number'] == 42)]
    pq.write_table(pa.Table.from_pylist(rows, schema=table.schema), structure.data_parquet_path)
    result = export_scientific(structure=structure, request=request)
    dataset = read_numpy_dataset(result.manifest_path.parent / 'npy')
    first, second = dataset.time_series
    np.testing.assert_array_equal(first.sample_timing.sample_ids, [10, 42])
    if mismatch == 'length':
        np.testing.assert_array_equal(second.sample_timing.sample_ids, [10])
    elif mismatch == 'frame_number':
        np.testing.assert_array_equal(second.sample_timing.sample_ids, [10, 43])
    else:
        assert second.sample_timing.timestamps_s[-1] == first.sample_timing.timestamps_s[-1] + 0.1
    assert first.sample_timing.timeline_id != second.sample_timing.timeline_id
    assert result.source_sha256 != before.source_sha256
    assert not list(structure.exports_dir.glob('.staging-*'))
