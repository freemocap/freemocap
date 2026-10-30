"""Shared reads prune only proven exclusions and never duplicate selected rows."""

from concurrent.futures import CancelledError
from itertools import groupby

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from freemocap.core.recording.parquet_storage.recording_view import recording_view
from freemocap.core.recording.parquet_storage.selected_batches import ChannelQuery, RunQuery, selected_batches
from freemocap.tests.test_wide_csv_export import scientific_recording  # noqa: F401


POINT_QUERY = ChannelQuery(3, "a", "points", "RAW_KEYPOINTS_3D", "world")
CLOCK_QUERY = ChannelQuery(0, "b", "clock", "TIMESTAMPS", None)


def matches(row, query):
    return all(row[name] == value for name, value in query.filter_values)


def write_channel_groups(structure, rows, *, statistics=True):
    schema = pq.read_schema(structure.data_parquet_path)
    with pq.ParquetWriter(structure.data_parquet_path, schema, write_statistics=statistics) as writer:
        for _, group in groupby(rows, lambda row: (row["run_id"], row["channel"])):
            writer.write_table(pa.Table.from_pylist(list(group), schema=schema))


def observe_reads(monkeypatch):
    calls = []
    original = pq.ParquetFile.iter_batches

    def read(self, **kwargs):
        calls.append(kwargs)
        yield from original(self, **kwargs)

    monkeypatch.setattr(pq.ParquetFile, "iter_batches", read)
    return calls


@pytest.mark.parametrize("statistics", [False, True])
def test_union_projection_pruning_and_single_open_view(scientific_recording, monkeypatch, statistics):
    structure, rows = scientific_recording
    write_channel_groups(structure, rows, statistics=statistics)
    calls = observe_reads(monkeypatch)
    queries = (POINT_QUERY, CLOCK_QUERY, POINT_QUERY)
    with recording_view(structure.data_parquet_path) as view:
        def forbid_open(*args, **kwargs):
            raise AssertionError("Selection reopened the recording")

        monkeypatch.setattr(pq.ParquetFile, "__init__", forbid_open)
        batches = list(selected_batches(view, queries, columns=("value", "frame_number")))
    columns = ["value", "frame_number", "run_id", "sensor_group", "source", "channel", "reference_frame"]
    expected = [{column: row[column] for column in columns} for row in rows
                if any(matches(row, query) for query in queries)]
    assert [row for batch in batches for row in batch.to_pylist()] == expected
    assert all(call["columns"] == columns for call in calls)
    assert [call["row_groups"] for call in calls] == ([[2], [3]] if statistics else [[i] for i in range(6)])
    assert len(batches) == 2  # Independent writer groups remain independent read batches.


@pytest.mark.parametrize("statistics", [False, True])
def test_mixed_groups_null_references_and_bounded_batches(scientific_recording, statistics):
    structure, rows = scientific_recording
    rows = rows[::2] + rows[1::2][::-1]
    schema = pq.read_schema(structure.data_parquet_path)
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), structure.data_parquet_path,
                   row_group_size=7, write_statistics=statistics)
    queries = (POINT_QUERY, CLOCK_QUERY)
    with recording_view(structure.data_parquet_path) as view:
        batches = list(selected_batches(view, queries, batch_size=3))
    assert all(batch.num_rows <= 3 for batch in batches)
    assert [row for batch in batches for row in batch.to_pylist()] == [
        row for row in rows if any(matches(row, query) for query in queries)
    ]


def test_empty_unknown_and_invalid_selections(scientific_recording, monkeypatch):
    structure, rows = scientific_recording
    write_channel_groups(structure, rows)
    calls = observe_reads(monkeypatch)
    with recording_view(structure.data_parquet_path) as view:
        assert list(selected_batches(view, ())) == []
        assert list(selected_batches(view, (ChannelQuery(99, "a", "points", "RAW_KEYPOINTS_3D", "world"),))) == []
        assert calls == []
        with pytest.raises(ValueError, match="Unknown recording columns"):
            list(selected_batches(view, (POINT_QUERY,), columns=("typo",)))
        with pytest.raises(ValueError, match="batch size must be positive"):
            list(selected_batches(view, (POINT_QUERY,), batch_size=0))


def test_cancellation_before_decode_and_between_groups(scientific_recording, monkeypatch):
    structure, rows = scientific_recording
    write_channel_groups(structure, rows)
    calls = observe_reads(monkeypatch)
    with recording_view(structure.data_parquet_path) as view:
        with pytest.raises(CancelledError):
            list(selected_batches(view, (POINT_QUERY,), cancelled=lambda: True))
        assert calls == []
        stopped = False
        reader = selected_batches(view, (POINT_QUERY, CLOCK_QUERY), cancelled=lambda: stopped)
        assert next(reader).num_rows == 2
        stopped = True
        with pytest.raises(CancelledError):
            next(reader)
        assert len(calls) == 1


@pytest.mark.parametrize('statistics', [False, True])
def test_run_queries_include_undeclared_channels_without_duplicate_decode(scientific_recording, monkeypatch, statistics):
    structure, rows = scientific_recording
    rows.append(dict(rows[-1], channel='undeclared'))
    write_channel_groups(structure, rows, statistics=statistics)
    queries = (RunQuery(3, 'b'), CLOCK_QUERY, RunQuery(3, 'b'))
    calls = observe_reads(monkeypatch)
    with recording_view(structure.data_parquet_path) as view:
        batches = list(selected_batches(view, queries))
    assert [row for batch in batches for row in batch.to_pylist()] == [
        row for row in rows if any(matches(row, query) for query in queries)
    ]
    assert any(row['channel'] == 'undeclared' for batch in batches for row in batch.to_pylist())
    decoded = [call['row_groups'][0] for call in calls]
    assert len(decoded) == len(set(decoded))
