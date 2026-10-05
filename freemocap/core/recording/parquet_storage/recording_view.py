"""One open snapshot shared by playback and secondary exports."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from typing import BinaryIO

import pyarrow.parquet as pq

from freemocap.core.recording.data_descriptors.recording_descriptor import RecordingMetadata
from freemocap.core.recording.parquet_storage.parquet_reader import metadata_from_schema
from freemocap.core.recording.parquet_storage.shared_file import shared_recording_file


@dataclass(frozen=True)
class RecordingView:
    parquet: pq.ParquetFile
    metadata: RecordingMetadata
    revision: str
    source: BinaryIO

    def content_sha256(self) -> str:
        position = self.source.tell()
        try:
            self.source.seek(0)
            digest = hashlib.sha256()
            while block := self.source.read(1024 * 1024):
                digest.update(block)
            return digest.hexdigest()
        finally:
            self.source.seek(position)


@contextmanager
def recording_view(path: Path) -> Iterator[RecordingView]:
    with shared_recording_file(path) as source:
        stat = os.fstat(source.fileno())
        revision = hashlib.sha256(
            f"{stat.st_dev}:{stat.st_ino}:{stat.st_size}:{stat.st_mtime_ns}".encode()
        ).hexdigest()
        with pq.ParquetFile(source) as parquet:
            metadata = metadata_from_schema(schema=parquet.schema_arrow, path=path)
            if metadata.recording_id != path.parent.name:
                raise ValueError("Recording identity does not match its folder")
            yield RecordingView(parquet=parquet, metadata=metadata, revision=revision, source=source)
