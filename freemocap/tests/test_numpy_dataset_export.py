"""Core publishes selected runtime tensors through Forge's NumPy dataset format."""
from concurrent.futures import CancelledError
from contextlib import contextmanager
from dataclasses import replace
import json
import weakref

import numpy as np
import pyarrow.parquet as pq
import pytest

from skellyforge.core.data_tensors import (
    CompanionTensor, DefinitionDocument, RecordingDataset, ScientificProvenance,
    TensorLayout, TimeSeries, read_numpy_dataset,
)
from freemocap.core.recording.exports import arrays, numpy_dataset, publication, wide_csv
from freemocap.core.recording.exports.requests import ScientificExportRequest
from freemocap.core.recording.parquet_storage.recording_view import recording_view
from freemocap.core.recording.sample_encoding.arrow_schema import DESCRIPTOR_KEY
from freemocap.tests.test_wide_csv_export import scientific_recording  # noqa: F401


def selected_request(structure, *, all_channels=True, formats=('npy', 'npz'), run_id=3, keep=False):
    with recording_view(structure.data_parquet_path) as view:
        choices = tuple(item[0] for item in arrays.available_channels(view.metadata.runs[run_id]))
    return ScientificExportRequest(formats=formats, wide_csv=choices if all_channels else choices[:1], run_id=run_id, keep=keep)


def exported_dataset(result, output_format='npy'):
    manifest = publication.verified_manifest(result.manifest_path)
    numpy_info = manifest.snapshots[result.source_sha256]['numpy_datasets'][output_format]
    path = result.manifest_path.parent / numpy_info['path']
    return read_numpy_dataset(path)


def test_saved_arrays_preserve_independent_clocks_static_values_and_missingness(scientific_recording, monkeypatch):
    structure, _ = scientific_recording
    original_reader = numpy_dataset.read_channel_arrays
    references = []
    @contextmanager
    def track_channel_storage(*args, **kwargs):
        assert all(reference() is None for reference in references), 'Previous channel storage was retained'
        with original_reader(*args, **kwargs) as data:
            references.append(weakref.ref(data.values))
            yield data
    monkeypatch.setattr(numpy_dataset, 'read_channel_arrays', track_channel_storage)
    monkeypatch.setattr(wide_csv, 'ordered_arrays', lambda *args, **kwargs: pytest.fail('NumPy must not build CSV projection'))
    result = wide_csv.export_scientific(structure=structure, request=selected_request(structure))
    assert all(reference() is None for reference in references)
    npy, npz = exported_dataset(result), exported_dataset(result, 'npz')
    assert npy.channel_identities == npz.channel_identities
    assert len(npy.time_series) == 3 and len(npy.static_tensors) == 1
    assert len(npy.sample_timings) == 3
    for first, second in zip(npy.time_series, npz.time_series, strict=True):
        assert first.data_tensor.tensor_layout == second.data_tensor.tensor_layout
        np.testing.assert_array_equal(first.data_tensor.data_values, second.data_tensor.data_values)
        np.testing.assert_array_equal(first.sample_timing.timestamps_s, second.sample_timing.timestamps_s)
    points = npy.time_series[0]
    assert numpy_dataset.axis_definition(points.data_tensor.tensor_layout, 'component_identity').identifiers == ('z', 'y', 'x')
    presence = points.data_tensor.companion_values('entry_presence')
    assert presence[0, 0, 0] and np.isnan(points.data_tensor.data_values[0, 0, 0])
    assert not presence[1, 1, 0] and np.isnan(points.data_tensor.data_values[1, 1, 0])
    assert 'value_validity' not in {item.metadata_name for item in points.data_tensor.companion_tensors}
    np.testing.assert_array_equal(npy.time_series[2].sample_timing.timestamps_s, points.sample_timing.timestamps_s + 5)
    assert npy.time_series[2].sample_timing.clock_id != points.sample_timing.clock_id
    assert npy.static_tensors[0].data_values.shape == (1, 1)
    assert 'sample_identity' not in {axis.axis_name for axis in npy.static_tensors[0].tensor_layout.axes}
    assert npy.static_tensors[0].data_values[0, 0] == 12.345678901234567
    assert result.timings_s['npy_write_and_verify'] > 0


