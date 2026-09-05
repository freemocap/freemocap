"""Publish a complete validated Parquet before updating its JSON descriptor mirror."""

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
import os
from pathlib import Path
import tempfile

from filelock import FileLock

import pyarrow as pa
import pyarrow.parquet as pq

from freemocap.core.recording.recording_data import (
    DESCRIPTOR_KEY,
    SAMPLE_SCHEMA,
    SampleValidator,
)
from freemocap.core.recording.recording_metadata import RecordingMetadata
from freemocap.core.recording.recording_reader import read_metadata
from freemocap.system.recording_structure.recording_structure import RecordingStructure


@contextmanager
def recording_write_lock(*, structure: RecordingStructure) -> Iterator[None]:
    structure.full_path.mkdir(parents=True, exist_ok=True)
    lock_path = structure.full_path / ".processing.lock"
    with FileLock(lock_file=lock_path, timeout=0):
        yield


def write_metadata_mirror(*, path: Path, metadata: RecordingMetadata) -> None:
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, suffix=".json.tmp")
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(metadata.model_dump_json(indent=2))
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def publish_recording(
    *,
    structure: RecordingStructure,
    metadata: RecordingMetadata,
    batches: Iterable[pa.RecordBatch],
) -> None:
    """Caller holds the recording write lock from run allocation through publication."""
    if metadata.recording_id != structure.recording_name:
        raise ValueError("Recording descriptor ID must match its directory name")
    validator = SampleValidator(metadata=metadata)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=structure.full_path, suffix=".parquet.tmp"
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        schema = SAMPLE_SCHEMA.with_metadata(
            {DESCRIPTOR_KEY: metadata.model_dump_json().encode("utf-8")}
        )
        with pq.ParquetWriter(temporary, schema=schema, compression="zstd") as writer:
            for batch in batches:
                validator.accept(batch=batch)
                writer.write_batch(batch=batch)
            validator.finish()
        with temporary.open("rb+") as completed:
            os.fsync(completed.fileno())
        os.replace(temporary, structure.data_parquet_path)
        write_metadata_mirror(path=structure.recording_info_path, metadata=metadata)
    finally:
        temporary.unlink(missing_ok=True)


def repair_metadata_mirror(*, structure: RecordingStructure) -> RecordingMetadata:
    """Recover the JSON mirror from the last committed Parquet under the write lock."""
    with recording_write_lock(structure=structure):
        metadata = read_metadata(path=structure.data_parquet_path)
        if metadata.recording_id != structure.recording_name:
            raise ValueError("Recording identity does not match its directory")
        write_metadata_mirror(path=structure.recording_info_path, metadata=metadata)
        return metadata
