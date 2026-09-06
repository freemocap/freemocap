"""Publish a complete validated Parquet with its embedded data descriptor."""

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
import os
from pathlib import Path
import tempfile

from filelock import FileLock

import pyarrow as pa
import pyarrow.parquet as pq

from freemocap.core.recording.sample_encoding.arrow_schema import (
    DESCRIPTOR_KEY,
    SAMPLE_SCHEMA,
    SampleValidator,
)
from freemocap.core.recording.data_descriptors.recording_descriptor import RecordingMetadata
from freemocap.core.recording.parquet_storage.shared_file import replace_recording_file
from freemocap.system.recording_structure.recording_structure import RecordingStructure


@contextmanager
def recording_write_lock(*, structure: RecordingStructure) -> Iterator[None]:
    structure.full_path.mkdir(parents=True, exist_ok=True)
    lock_path = structure.full_path / ".processing.lock"
    with FileLock(lock_file=lock_path, timeout=0):
        yield


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
        replace_recording_file(source=temporary, destination=structure.data_parquet_path)
    finally:
        temporary.unlink(missing_ok=True)