def test_runtime_dataset_values_go_directly_to_writer(scientific_recording, monkeypatch, tmp_path):
    structure, _ = scientific_recording
    request = selected_request(structure, all_channels=False)
    with recording_view(structure.data_parquet_path) as view:
        run_id, selected = arrays.resolve_selection(view, request)
        with numpy_dataset.saved_channel_tensor(view, run_id, selected[0], source_hash=view.content_sha256(), scratch=tmp_path) as original:
            values = (original.data_tensor.data_values + 100).astype('>f4')
            values[0, 0, 1] = -0.
            validity = np.isfinite(values) & original.data_tensor.companion_values('entry_presence')
            validity[-1, 0, -1] = False  # Explicitly invalid despite a finite saved value.
            validity_layout = original.data_tensor.companion_tensors[0].tensor_layout
            confidence_layout = TensorLayout(tuple(axis for axis in original.data_tensor.tensor_layout.axes
                if axis.axis_name != 'component_identity'), np.float32)
            companions = (*original.data_tensor.companion_tensors,
                CompanionTensor('value_validity', validity, validity_layout),
                CompanionTensor('confidence_scores', np.full(confidence_layout.shape, .75, dtype=np.float32), confidence_layout))
            tensor = replace(original.data_tensor, data_values=values,
                tensor_layout=replace(original.data_tensor.tensor_layout, dtype=values.dtype),
                scientific_provenance=ScientificProvenance('runtime_prediction', 'runtime_test', ('input_fixture',)),
                companion_tensors=companions).immutable_copy()
            series = TimeSeries(tensor, original.sample_timing)
        document = DefinitionDocument('runtime:fixture', '{ "meaning": "scientific input", "weights": [0.25, 0.75] }')
        dataset = RecordingDataset(view.metadata.recording_id, run_id, (series,), definition_documents=(document,))
    monkeypatch.setattr(numpy_dataset, 'read_channel_arrays', lambda *args, **kwargs: pytest.fail('Runtime NumPy must not reread Parquet numbers'))
    result = wide_csv.export_scientific(structure=structure, request=request, runtime_dataset=dataset)
    for output_format in ('npy', 'npz'):
        restored = exported_dataset(result, output_format)
        actual = restored.time_series[0]
        assert actual.data_tensor.data_values.dtype.str == '>f4'
        assert actual.data_tensor.tensor_layout == tensor.tensor_layout
        assert actual.data_tensor.scientific_provenance == tensor.scientific_provenance
        np.testing.assert_array_equal(actual.data_tensor.data_values, tensor.data_values)
        assert np.signbit(actual.data_tensor.data_values[0, 0, 1])
        for found, expected in zip(actual.data_tensor.companion_tensors, tensor.companion_tensors, strict=True):
            assert found.metadata_name == expected.metadata_name
            assert found.tensor_layout == expected.tensor_layout
            assert found.data_values.dtype.str == expected.data_values.dtype.str
            np.testing.assert_array_equal(found.data_values, expected.data_values)
        assert document in restored.definition_documents
        assert actual.sample_timing.timeline_id == series.sample_timing.timeline_id
        assert actual.sample_timing.clock_id == series.sample_timing.clock_id
        assert actual.sample_timing.clock_epoch == series.sample_timing.clock_epoch
        assert actual.sample_timing.source_identity == series.sample_timing.source_identity
        np.testing.assert_array_equal(actual.sample_timing.sample_ids, series.sample_timing.sample_ids)
        np.testing.assert_array_equal(actual.sample_timing.timestamps_s, series.sample_timing.timestamps_s)
    manifest = publication.verified_manifest(result.manifest_path)
    assert manifest.snapshots[result.source_sha256]['numpy_datasets']['npy']['value_origin'] == 'caller_supplied_runtime_dataset'
    for bad_dataset in (replace(dataset, run_id=0), replace(dataset, recording_id='another'), replace(dataset, time_series=())):
        with pytest.raises(ValueError, match='Runtime dataset'):
            wide_csv.export_scientific(structure=structure, request=request, runtime_dataset=bad_dataset)
    with pytest.raises(ValueError, match='only NPY/NPZ'):
        wide_csv.export_scientific(structure=structure, request=request.model_copy(update={'formats': ('npy', 'wide_csv')}), runtime_dataset=dataset)


@pytest.mark.parametrize('output_format', ['npy', 'npz'])
def test_publication_rejects_payload_changed_after_artifact_hash(scientific_recording, monkeypatch, output_format):
    structure, _ = scientific_recording
    original_publish = wide_csv.publish
    saved = {}

    def tamper_before_publication(directory, staging, manifest_name, manifest, filenames, keep, **kwargs):
        name = next(name for name in filenames if name.endswith('_values.npy' if output_format == 'npy' else '.npz'))
        pending = staging / name
        payload = pending.read_bytes()
        saved.update(directory=directory, pending=pending, filename=name, payload=payload,
                     expected_hash=manifest.artifacts[name].sha256, manifest_name=manifest_name)
        pending.write_bytes(payload[:-1] + bytes([payload[-1] ^ 1]))
        return original_publish(directory, staging, manifest_name, manifest, filenames, keep, **kwargs)

    monkeypatch.setattr(wide_csv, 'publish', tamper_before_publication)
    with pytest.raises(ValueError, match='Staged export changed'):
        wide_csv.export_scientific(structure=structure,
            request=selected_request(structure, all_channels=False, formats=(output_format,)))
    assert not (saved['directory'] / saved['filename']).exists()
    journal = json.loads((saved['directory'] / '.publication.json').read_text())
    entry = next(entry for entry in journal['files'] if entry['filename'] == saved['filename'])
    assert entry['sha256'] == saved['expected_hash']
    # Recovery accepts only restoration of the originally validated bytes.
    saved['pending'].write_bytes(saved['payload'])
    publication.finish_publication(saved['directory'])
    publication.verified_manifest(saved['directory'] / saved['manifest_name'])


