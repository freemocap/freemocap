"""Generate portable ZSTD recordings for the browser playback regression tests."""

import inspect
import json
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import numpy as np

from freemocap.core.recording.playback_queries import playback_manifest
from freemocap.core.types.channel_kind import ChannelKind
from freemocap.core.recording.result_processing.observation_publication import publish_posthoc_observations
from freemocap.system.recording_structure.recording_structure import RecordingStructure
from freemocap.tests.test_reconstruction_checkpoints import publication
from freemocap.tests.test_recording_store import metadata_fixture, sample_batch
from freemocap.core.recording.parquet_storage.parquet_writer import publish_recording, recording_write_lock


def create_fixture(directory: Path) -> None:
    request = inspect.unwrap(publication)(directory)
    metadata = publish_posthoc_observations(request)
    structure = RecordingStructure(base_directory=directory, recording_name="recording")
    table = pq.read_table(structure.data_parquet_path).replace_schema_metadata(None)
    second = table.set_column(table.schema.get_field_index("run_id"), "run_id", pa.array([1] * len(table), type=pa.int64()))
    second = second.cast(table.schema)
    metadata = metadata.model_copy(update={"runs": {0: metadata.runs[0], 1: metadata.runs[0]}})
    with recording_write_lock(structure=structure):
        publish_recording(structure=structure, metadata=metadata, batches=pa.concat_tables([table, second]).to_batches())
    # Small pages and row groups exercise both boundaries independently of time.
    table = pq.read_table(structure.data_parquet_path)
    pq.write_table(table, structure.data_parquet_path, compression="zstd", row_group_size=4000, data_page_size=512, write_batch_size=32)
    manifest = playback_manifest(structure.data_parquet_path)
    (directory / "manifest.json").write_text(manifest.model_dump_json(), encoding="utf-8")
    scene_row = table.column("channel").to_pylist().index(ChannelKind.SEGMENT_ORIGINS)
    pq.write_table(pa.concat_tables([table, table.slice(scene_row, 1)]), directory / "duplicate.parquet", compression="zstd")
    pq.write_table(pa.concat_tables([table.slice(0, scene_row), table.slice(scene_row + 1)]), directory / "incomplete.parquet", compression="zstd")

    rates_directory = directory / "rates"
    rates_structure = RecordingStructure(base_directory=rates_directory, recording_name="recording")
    with recording_write_lock(structure=rates_structure):
        publish_recording(structure=rates_structure, metadata=metadata_fixture(), batches=[
            sample_batch(group="mocap", count=2, fps=30.0),
            sample_batch(group="eye", count=8, fps=120.0),
        ])
    (directory / "rates.json").write_text(playback_manifest(rates_structure.data_parquet_path).model_dump_json(), encoding="utf-8")
    create_columnar_fixtures(directory)


def create_columnar_fixtures(directory: Path) -> None:
    """Exercise declared tensor axes independently of display XYZ/quaternion projections."""
    runs = []
    rows = []
    expected = []
    for run_id, components, frames, rate in (
        (0, {"north": "m", "angle": "rad", "confidence": "1", "south": "m", "fifth": "1"}, [9, 11, 40], 30),
        (2, {"scalar": "1"}, [4, 8, 12, 16], 120),
    ):
        channel = {"sensor_group": f"group:{run_id}", "source": "source", "reference_frame": None,
                   "kind": "LANDMARKS_3D", "names": ["marker-z", "marker-a"], "components": components}
        runs.append({"run_id": run_id, "models": [], "model_sources": {}, "channels": [channel],
                     "static_channels": [], "timelines": [], "media": []})
        values = []
        for frame_index, frame_number in enumerate(frames):
            for name_index, name in enumerate(channel["names"]):
                for component_index, (component, units) in enumerate(components.items()):
                    value = run_id + frame_index * 100 + name_index * 10 + component_index + 0.1234567890123
                    if frame_index == name_index == component_index == 0:
                        value = -0.0
                    if frame_index == len(frames) - 1:
                        value = None
                    values.append(value)
                    rows.append({"run_id": run_id, "sensor_group": channel["sensor_group"], "source": "source",
                                 "reference_frame": None, "channel": channel["kind"], "name": name,
                                 "component": component, "units": units, "frame_number": frame_number,
                                 "timestamp_s": frame_number / rate, "value": value})
        expected.append({"run_id": run_id, "channel": channel, "frames": frames,
                         "times": [frame / rate for frame in frames], "values": values})
    manifest = {"recording_id": "tensor-cases", "revision": "test-revision", "selected_run_id": 0, "runs": runs}
    (directory / "tensor-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (directory / "tensor-expected.json").write_text(json.dumps(expected), encoding="utf-8")
    fields = [pa.field(name, pa.int64() if name in {"run_id", "frame_number"} else
                       pa.float64() if name in {"timestamp_s", "value"} else pa.string()) for name in rows[0]]
    table = pa.Table.from_pylist(rows, schema=pa.schema(fields))
    shuffled = table.take(pa.array(np.random.default_rng(128).permutation(len(table))))

    def write_case(name: str, data: pa.Table) -> None:
        pq.write_table(data, directory / f"tensor-{name}.parquet", compression="zstd", row_group_size=7,
                       data_page_size=64, write_batch_size=2)

    write_case("valid", shuffled)
    write_case("duplicate", pa.concat_tables([shuffled, shuffled.slice(0, 1)]))
    write_case("incomplete", shuffled.slice(1))
    write_case("missing-column", shuffled.drop(["units"]))
    for case, name, replacement in (
        ("units", "units", "wrong"), ("component", "component", "undeclared"),
        ("name", "name", "undeclared"), ("timestamp", "timestamp_s", float("nan")),
        ("inconsistent-time", "timestamp_s", 9.75), ("value", "value", float("inf")),
        ("null-frame", "frame_number", None), ("negative-frame", "frame_number", -1),
        ("unsafe-frame", "frame_number", 2**53), ("null-run", "run_id", None),
        ("unsafe-run", "run_id", 2**53), ("null-name", "name", None),
    ):
        changed = shuffled.column(name).to_pylist()
        changed[0] = replacement
        write_case(case, shuffled.set_column(shuffled.schema.get_field_index(name), name,
                                            pa.array(changed, type=shuffled.schema.field(name).type)))
    write_case("reversed-time", shuffled.set_column(shuffled.schema.get_field_index("timestamp_s"), "timestamp_s",
                                                   pa.array([-value for value in shuffled.column("timestamp_s").to_pylist()])))
    write_case("string-values", shuffled.set_column(shuffled.schema.get_field_index("value"), "value",
                                                   pa.array([str(value) if value is not None else None
                                                             for value in shuffled.column("value").to_pylist()])))


if __name__ == "__main__":
    create_fixture(Path(sys.argv[1]))
