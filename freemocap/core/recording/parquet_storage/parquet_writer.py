"""Publish a complete validated Parquet with its embedded data descriptor."""

from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import CancelledError
from contextlib import contextmanager
import os
import logging
from time import perf_counter
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
from freemocap.core.recording.recording_info import write_recording_info


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
    cancelled: Callable[[], bool] = lambda: False,
) -> None:
    """Caller holds the recording write lock from run allocation through publication."""
    if metadata.recording_id != structure.recording_name:
        raise ValueError("Recording descriptor ID must match its directory name")
    validator = SampleValidator(metadata=metadata)

    def validated_batches() -> Iterator[pa.RecordBatch]:
        for batch in batches:
            validator.accept(batch=batch)
            yield batch
        validator.finish()

    started = perf_counter()
    publish_parquet(
        path=structure.data_parquet_path,
        schema=SAMPLE_SCHEMA.with_metadata(
            {DESCRIPTOR_KEY: metadata.model_dump_json().encode("utf-8")}
        ),
        batches=validated_batches(),
        cancelled=cancelled,
    )
    write_recording_info(structure, metadata)
    logging.getLogger(__name__).info(
        "Recording saved in %.3f s: %s columnar validation rows, %s scalar fallback rows: %s",
        perf_counter() - started, validator.columnar_rows, validator.scalar_rows,
        structure.data_parquet_path)


def publish_parquet(*, path: Path, schema: pa.Schema, batches: Iterable[pa.RecordBatch],
                    cancelled: Callable[[], bool] = lambda: False) -> None:
    """Write compressed batches and replace the destination only after completion."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, suffix=".parquet.tmp"
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with pq.ParquetWriter(temporary, schema=schema, compression="zstd") as writer:
            for batch in batches:
                if cancelled():
                    raise CancelledError('Cancelled while writing temporary recording')
                writer.write_batch(batch=batch)
        with temporary.open("rb+") as completed:
            os.fsync(completed.fileno())
        if cancelled():
            raise CancelledError('Cancelled before replacing saved recording')
        replace_recording_file(source=temporary, destination=path)
    finally:
        temporary.unlink(missing_ok=True)