def test_same_run_replaces_obsolete_numpy_members_and_preserves_unselected_formats(scientific_recording):
    structure, _ = scientific_recording
    first = wide_csv.export_scientific(structure=structure, request=selected_request(structure))
    first_manifest = publication.verified_manifest(first.manifest_path)
    first_members = {name for name, item in first_manifest.artifacts.items() if item.format == 'npy'}
    archive = next(path for path in first.files if path.suffix == '.npz')
    archive_bytes = archive.read_bytes()
    result = wide_csv.export_scientific(structure=structure, request=selected_request(structure, all_channels=False, formats=('npy',)))
    assert result.manifest_path == first.manifest_path
    current = publication.verified_manifest(result.manifest_path)
    current_members = {name for name, item in current.artifacts.items() if item.format == 'npy'}
    assert first_members - current_members
    assert all(not (result.manifest_path.parent / name).exists() for name in first_members - current_members)
    assert archive.read_bytes() == archive_bytes
    assert current.snapshots[result.source_sha256]['numpy_datasets']['npz'] == first_manifest.snapshots[first.source_sha256]['numpy_datasets']['npz']
    assert len(exported_dataset(result).time_series) == 1
    assert len(exported_dataset(result, 'npz').time_series) == 3
    assert (result.manifest_path.parent / 'npy/dataset.json').is_file()
    assert not list((result.manifest_path.parent / 'npy').glob('dataset-*'))
    numpy_bytes = {path: path.read_bytes() for path in result.files}
    old_descriptor = current.snapshots[result.source_sha256]['numpy_datasets']['npy']
    inverse = wide_csv.export_scientific(structure=structure, request=selected_request(structure, all_channels=False, formats=('npz',)))
    assert all(path.read_bytes() == content for path, content in numpy_bytes.items())
    assert publication.verified_manifest(inverse.manifest_path).snapshots[inverse.source_sha256]['numpy_datasets']['npy'] == old_descriptor


def test_explicit_run_exports_stay_separate_and_keep_refuses_replacement(scientific_recording):
    structure, _ = scientific_recording
    first = wide_csv.export_scientific(structure=structure, request=selected_request(structure, run_id=0, formats=('npy',)))
    first_bytes = {path: path.read_bytes() for path in first.files}
    retained = wide_csv.export_scientific(structure=structure, request=selected_request(structure, run_id=3, formats=('npy',), keep=True))
    assert first.manifest_path.parent == structure.exports_dir
    assert retained.manifest_path.parent == structure.exports_dir / 'run-3'
    assert all(path.read_bytes() == content for path, content in first_bytes.items())
    with pytest.raises(FileExistsError):
        wide_csv.export_scientific(structure=structure, request=selected_request(structure, run_id=3, formats=('npy',), keep=True))


def test_unmanaged_and_edited_numpy_files_are_preserved(scientific_recording):
    structure, _ = scientific_recording
    result = wide_csv.export_scientific(structure=structure, request=selected_request(structure))
    before = result.manifest_path.read_bytes()
    unknown = result.manifest_path.parent / 'npy/user_values.npy'
    unknown.write_bytes(b'user content')
    with pytest.raises(ValueError, match='Unmanaged file'):
        wide_csv.export_scientific(structure=structure, request=selected_request(structure))
    assert unknown.read_bytes() == b'user content' and result.manifest_path.read_bytes() == before
    unknown.rename(unknown.with_suffix('.preserved'))
    # Keep the unrelated file protected outside the managed NumPy directory.
    unknown.with_suffix('.preserved').rename(result.manifest_path.parent / 'user_values.preserved')
    edited = next(path for path in result.files if path.name.endswith('_values.npy'))
    edited.write_bytes(b'user edited managed array')
    with pytest.raises(ValueError, match='missing or changed'):
        wide_csv.export_scientific(structure=structure, request=selected_request(structure))
    assert edited.read_bytes() == b'user edited managed array'


