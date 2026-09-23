"""Generate portable ZSTD recordings for the browser playback regression tests."""

import inspect
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

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


if __name__ == "__main__":
    create_fixture(Path(sys.argv[1]))
