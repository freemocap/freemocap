"""Batch optimizations must reject malformed sources and preserve scalar semantics."""
import csv

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from freemocap.core.recording.exports import arrays, wide_csv
from freemocap.core.recording.parquet_storage.recording_view import recording_view
from freemocap.tests.test_wide_csv_export import scientific_recording  # noqa: F401


def rewrite(structure, rows, **options):
    schema = pq.read_schema(structure.data_parquet_path)
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), structure.data_parquet_path, **options)


def raw_arrays(structure, scratch):
    with recording_view(structure.data_parquet_path) as view:
        item = arrays.available_channels(view.metadata.runs[3])[0]
        with arrays.ordered_arrays(view, 3, item, scratch=scratch) as values:
            return tuple(a.copy() for a in (values.frames, values.timestamps, values.values, values.present))


@pytest.mark.parametrize('statistics', [False, True])
@pytest.mark.parametrize('row_group_size', [1, 7, 1000])
def test_row_group_pruning_keeps_exact_results_for_mixed_groups(scientific_recording, tmp_path, statistics, row_group_size):
    structure, rows = scientific_recording
    expected = raw_arrays(structure, tmp_path)
    # Reverse/interleave runs, frames and channels; source order is not an axis definition.
    rows = rows[::2] + rows[1::2][::-1]
    rewrite(structure, rows, write_statistics=statistics, row_group_size=row_group_size)
    actual = raw_arrays(structure, tmp_path)
    for left, right in zip(actual, expected, strict=True):
        np.testing.assert_array_equal(left, right)
    # Null reference frames must not be pruned as if they were absent.
    with recording_view(structure.data_parquet_path) as view:
        context = arrays.available_channels(view.metadata.runs[3])[2][0]
        assert sum(b.num_rows for b in arrays.channel_batches(view, 3, context, None)) == 2


@pytest.mark.parametrize('change, message', [
    ({'name': 'unknown'}, 'Undeclared'),
    ({'component': 'unknown'}, 'Undeclared'),
    ({'units': 'wrong'}, 'incorrect units'),
    ({'value': float('nan')}, 'finite numbers'),
    ({'value': float('inf')}, 'finite numbers'),
    ({'frame_number': -1}, 'Invalid frame/time'),
    ({'timestamp_s': float('inf')}, 'Invalid frame/time'),
    ({'timestamp_s': 0.2}, 'Conflicting timestamps'),
])
def test_batched_array_validation_rejects_corruption(scientific_recording, tmp_path, change, message):
    structure, rows = scientific_recording
    target = next(row for row in rows if row['run_id'] == 3 and row['channel'] == 'RAW_KEYPOINTS_3D')
    target.update(change)
    rewrite(structure, rows, row_group_size=1)
    with pytest.raises(ValueError, match=message):
        raw_arrays(structure, tmp_path)


@pytest.mark.parametrize('row_group_size', [1, 1000])
def test_duplicate_rejected_inside_and_across_batches(scientific_recording, tmp_path, row_group_size, monkeypatch):
    structure, rows = scientific_recording
    target = next(row for row in rows if row['run_id'] == 3 and row['channel'] == 'RAW_KEYPOINTS_3D')
    rewrite(structure, rows + [target], row_group_size=row_group_size)
    original = arrays.channel_batches
    def small_batches(*args, **kwargs):
        for batch in original(*args, **kwargs):
            if row_group_size == 1:
                for i in range(batch.num_rows):
                    yield batch.slice(i, 1)
            else:
                yield batch
    monkeypatch.setattr(arrays, 'channel_batches', small_batches)
    with pytest.raises(ValueError, match='Duplicate'):
        raw_arrays(structure, tmp_path)


@pytest.mark.parametrize("split_batches", [False, True])
def test_last_equal_timestamp_sign_and_value_signed_zero_preserved(scientific_recording, tmp_path, monkeypatch, split_batches):
    structure, rows = scientific_recording
    target = [row for row in rows if row['run_id'] == 3 and row['channel'] == 'RAW_KEYPOINTS_3D' and row['frame_number'] == 10]
    for row in target:
        row['timestamp_s'] = 0.0
    target[-1]['timestamp_s'] = -0.0
    target[0]['value'] = -0.0
    rewrite(structure, rows)
    if split_batches:
        original = arrays.channel_batches
        def split(*args, **kwargs):
            for batch in original(*args, **kwargs):
                for i in range(batch.num_rows):
                    yield batch.slice(i, 1)
        monkeypatch.setattr(arrays, 'channel_batches', split)
    _, timestamps, values, _ = raw_arrays(structure, tmp_path)
    assert np.signbit(timestamps[0])
    assert values[0, 0, 2] == 0 and np.signbit(values[0, 0, 2])


@pytest.mark.parametrize('mutation', ['signed_zero', 'null_to_absent', 'absent_to_null', 'extra_row', 'bad_width', 'changed_float'])
def test_csv_bulk_validation_rejects_corruption(tmp_path, mutation):
    context = arrays.ChannelSelection(sensor_group='camera', source='tracker', reference_frame='world', channel='RAW_KEYPOINTS_3D')
    values = arrays.ChannelArrays(context, ('point',), ('x', 'y', 'z'), ('mm',)*3,
        np.array([10, 42]), np.array([0.0, 1.0]),
        np.array([[[-0.0, np.nan, np.nan]], [[np.nextafter(1.0, 2.0), 2.0, 3.0]]]),
        np.array([[[True, True, False]], [[True, True, True]]]))
    columns = ['frame_number', 'timestamp_s', 'point.x', 'point.y', 'point.z']
    rows = list(wide_csv.rows_for(values, 0, 2, 0, 3))
    if mutation == 'signed_zero': rows[0][2] = 0.0
    if mutation == 'null_to_absent': rows[0][3] = ''
    if mutation == 'absent_to_null': rows[0][4] = 'NaN'
    if mutation == 'extra_row': rows.append(rows[0])
    if mutation == 'bad_width': rows[0].pop()
    if mutation == 'changed_float': rows[1][2] = 1.0
    path = tmp_path / 'corrupt.csv'
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        writer.writerows(rows)
    with pytest.raises(ValueError):
        wide_csv.validate_table(path, values, columns, (0, 2, 0, 3), None)


def test_dictionary_encoded_batches_preserve_descriptor_order(scientific_recording, tmp_path, monkeypatch):
    structure, _ = scientific_recording
    expected = raw_arrays(structure, tmp_path)
    original = arrays.channel_batches
    def dictionary_batches(*args, **kwargs):
        for batch in original(*args, **kwargs):
            for name in ('name', 'component', 'units'):
                index = batch.schema.get_field_index(name)
                if index >= 0:
                    batch = batch.set_column(index, name, batch.column(index).dictionary_encode())
            yield batch
    monkeypatch.setattr(arrays, 'channel_batches', dictionary_batches)
    for left, right in zip(raw_arrays(structure, tmp_path), expected, strict=True):
        np.testing.assert_array_equal(left, right)