@pytest.mark.parametrize('edit_obsolete', [False, True])
def test_interrupted_numpy_replacement_recovers_obsolete_cleanup(scientific_recording, monkeypatch, edit_obsolete):
    structure, _ = scientific_recording
    first = wide_csv.export_scientific(structure=structure, request=selected_request(structure))
    original = publication.os.replace
    def interrupt_manifest(source, target):
        if str(target).endswith('_recording_info.json'):
            raise OSError('interrupted publication')
        return original(source, target)
    monkeypatch.setattr(publication.os, 'replace', interrupt_manifest)
    with pytest.raises(OSError, match='interrupted'):
        wide_csv.export_scientific(structure=structure, request=selected_request(structure, all_channels=False))
    journal = first.manifest_path.parent / '.publication.json'
    entries = json.loads(journal.read_text())['obsolete_numpy']
    assert entries
    monkeypatch.setattr(publication.os, 'replace', original)
    if edit_obsolete:
        edited = first.manifest_path.parent / entries[0]['filename']
        edited.write_bytes(b'edited after interruption')
        with pytest.raises(ValueError, match='edited; preserving'):
            publication.finish_publication(first.manifest_path.parent)
        assert edited.read_bytes() == b'edited after interruption'
        assert journal.exists()
        return
    publication.finish_publication(first.manifest_path.parent)
    assert not journal.exists()
    assert all(not (first.manifest_path.parent / item['filename']).exists() for item in entries)
    assert len(exported_dataset(first).time_series) == 1


def test_cancelled_numpy_export_leaves_previous_outputs_unchanged(scientific_recording):
    structure, _ = scientific_recording
    first = wide_csv.export_scientific(structure=structure, request=selected_request(structure))
    before = {path: path.read_bytes() for path in (*first.files, first.manifest_path)}
    stopped = False
    def progress(*args):
        nonlocal stopped
        stopped = True
    with pytest.raises(CancelledError):
        wide_csv.export_scientific(structure=structure, request=selected_request(structure), progress=progress, cancelled=lambda: stopped)
    assert all(path.read_bytes() == content for path, content in before.items())
    assert not list(first.manifest_path.parent.glob('.staging-*'))


def test_scientific_source_settings_retained_execution_configuration_excluded(scientific_recording):
    structure, _ = scientific_recording
    table = pq.read_table(structure.data_parquet_path)
    metadata = dict(table.schema.metadata)
    descriptor = json.loads(metadata[DESCRIPTOR_KEY])
    descriptor['runs']['3']['sources']['points']['definition'].update(
        filter_config={'enabled': False, 'cutoff': 6.0}, execution={'private_backend': 'not scientific'})
    metadata[DESCRIPTOR_KEY] = json.dumps(descriptor).encode()
    pq.write_table(table.replace_schema_metadata(metadata), structure.data_parquet_path)
    result = wide_csv.export_scientific(structure=structure, request=selected_request(structure, all_channels=False))
    documents = {doc.definition_id: json.loads(doc.content_json) for doc in exported_dataset(result).definition_documents}
    definition = documents['source:points']['definition']
    assert definition['filter_config'] == {'enabled': False, 'cutoff': 6.0}
    assert 'execution' not in definition


@pytest.mark.parametrize('updated_format', ['npy', 'npz'])
def test_partial_format_update_prunes_replaced_source_descriptor(scientific_recording, updated_format):
    structure, _ = scientific_recording
    first = wide_csv.export_scientific(structure=structure, request=selected_request(structure))
    original = publication.verified_manifest(first.manifest_path)
    retained_format = 'npz' if updated_format == 'npy' else 'npy'
    retained_files = {first.manifest_path.parent / item.filename: (first.manifest_path.parent / item.filename).read_bytes()
        for item in original.artifacts.values() if item.format == retained_format}
    table = pq.read_table(structure.data_parquet_path)
    metadata = dict(table.schema.metadata)
    descriptor = json.loads(metadata[DESCRIPTOR_KEY])
    descriptor['recording_info']['updated_source'] = True
    metadata[DESCRIPTOR_KEY] = json.dumps(descriptor).encode()
    pq.write_table(table.replace_schema_metadata(metadata), structure.data_parquet_path)
    current = wide_csv.export_scientific(structure=structure,
        request=selected_request(structure, all_channels=False, formats=(updated_format,)))
    assert current.source_sha256 != first.source_sha256
    final = publication.verified_manifest(current.manifest_path)
    assert set(final.snapshots[first.source_sha256]['numpy_datasets']) == {retained_format}
    assert set(final.snapshots[current.source_sha256]['numpy_datasets']) == {updated_format}
    assert all(path.read_bytes() == content for path, content in retained_files.items())
