"""Stream exact selected-run samples to tall CSV, preserving scientific metadata."""

from collections.abc import Callable
from concurrent.futures import CancelledError
from datetime import datetime, timezone
from importlib.metadata import version
import json
import os
from pathlib import Path
import tempfile

from filelock import FileLock
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as csv
from pydantic import BaseModel, ConfigDict, Field

from freemocap.core.recording.exports.publication import (
    ExportArtifact, ExportManifest, digest, finish_publication, publish, verified_manifest, remove_staging,
)
from freemocap.core.recording.parquet_storage.parquet_reader import read_static_channels
from freemocap.core.recording.parquet_storage.recording_view import recording_view
from freemocap.core.recording.sample_encoding.arrow_schema import DESCRIPTOR_KEY, SAMPLE_SCHEMA, SampleValidator
from freemocap.system.recording_structure.recording_structure import RecordingStructure

STATIC_SCHEMA = pa.schema([field for field in SAMPLE_SCHEMA if field.name not in ('timestamp_s', 'frame_number')])


class TallCsvRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    run_id: int | None = Field(default=None, ge=0)
    expected_revision: str | None = None
    keep: bool = False


class TallCsvResult(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    run_id: int
    source_revision: str
    source_sha256: str
    manifest_path: Path
    files: tuple[Path, ...]


def export_tall_csv(*, structure: RecordingStructure, request: TallCsvRequest,
                    cancelled: Callable[[], bool] | None = None,
                    progress: Callable[[int], None] | None = None) -> TallCsvResult:
    def check_cancelled():
        if cancelled is not None and cancelled():
            raise CancelledError('Tall CSV export cancelled')

    check_cancelled()
    with recording_view(structure.data_parquet_path) as view:
        if request.expected_revision is not None and request.expected_revision != view.revision:
            raise ValueError('Recording revision changed; reload the saved result')
        run_id = view.metadata.selected_run_id if request.run_id is None else request.run_id
        if run_id not in view.metadata.runs:
            raise ValueError(f'Unknown recording run: {run_id}')
        source_hash = view.content_sha256()
        check_cancelled()
        run = view.metadata.runs[run_id]
        prefix = structure.recording_name + (f'.run-{run_id}' if request.keep else '')
        root = structure.exports_dir
        directory = root / f'run-{run_id}' if request.keep else root
        if root.is_symlink() or directory.is_symlink():
            raise ValueError('Export directories must not be links')
        directory.mkdir(parents=True, exist_ok=True)
        with FileLock(root / '.exports.lock', timeout=0):
            manifest_name = f'{prefix}.metadata.json'
            manifest_path = directory / manifest_name
            if manifest_path.is_symlink():
                raise ValueError('Export metadata must not be a link')
            if (directory / '.publication.json').exists():
                raise ValueError('Export publication is incomplete; recover it before exporting')
            previous = verified_manifest(manifest_path) if manifest_path.exists() else ExportManifest(artifacts={}, snapshots={})
            if request.keep and any(a.source_sha256 != source_hash or a.source_revision != view.revision
                                    or a.run_id != run_id for a in previous.artifacts.values()):
                raise FileExistsError('Retained exports belong to a different source revision')
            # Always write a header-only static CSV if no static values exist: a
            # repeated default export cannot leave an old static table looking current.
            filenames = (f'{prefix}.tall.csv', f'{prefix}.static.tall.csv')
            for name in filenames:
                target = directory / name
                if target.is_symlink() or (request.keep and target.exists()):
                    raise FileExistsError(f'Export destination already exists or is a link: {target}')
            staging = Path(tempfile.mkdtemp(prefix='.staging-', dir=directory))
            try:
                selected_metadata = view.metadata.model_copy(update={'selected_run_id': run_id, 'runs': {run_id: run}})
                validator = SampleValidator(metadata=selected_metadata)
                count = 0
                with (staging / filenames[0]).open('wb') as stream:
                    stream.write(b'\xef\xbb\xbf')
                    with csv.CSVWriter(stream, SAMPLE_SCHEMA) as writer:
                        for batch in view.parquet.iter_batches(batch_size=65536):
                            check_cancelled()
                            chosen = batch.filter(pc.equal(batch.column('run_id'), run_id)).replace_schema_metadata(None)
                            if chosen.num_rows:
                                validator.accept(batch=chosen)
                                writer.write_batch(chosen)
                                count += chosen.num_rows
                                if progress is not None:
                                    progress(count)
                        validator.finish()
                    stream.flush()
                    os.fsync(stream.fileno())
                static_rows = []
                for item in read_static_channels(run):
                    c = item.channel
                    for name in c.names:
                        for component, units in c.components.items():
                            static_rows.append(dict(sensor_group=c.sensor_group, source=c.source,
                                reference_frame=c.reference_frame, channel=c.kind, name=name,
                                component=component, value=item.values[name][component], units=units, run_id=run_id))
                check_cancelled()
                with (staging / filenames[1]).open('wb') as stream:
                    stream.write(b'\xef\xbb\xbf')
                    with csv.CSVWriter(stream, STATIC_SCHEMA) as writer:
                        writer.write_table(pa.Table.from_pylist(static_rows, schema=STATIC_SCHEMA))
                    stream.flush()
                    os.fsync(stream.fileno())
                artifacts = dict(previous.artifacts)
                for name, schema, rows, kind in zip(filenames, (SAMPLE_SCHEMA, STATIC_SCHEMA),
                        (count, len(static_rows)), ('tall_csv', 'static_tall_csv'), strict=True):
                    artifacts[name] = ExportArtifact(filename=name, sha256=digest(staging / name), rows=rows,
                        columns=tuple(schema.names), source_sha256=source_hash, source_revision=view.revision,
                        run_id=run_id, format=kind)
                snapshots = dict(previous.snapshots)
                snapshots[source_hash] = dict(revision=view.revision,
                    exported_at=datetime.now(timezone.utc).isoformat(), software=dict(freemocap=version('freemocap'), pyarrow=pa.__version__),
                    recording_descriptor=json.loads(view.parquet.schema_arrow.metadata[DESCRIPTOR_KEY]),
                    static_channels_by_run={str(key): [item.model_dump(mode='json') for item in read_static_channels(value)]
                        for key, value in view.metadata.runs.items()})
                snapshots = {key: value for key, value in snapshots.items() if key in {a.source_sha256 for a in artifacts.values()}}
                manifest = ExportManifest(artifacts=artifacts, snapshots=snapshots)
                check_cancelled()
                # Commit is short and recoverable; cancellation no longer interrupts it.
                publish(directory, staging, manifest_name, manifest, filenames, request.keep)
                return TallCsvResult(run_id=run_id, source_revision=view.revision, source_sha256=source_hash,
                    manifest_path=manifest_path, files=tuple(directory / name for name in filenames))
            finally:
                if staging.exists() and not (directory / '.publication.json').exists():
                    remove_staging(directory, staging)


def recover_tall_export(*, structure: RecordingStructure, retained_run_id: int | None = None) -> None:
    root = structure.exports_dir
    directory = root if retained_run_id is None else root / f'run-{retained_run_id}'
    if root.is_symlink() or directory.is_symlink():
        raise ValueError('Export directories must not be links')
    if not (directory / '.publication.json').is_file():
        raise ValueError('No pending export publication')
    with FileLock(root / '.exports.lock', timeout=0):
        finish_publication(directory)
