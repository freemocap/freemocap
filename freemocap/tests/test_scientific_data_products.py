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
    assert all(p.parent.name == ('npy' if p.suffix == '.npy' else 'csv') for p in result.files if p.suffix != '.npz')
    assert not list(structure.exports_dir.glob('*.csv'))
    assert not list(structure.exports_dir.glob('*.npy'))
    manifest = verified_manifest(result.manifest_path)
    assert len(list((structure.exports_dir / 'npy').glob('*.frames.npy'))) == 1
    assert len(list((structure.exports_dir / 'npy').glob('*.timestamps.npy'))) == 1
    snapshot = manifest.snapshots[source_hash]
    assert len(snapshot['channels']) == 3
    assert any('2d_overlay--' in p.name and p.name.endswith('--camera.csv') for p in result.files)
    info = json.loads(structure.recording_info_path.read_text())
    assert all(info[key] == value for key, value in capture.items())
    assert info['processed']['parquet_sha256'] == source_hash
    assert info['processed']['export_inventories'] == ['exports/recording_recording_info.json']
    source = {(r['channel'], r['source'], r['reference_frame'], r['frame_number'], r['name'], r['component']): r
              for r in pq.read_table(structure.data_parquet_path).to_pylist()}
    assert not list(structure.exports_dir.rglob('*.present.npy'))
    archive_path = next(p for p in result.files if p.suffix == '.npz')
    with ZipFile(archive_path) as zipped:
        assert not any(name.endswith('.present.npy') for name in zipped.namelist())
        embedded = json.loads(zipped.read('recording_info.json'))
        assert embedded['channels'] == snapshot['channels']
    with np.load(archive_path, allow_pickle=False) as archive:
        for context_key, description in snapshot['channels'].items():
            context = description['context']
            members = {a.details['role']: result.manifest_path.parent / a.filename
                       for a in manifest.artifacts.values() if a.format == 'npy' and a.details['context_key'] in (None, context_key)}
            loaded = {role: np.load(path, allow_pickle=False) for role, path in members.items()}
            for role, value in loaded.items():
                np.testing.assert_array_equal(value, archive[f"{description['numpy_key']}.values" if role == "values" else role])
            assert loaded['values'].shape == tuple(description['shape'])
            if context['channel'] == 'SEGMENT_POSES':
                assert description['components'] == ['x', 'y', 'z', 'qw', 'qx', 'qy', 'qz']
            if context['channel'] == 'OVERLAY_2D':
                assert description['components'] == ['x', 'y', 'confidence']
                assert description['source_components'] == ['x', 'y', 'visibility']
                assert description['numpy_key'] == f"2d_overlay--{context['source'].split(':', 1)[-1]}--camera"
                assert members['values'].name == f"recording.{description['numpy_key']}.npy"
            for i, frame in enumerate(loaded['frames']):
                for j, name in enumerate(description['names']):
                    for k, component in enumerate(description['components']):
                        channel = context['channel']
                        if channel == 'SEGMENT_POSES':
                            channel = 'ROTATIONS_WORLD' if component.startswith('q') else 'SEGMENT_ORIGINS'
                            component = component.removeprefix('q')
                        if channel == 'OVERLAY_2D' and component == 'confidence':
                            component = 'visibility'
                        row = source.get((channel, context['source'], context['reference_frame'], int(frame), name, component))
                        value = loaded['values'][i, j, k]
                        if row is None or row['value'] is None:
                            assert np.isnan(value)
                        else:
                            assert value == row['value']
                            assert loaded['timestamps'][i] == row['timestamp_s']
            for a in manifest.artifacts.values():
                if a.format != 'wide_csv' or a.details['context_key'] != context_key:
                    continue
                with (result.manifest_path.parent / a.filename).open(encoding='utf-8-sig', newline='') as stream:
                    for i, row in enumerate(csv.DictReader(stream)):
                        for heading, value in row.items():
                            if heading in ('frame_number', 'timestamp_s'):
                                continue
                            name, component = heading.rsplit('.', 1)
                            j, k = description['names'].index(name), description['components'].index(component)
                            expected = loaded['values'][i, j, k]
                            assert value in ('', 'NaN') if np.isnan(expected) else float(value) == expected
    assert digest(structure.data_parquet_path) == source_hash
    # Replacing only CSV leaves the existing NumPy files bound to their original data.
    numpy_before = {p: p.read_bytes() for p in result.files if p.suffix in ('.npy', '.npz')}
    smaller = export_scientific(structure=structure, request=ScientificExportRequest(formats=('wide_csv',)))
    assert all(p.read_bytes() == content for p, content in numpy_before.items())
    assert len(list((structure.exports_dir / 'csv').glob('*.csv'))) == 1
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
    assert not old_path.exists() and not old_csv.exists()
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
    assert len(organize_exports(structure)) == 4
    assert organize_exports(structure) == []
    manifest = verified_manifest(result.manifest_path)
    for artifact in manifest.artifacts.values():
        path = result.manifest_path.parent / artifact.filename
        assert digest(path) == original_hashes[path.name]
        assert path.parent.name == ('csv' if path.suffix == '.csv' else 'npy' if path.suffix == '.npy' else 'exports')


@pytest.mark.parametrize('name', ['../outside.csv', 'CSV/../outside.csv', '/absolute.csv', 'CSV//file.csv',
                                 'NPY/../../outside.npy', 'CSV\\file.csv', 'CSV/file.csv:stream', 'CSV /file.csv'])
def test_nested_artifact_paths_cannot_escape(name):
    from freemocap.core.recording.exports.publication import ExportArtifact
    with pytest.raises(ValueError):
        ExportArtifact.safe_filename(name)


@pytest.mark.parametrize('mismatch', ['length', 'frame_number', 'timestamp'])
def test_shared_timeline_rejects_mismatch_before_publication(scientific_recording, mismatch):
    from freemocap.core.recording.exports.arrays import available_channels
    from freemocap.core.recording.parquet_storage.recording_view import recording_view
    structure, _ = scientific_recording
    with recording_view(structure.data_parquet_path) as view:
        contexts = tuple(item[0] for item in available_channels(view.metadata.runs[3])[:2])
    request = ScientificExportRequest(formats=('npy', 'npz'), wide_csv=contexts)
    before = export_scientific(structure=structure, request=request)
    saved = {p: p.read_bytes() for p in (*before.files, before.manifest_path)}
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
    with pytest.raises(ValueError, match='completeness check failed'):
        export_scientific(structure=structure, request=request)
    assert all(p.read_bytes() == data for p, data in saved.items())
    assert not list(structure.exports_dir.glob('.staging-*'))


def test_shared_timestamps_accept_only_float64_roundoff():
    from freemocap.core.recording.exports.wide_csv import matching_timestamps
    assert matching_timestamps(np.array([0., 0.1]), np.array([0., 0.10000000000000002]))
    assert not matching_timestamps(np.array([0., 0.1]), np.array([0., 0.100001]))
    assert not matching_timestamps(np.array([0.]), np.array([0., 0.1]))
