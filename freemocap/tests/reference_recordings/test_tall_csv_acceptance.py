"""Compare every exported scalar to production-generated test/sample Parquet."""

import json
import os
from pathlib import Path
import shutil

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as csv
import pyarrow.parquet as pq
import pytest

from freemocap.core.recording.exports.tall_csv import TallCsvRequest, export_tall_csv, STATIC_SCHEMA
from freemocap.core.recording.exports.publication import digest, verified_manifest
from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata, read_static_channels
from freemocap.core.recording.sample_encoding.arrow_schema import SAMPLE_SCHEMA
from freemocap.system.recording_structure.recording_structure import RecordingStructure


def csv_batches(path, schema):
    return csv.open_csv(path, read_options=csv.ReadOptions(block_size=4 * 1024 * 1024),
        convert_options=csv.ConvertOptions(column_types={f.name: f.type for f in schema},
            strings_can_be_null=True, quoted_strings_can_be_null=False, null_values=['']))


def compare_streams(expected, actual, schema):
    """Compare slices across differing Parquet/CSV batch boundaries; bounded memory."""
    right = None
    offset = 0
    count = 0
    for left in expected:
        start = 0
        while start < left.num_rows:
            if right is None or offset == right.num_rows:
                right = next(actual).cast(schema)
                offset = 0
            length = min(left.num_rows - start, right.num_rows - offset)
            assert left.slice(start, length).replace_schema_metadata(None).equals(right.slice(offset, length))
            start += length
            offset += length
            count += length
    assert right is None or offset == right.num_rows
    assert next(actual, None) is None
    return count


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.parametrize('name', ['freemocap_test_data', 'freemocap_sample_data'])
def test_tall_export_matches_every_production_sample(tmp_path, name):
    configured = os.environ.get('FREEMOCAP_PROVENANCE_PREPARED_ROOT')
    if not configured:
        pytest.skip('Set FREEMOCAP_PROVENANCE_PREPARED_ROOT to verified production outputs')
    marker = json.loads((Path(configured) / name / 'ready.json').read_text())
    original = Path(marker['recording']) / f'{name}_data.parquet'
    original_hash = digest(original)
    assert original_hash == marker['result']['validation']['parquet_sha256']
    structure = RecordingStructure(base_directory=tmp_path, recording_name=name)
    structure.full_path.mkdir()
    shutil.copy2(original, structure.data_parquet_path)
    result = export_tall_csv(structure=structure, request=TallCsvRequest())
    manifest = verified_manifest(result.manifest_path)
    with pq.ParquetFile(structure.data_parquet_path) as parquet, csv_batches(result.files[0], SAMPLE_SCHEMA) as exported:
        expected = (batch.filter(pc.equal(batch.column('run_id'), result.run_id)) for batch in parquet.iter_batches(batch_size=65536))
        count = compare_streams(expected, iter(exported), SAMPLE_SCHEMA)
    assert count == manifest.artifacts[result.files[0].name].rows
    run = read_metadata(path=structure.data_parquet_path).runs[result.run_id]
    expected_static = []
    for item in read_static_channels(run):
        channel = item.channel
        for name in channel.names:
            for component, units in channel.components.items():
                expected_static.append(dict(sensor_group=channel.sensor_group, source=channel.source,
                    reference_frame=channel.reference_frame, channel=channel.kind, name=name,
                    component=component, value=item.values[name][component], units=units, run_id=result.run_id))
    with csv_batches(result.files[1], STATIC_SCHEMA) as exported:
        assert exported.read_all().cast(STATIC_SCHEMA).equals(pa.Table.from_pylist(expected_static, schema=STATIC_SCHEMA))
    assert digest(original) == digest(structure.data_parquet_path) == original_hash
