"""Playback clocks preserve stored identities and exact duplicate semantics."""

import math

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from freemocap.core.recording.playback_queries import playback_manifest
from freemocap.tests.test_selective_parquet_read import observe_reads, write_channel_groups
from freemocap.tests.test_wide_csv_export import scientific_recording  # noqa: F401


def rewrite(structure, rows, *, statistics=True):
    schema = pq.read_schema(structure.data_parquet_path)
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), structure.data_parquet_path,
                   row_group_size=3, write_statistics=statistics)


@pytest.fixture
def timing_recording(scientific_recording):
    structure, rows = scientific_recording
    rows = [dict(row, component="timestamp_s") if row["channel"] == "TIMESTAMPS" else row for row in rows]
    rewrite(structure, rows)
    return structure, rows


@pytest.mark.parametrize("statistics", [False, True])
def test_manifest_projects_only_clock_columns_and_prunes_proven_exclusions(timing_recording, monkeypatch, statistics):
    structure, rows = timing_recording
    write_channel_groups(structure, rows, statistics=statistics)
    calls = observe_reads(monkeypatch)
    manifest = playback_manifest(structure.data_parquet_path)
    assert manifest.selected_run_id == 3
    assert [run.run_id for run in manifest.runs] == [0, 3]
    for run in manifest.runs:
        assert len(run.timelines) == 1
        timeline = run.timelines[0]
        assert (timeline.sensor_group, timeline.source) == ("b", "clock")
        assert timeline.frame_numbers == (10, 42)
        assert timeline.timestamps_s == (5.125, 5.987654321)
    assert all(call["columns"] == ["run_id", "sensor_group", "source", "frame_number", "timestamp_s",
                                    "channel", "component"] for call in calls)
    assert [call["row_groups"] for call in calls] == ([[2], [5]] if statistics else [[i] for i in range(6)])


@pytest.mark.parametrize("statistics", [False, True])
def test_manifest_orders_frames_and_identities_across_batches_without_rounding(timing_recording, statistics):
    structure, rows = timing_recording
    clock = next(row for row in rows if row["channel"] == "TIMESTAMPS")
    # Undeclared timing channels still participate, including nonnull references.
    extra = [dict(clock, source="points", sensor_group="a", reference_frame="world",
                  frame_number=frame, timestamp_s=timestamp)
             for frame, timestamp in [(42, 0.9876543210123456), (10, 0.125000000000001)]]
    rewrite(structure, extra + rows[::-1] + extra[::-1], statistics=statistics)
    manifest = playback_manifest(structure.data_parquet_path)
    timelines = manifest.runs[0].timelines
    assert [(item.sensor_group, item.source) for item in timelines] == [("a", "points"), ("b", "clock")]
    assert timelines[0].frame_numbers == (10, 42)
    assert timelines[0].timestamps_s == (0.125000000000001, 0.9876543210123456)


@pytest.mark.parametrize("identity", [{}, {"source": "undeclared"}, {"run_id": 99}, {"sensor_group": "undeclared"}])
def test_manifest_rejects_conflicting_duplicates_even_for_undeclared_identities(timing_recording, identity):
    structure, rows = timing_recording
    clock = dict(next(row for row in rows if row["channel"] == "TIMESTAMPS"), **identity)
    rewrite(structure, [clock] + rows + [dict(clock, timestamp_s=clock["timestamp_s"] + 1e-12)])
    with pytest.raises(ValueError, match="Inconsistent playback timestamps"):
        playback_manifest(structure.data_parquet_path)


def test_manifest_does_not_hide_undeclared_source(timing_recording):
    structure, rows = timing_recording
    clock = next(row for row in rows if row["channel"] == "TIMESTAMPS")
    rewrite(structure, rows + [dict(clock, source="undeclared")])
    with pytest.raises(KeyError, match="undeclared"):
        playback_manifest(structure.data_parquet_path)


@pytest.mark.parametrize("timestamps", [(0.2, 0.1), (0.1, 0.1), (0.1, float("nan"))])
def test_manifest_rejects_invalid_native_clock(timing_recording, timestamps):
    structure, rows = timing_recording
    clock = next(row for row in rows if row["channel"] == "TIMESTAMPS")
    rewrite(structure, [dict(clock, frame_number=frame, timestamp_s=timestamp)
                        for frame, timestamp in zip((10, 42), timestamps, strict=True)])
    with pytest.raises(ValueError, match="Playback timeline"):
        playback_manifest(structure.data_parquet_path)


def test_manifest_ignores_other_components_and_unknown_run_but_checks_all_duplicates(timing_recording):
    structure, rows = timing_recording
    clock = next(row for row in rows if row["channel"] == "TIMESTAMPS")
    before = playback_manifest(structure.data_parquet_path)
    rewrite(structure, rows + [dict(clock, component="other", timestamp_s=-1),
                               dict(clock, run_id=99, timestamp_s=float("nan"))])
    after = playback_manifest(structure.data_parquet_path)
    assert after.runs == before.runs


def test_manifest_without_timestamp_rows_has_empty_timelines(timing_recording):
    structure, rows = timing_recording
    rewrite(structure, [row for row in rows if row["channel"] != "TIMESTAMPS"])
    assert all(not run.timelines for run in playback_manifest(structure.data_parquet_path).runs)


def test_equal_duplicate_keeps_last_signed_zero(timing_recording):
    structure, rows = timing_recording
    clock = next(row for row in rows if row["channel"] == "TIMESTAMPS")
    rewrite(structure, [dict(clock, timestamp_s=0.0), dict(clock, timestamp_s=-0.0)])
    timestamp = playback_manifest(structure.data_parquet_path).runs[0].timelines[0].timestamps_s[0]
    assert math.copysign(1.0, timestamp) == -1.0
