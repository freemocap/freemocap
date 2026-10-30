"""All-channel wide exports from the production reference outputs; no new producer."""
import csv
import json
import os
from pathlib import Path
import shutil
from threading import Event, Thread
import time

import psutil
import numpy as np
import pytest

from freemocap.core.recording.exports.arrays import scientific_channels, channel_batches
from freemocap.core.recording.exports.requests import ScientificExportRequest, ChannelSelection
from freemocap.core.recording.exports.wide_csv import export_scientific
from freemocap.core.recording.exports.publication import digest, verified_manifest
from freemocap.core.recording.parquet_storage.recording_view import recording_view
from freemocap.system.recording_structure.recording_structure import RecordingStructure
from freemocap.tools.datasets.workflow import checked_ready
from skellyforge.core.data_tensors import read_numpy_dataset
from freemocap.tests.numpy_export_assertions import display_projection


@pytest.mark.e2e
@pytest.mark.parametrize('name', ['freemocap_test_data', 'freemocap_sample_data'])
def test_reference_wide_csv_values_and_metadata(tmp_path, name):
    configured = os.environ.get('FREEMOCAP_PROVENANCE_PREPARED_ROOT')
    if not configured:
        pytest.skip('Set FREEMOCAP_PROVENANCE_PREPARED_ROOT to standard reference outputs')
    ready = checked_ready(Path(configured) / name, require_complete=False, check_exports=False)
    assert ready is not None
    source = Path(ready['recording']) / f'{name}_data.parquet'
    before = digest(source)
    structure = RecordingStructure(base_directory=tmp_path, recording_name=name)
    structure.full_path.mkdir()
    shutil.copy2(source, structure.data_parquet_path)
    stop = Event()
    memory = [psutil.Process().memory_info().rss]
    def sample_memory():
        while not stop.wait(0.2):
            memory.append(psutil.Process().memory_info().rss)
    sampler = Thread(target=sample_memory, daemon=True)
    sampler.start()
    started = time.monotonic()
    try:
        result = export_scientific(structure=structure, request=ScientificExportRequest(formats=('wide_csv', 'npy', 'npz'), data=('LANDMARKS_3D', 'RAW_KEYPOINTS_3D', 'KEYPOINTS_3D', 'OVERLAY_2D', 'SEGMENT_POSES')))
    finally:
        stop.set()
        sampler.join()
    elapsed = time.monotonic() - started
    manifest = verified_manifest(result.manifest_path)
    contexts = manifest.snapshots[result.source_sha256]['channels']
    numpy_dataset = read_numpy_dataset(result.manifest_path.parent / 'npy')
    archived_dataset = read_numpy_dataset(next(path for path in result.files if path.suffix == '.npz'))
    assert numpy_dataset.channel_identities == archived_dataset.channel_identities
    with recording_view(structure.data_parquet_path) as view:
        declarations = {context.key: (channel, values) for context, channel, values in scientific_channels(view.metadata.runs[result.run_id])}
        csv_contexts = {artifact.details['context_key'] for artifact in manifest.artifacts.values() if artifact.format == 'wide_csv'}
        assert csv_contexts == set(declarations)
        assert set(declarations).issubset(contexts)
        for artifact in manifest.artifacts.values():
            if artifact.format != 'wide_csv':
                continue
            context_key = artifact.details['context_key']
            context = ChannelSelection(**contexts[context_key]['context'])
            channel, static_values = declarations[context_key]
            assert contexts[context_key]['names'] == list(channel.names)
            with (result.manifest_path.parent / artifact.filename).open(encoding='utf-8-sig', newline='') as stream:
                reader = csv.reader(stream)
                assert next(reader) == list(artifact.columns)
                parsed = list(reader)
            headers = artifact.columns if context.static else artifact.columns[2:]
            mapping = [dict(zip(('name', 'component'), heading.rsplit('.', 1), strict=True)) for heading in headers]
            assert len(parsed) == artifact.rows
            if context.static:
                for column, value in zip(mapping, parsed[0], strict=True):
                    assert float(value) == static_values[column['name']][column['component']]
                continue
            by_frame = {int(row[0]): row for row in parsed}
            assert len(by_frame) == len(parsed)
            by_column = {(column['name'], column['component']): i + 2 for i, column in enumerate(mapping)}
            expected_count = 0
            source_contexts = [context] if context.channel != 'SEGMENT_POSES' else [context.model_copy(update={'channel': kind}) for kind in ('SEGMENT_ORIGINS', 'ROTATIONS_WORLD')]
            batches = ((source_context, batch) for source_context in source_contexts for batch in channel_batches(view, result.run_id, source_context, None))
            for source_context, batch in batches:
                for frame, timestamp, point, component, unit, value in zip(*batch.select(
                        ['frame_number', 'timestamp_s', 'name', 'component', 'units', 'value']).to_pydict().values(), strict=True):
                    if context.channel == 'SEGMENT_POSES' and source_context.channel == 'ROTATIONS_WORLD':
                        component = 'q' + component
                    source_component = component
                    if context.channel == 'OVERLAY_2D' and component == 'visibility':
                        component = 'confidence'
                    row, column_index = by_frame.get(frame), by_column.get((point, component))
                    if row is None or column_index is None:
                        continue  # Another row/column part owns this sample.
                    expected_count += 1
                    assert float(row[1]) == timestamp
                    assert channel.components[source_component] == unit
                    assert row[column_index] == 'NaN' if value is None else float(row[column_index]) == value
            projected = display_projection(numpy_dataset, context.model_dump(mode='json'))
            archived = display_projection(archived_dataset, context.model_dump(mode='json'))
            arrays = dict(values=projected.values, present=projected.present, frames=projected.frames, timestamps=projected.timestamps)
            for role, values in arrays.items():
                np.testing.assert_array_equal(values, getattr(archived, role))
            assert arrays['values'].shape == tuple(contexts[context_key]['shape'])
            for row in parsed:
                i = list(arrays['frames']).index(int(row[0]))
                expected_time = arrays['timestamps'][i]
                assert float(row[1]) == expected_time
                for column, value in zip(mapping, row[2:], strict=True):
                    j = contexts[context_key]['names'].index(column['name'])
                    k = contexts[context_key]['components'].index(column['component'])
                    expected = arrays['values'][i, j, k]
                    assert np.isnan(expected) if value in ('', 'NaN') else float(value) == expected
            assert sum(value != '' for row in parsed for value in row[2:]) == expected_count
    assert digest(source) == before == digest(structure.data_parquet_path)
    print(json.dumps(dict(dataset=name, seconds=elapsed, peak_rss_bytes=max(memory),
        export_bytes=sum(path.stat().st_size for path in result.files), files=len(result.files),
        csv_tables=sum(path.suffix == '.csv' for path in result.files), channels=len(contexts))))
