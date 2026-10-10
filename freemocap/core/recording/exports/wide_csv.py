"""Selected channel tables, reloaded and verified before recoverable publication."""
import csv
from datetime import datetime, timezone
import math
import json
from contextlib import ExitStack
from zipfile import ZipFile, ZIP_DEFLATED
import os
import re
from pathlib import Path
import tempfile

from filelock import FileLock
import numpy as np
from pydantic import BaseModel, ConfigDict

from freemocap.core.recording.exports.arrays import ScientificExportRequest, resolve_selection, ordered_arrays, check_cancelled, available_channels, scientific_channels
from freemocap.core.recording.exports.publication import ExportArtifact, ExportManifest, digest, verified_manifest, publish, remove_staging
from freemocap.core.recording.parquet_storage.recording_view import recording_view

from freemocap.core.recording.exports.guides import stage_guides
from freemocap.core.recording.exports.notebook import write_notebook

MAX_VALUE_COLUMNS = 1024
MAX_ROWS = 500_000

# Public file/NPZ labels; canonical Parquet channel identifiers stay unchanged.
DATA_LABELS = {
    'OVERLAY_2D': '2d_overlay',
    'RAW_KEYPOINTS_3D': '3d_keypoints_raw',
    'KEYPOINTS_3D': '3d_keypoints_filtered',
    'LANDMARKS_3D': '3d_landmarks',
    'SEGMENT_POSES': '3d_segment_poses',
}


def table_names(run):
    """Stable across selection changes; exact identities remain in metadata."""
    names, used = {}, set()
    for context, _, _ in sorted(available_channels(run) + scientific_channels(run), key=lambda item: item[0].model_dump_json()):
        if context.key in names:
            continue
        source = context.source.split(':', 1)[-1]
        if context.channel == 'OVERLAY_2D' and context.reference_frame:
            camera = context.reference_frame.removeprefix('camera:').removesuffix(':image')
            source += f'--{Path(camera).stem}'
        source = re.sub(r'[<>:\x00-\x1f\"/\\|?*]', '-', source).strip(' .').replace('..', '-') or 'source'
        base = f'{DATA_LABELS.get(context.channel, context.channel.lower())}--{source}'
        name, number = base, 1
        while name.casefold() in used:
            number += 1
            name = f'{base}--{number}'
        used.add(name.casefold())
        names[context.key] = name
    return names


class ScientificExportResult(BaseModel):
    model_config = ConfigDict(extra='forbid')
    run_id: int
    source_revision: str
    source_sha256: str
    manifest_path: Path
    files: tuple[Path, ...]
    validated: bool = True


def header(name, component):
    # CSV quoting handles punctuation; metadata preserves the exact axis mapping.
    return f'{name}.{component}'


def rows_for(arrays, start, stop, first, last):
    values = arrays.values.reshape((-1, len(arrays.names) * len(arrays.components)))
    presence = arrays.present.reshape(values.shape)
    for i in range(start, stop):
        prefix = [] if arrays.context.static else [int(arrays.frames[i]), float(arrays.timestamps[i])]
        yield prefix + [('' if not presence[i, j] else 'NaN' if np.isnan(values[i, j]) else float(values[i, j]))
                        for j in range(first, last)]


def validate_table(path, arrays, columns, bounds, cancelled):
    """Independent CSV parser: exact float64 round trip and absence/null distinction."""
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.reader(stream)
        if next(reader, None) != columns:
            raise ValueError('Wide CSV headers changed')
        for expected in rows_for(arrays, *bounds):
            check_cancelled(cancelled)
            actual = next(reader, None)
            if actual is None or len(actual) != len(expected):
                raise ValueError('Wide CSV row shape mismatch')
            for value, wanted in zip(actual, expected, strict=True):
                if isinstance(wanted, str):
                    equal = value == wanted
                elif isinstance(wanted, int):
                    equal = int(value) == wanted
                else:
                    parsed = float(value)
                    equal = parsed == wanted and (wanted != 0 or math.copysign(1, parsed) == math.copysign(1, wanted))
                if not equal:
                    raise ValueError('Wide CSV value or missingness mismatch')
        if next(reader, None) is not None:
            raise ValueError('Wide CSV contains unexpected rows')


def validate_array(actual, expected):
    if actual.dtype != expected.dtype or actual.shape != expected.shape or not np.array_equal(actual, expected, equal_nan=True):
        raise ValueError('NumPy values, shape or dtype changed during export')
    if np.issubdtype(actual.dtype, np.floating) and not np.array_equal(np.signbit(actual), np.signbit(expected)):
        raise ValueError('NumPy floating point signs changed during export')


def matching_timestamps(left, right):
    """Allow float64 arithmetic roundoff, never a sampling/time alignment tolerance."""
    return left.shape == right.shape and bool(np.all(
        np.abs(left - right) <= 4 * np.spacing(np.maximum(np.abs(left), np.abs(right)))))


def _export_scientific(*, structure, request: ScientificExportRequest, cancelled=None, progress=None):
    check_cancelled(cancelled)
    with recording_view(structure.data_parquet_path) as view:
        run_id, selected = resolve_selection(view, request)
        source_hash = view.content_sha256()
        names = table_names(view.metadata.runs[run_id])
        prefix = structure.recording_name + (f'.run-{run_id}' if request.keep else '')
        root = structure.exports_dir
        directory = root / f'run-{run_id}' if request.keep else root
        if root.is_symlink() or directory.is_symlink():
            raise ValueError('Export directories must not be links')
        directory.mkdir(parents=True, exist_ok=True)
        with FileLock(root / '.exports.lock', timeout=0):
            manifest_name = f'{prefix}_recording_info.json'
            manifest_path = directory / manifest_name
            if manifest_path.is_symlink():
                raise ValueError('Export metadata must not be a link')
            if (directory / '.publication.json').exists():
                raise ValueError('Export publication is incomplete; recover it before exporting')
            legacy_path = directory / f'{prefix}.wide.metadata.json'
            previous_path = manifest_path if manifest_path.exists() else legacy_path
            previous = verified_manifest(previous_path) if previous_path.exists() else None
            if request.keep and previous is not None:
                if any(a.source_sha256 != source_hash or a.source_revision != view.revision or a.run_id != run_id for a in previous.artifacts.values()):
                    raise ValueError('Retained export is bound to another source revision')
                if any(a.format in request.formats or (a.format == 'static_wide_csv' and 'wide_csv' in request.formats) for a in previous.artifacts.values()):
                    raise FileExistsError('Selected format already exists in this retained export')
            staging = Path(tempfile.mkdtemp(prefix='.staging-', dir=directory))
            try:
                artifacts, descriptions = {}, {}
                shared_frames, shared_timestamps = None, None
                timestamp_roundoff = 0.0
                numpy_requested = bool(set(request.formats) & {"npy", "npz"})
                with ExitStack() as stack:
                    archive_name = f'{prefix}.npz'
                    archive = stack.enter_context(ZipFile(staging / archive_name, 'w', compression=ZIP_DEFLATED)) if 'npz' in request.formats else None
                    export_started = datetime.now(timezone.utc).isoformat()
                    for index, item in enumerate(selected):
                        context = item[0]
                        if progress:
                            progress(index, len(selected), f'Exporting {context.channel} ({context.source})')
                        with ordered_arrays(view, run_id, item, scratch=staging, cancelled=cancelled) as arrays:
                            first_timeline = shared_frames is None
                            if numpy_requested or request.wide_csv is None:
                                if context.static or len(arrays.values) != len(arrays.frames):
                                    raise ValueError('Export completeness check failed: every measurement array must have a frame axis')
                                if first_timeline:
                                    shared_frames, shared_timestamps = arrays.frames.copy(), arrays.timestamps.copy()
                                elif not np.array_equal(shared_frames, arrays.frames) or not matching_timestamps(shared_timestamps, arrays.timestamps):
                                    raise ValueError('Export completeness check failed: selected arrays must have identical frame counts, frame numbers and timestamps')
                                if len(arrays.timestamps):
                                    timestamp_roundoff = max(timestamp_roundoff, float(np.max(np.abs(shared_timestamps - arrays.timestamps))))
                            descriptions[context.key] = arrays.descriptor()
                            descriptions[context.key]['missing_values'] = 'NumPy: NaN for unavailable values; CSV: empty for absent entries, NaN for recorded null'
                            stem = f'{prefix}.{names[context.key]}'
                            descriptions[context.key]['numpy_key'] = names[context.key]
                            descriptions[context.key]['timing'] = dict(frame_count=len(arrays.frames),
                                first_frame=int(arrays.frames[0]) if len(arrays.frames) else None,
                                last_frame=int(arrays.frames[-1]) if len(arrays.frames) else None,
                                first_timestamp_s=float(arrays.timestamps[0]) if len(arrays.timestamps) else None,
                                last_timestamp_s=float(arrays.timestamps[-1]) if len(arrays.timestamps) else None)
                            outputs = dict(values=arrays.values)
                            if first_timeline:
                                outputs.update(frames=arrays.frames, timestamps=arrays.timestamps)
                            for role, value in outputs.items():
                                check_cancelled(cancelled)
                                if 'npy' in request.formats:
                                    filename = f'npy/{stem}.npy' if role == "values" else f'npy/{prefix}.{role}.npy'
                                    (staging / 'npy').mkdir(exist_ok=True)
                                    np.save(staging / filename, value, allow_pickle=False)
                                    loaded = np.load(staging / filename, allow_pickle=False)
                                    validate_array(loaded, value)
                                    artifacts[filename] = ExportArtifact(filename=filename, sha256=digest(staging / filename),
                                        rows=len(value), columns=(), source_sha256=source_hash, source_revision=view.revision,
                                        run_id=run_id, format='npy', details=dict(context_key=context.key if role == "values" else None, role=role,
                                            shape=list(value.shape), dtype=str(value.dtype), validation='reload_exact', validator_version=1))
                                if archive is not None:
                                    key = f'{names[context.key]}.values.npy' if role == 'values' else f'{role}.npy'
                                    with archive.open(key, 'w', force_zip64=True) as stream:
                                        np.lib.format.write_array(stream, value, allow_pickle=False)
                                    # Reload the individual member before releasing this channel's arrays.
                                    with archive.open(key) as stream:
                                        validate_array(np.lib.format.read_array(stream, allow_pickle=False), value)
                            if 'wide_csv' not in request.formats:
                                continue
                            mapping = [(name, component) for name in arrays.names for component in arrays.components]
                            total_rows = 1 if context.static else len(arrays.frames)
                            for row_start in range(0, max(1, total_rows), MAX_ROWS):
                                row_stop = min(row_start + MAX_ROWS, total_rows)
                                for first in range(0, len(mapping), MAX_VALUE_COLUMNS):
                                    last = min(first + MAX_VALUE_COLUMNS, len(mapping))
                                    clock_headers = [] if context.static else ['frame_number', 'timestamp_s']
                                    columns = clock_headers + [header(*pair) for pair in mapping[first:last]]
                                    if len(set(columns)) != len(columns):
                                        raise ValueError('CSV name/component pairs produce duplicate headers')
                                    parts = (f'.rows-{row_start // MAX_ROWS + 1}' if total_rows > MAX_ROWS else '')
                                    parts += (f'.columns-{first // MAX_VALUE_COLUMNS + 1}' if len(mapping) > MAX_VALUE_COLUMNS else '')
                                    name = f'csv/{stem}{parts}.csv'
                                    path = staging / name
                                    path.parent.mkdir(exist_ok=True)
                                    bounds = (row_start, row_stop, first, last)
                                    with path.open('w', encoding='utf-8-sig', newline='') as stream:
                                        writer = csv.writer(stream)
                                        writer.writerow(columns)
                                        for row in rows_for(arrays, *bounds):
                                            check_cancelled(cancelled)
                                            writer.writerow(row)
                                        stream.flush()
                                        os.fsync(stream.fileno())
                                    validate_table(path, arrays, columns, bounds, cancelled)
                                    artifacts[name] = ExportArtifact(filename=name, sha256=digest(path), rows=row_stop-row_start,
                                        columns=tuple(columns), source_sha256=source_hash, source_revision=view.revision, run_id=run_id,
                                        format='static_wide_csv' if context.static else 'wide_csv',
                                        details=dict(context_key=context.key, frame_slice=[row_start, row_stop],
                                            value_column_slice=[first, last],
                                            validation='reload_exact_float64', validator_version=1))
                    snapshot = dict(revision=view.revision, exported_at=export_started,
                        recording_id=view.metadata.recording_id, run_id=run_id, source_sha256=source_hash,
                        source_file=structure.data_parquet_path.name,
                        conventions=dict(quaternion_order="wxyz", segment_pose="saved origin and world orientation",
                            missing_values="NumPy: NaN for unavailable values; CSV: empty for absent entries, NaN for recorded null"),
                        reference_frames={key: value for key, value in view.metadata.runs[run_id].reference_frames.items()
                                          if key in {item[0].reference_frame for item in selected}},
                        channels=descriptions, selection=request.model_dump(mode='json'))
                    if numpy_requested:
                        snapshot['numpy_timeline'] = dict(frame_count=len(shared_frames),
                            frames_file=f'npy/{prefix}.frames.npy', timestamps_file=f'npy/{prefix}.timestamps.npy',
                            npz_frames_key='frames', npz_timestamps_key='timestamps', validation='all_selected_frame_axes_equal',
                            timestamp_roundoff_limit='4 float64 ULPs', maximum_timestamp_difference_s=timestamp_roundoff)
                    if archive is not None:
                        archive.writestr('recording_info.json', json.dumps(snapshot, ensure_ascii=False, allow_nan=False))
                if 'npz' in request.formats:
                    with np.load(staging / archive_name, allow_pickle=False) as loaded:
                        expected_keys = {f'{names[item[0].key]}.values' for item in selected} | {'frames', 'timestamps'}
                        if set(loaded.files) != expected_keys | {'recording_info.json'}:
                            raise ValueError('NPZ archive inventory mismatch')
                    artifacts[archive_name] = ExportArtifact(filename=archive_name, sha256=digest(staging / archive_name),
                        rows=len(selected), columns=(), source_sha256=source_hash, source_revision=view.revision,
                        run_id=run_id, format='npz', details=dict(context_keys=[item[0].key for item in selected],
                            validation='reload_exact', validator_version=1))
                if 'notebook' in request.formats:
                    notebook_name = f'{prefix}.explorer.ipynb'
                    write_notebook(staging / notebook_name, snapshot=snapshot, retained=request.keep)
                    artifacts[notebook_name] = ExportArtifact(filename=notebook_name,
                        sha256=digest(staging / notebook_name), rows=0, columns=(),
                        source_sha256=source_hash, source_revision=view.revision, run_id=run_id,
                        format='notebook', details=dict(context_keys=[item[0].key for item in selected]))
                generated = tuple(artifacts)
                # Updating CSV must not relabel or remove a previously exported NumPy artifact.
                replaced_formats = set(request.formats)
                if 'wide_csv' in replaced_formats:
                    replaced_formats.add('static_wide_csv')
                if previous:
                    artifacts.update({name: a for name, a in previous.artifacts.items() if a.format not in replaced_formats})
                snapshots = dict(previous.snapshots) if previous else {}
                existing = snapshots.get(source_hash, {})
                snapshot['channels'] = {**existing.get('channels', {}), **snapshot['channels']}
                snapshot['reference_frames'] = {**existing.get('reference_frames', {}), **snapshot['reference_frames']}
                if not numpy_requested and 'numpy_timeline' in existing:
                    snapshot['numpy_timeline'] = existing['numpy_timeline']
                snapshots[source_hash] = snapshot
                for key, description in snapshots.items():
                    needed = {context for a in artifacts.values() if a.source_sha256 == key
                              for context in ([a.details['context_key']] if 'context_key' in a.details else a.details.get('context_keys', []))}
                    description['channels'] = {k: v for k, v in description.get('channels', {}).items() if k in needed}
                snapshots = {key: value for key, value in snapshots.items() if key in {a.source_sha256 for a in artifacts.values()}}
                manifest = ExportManifest(version=3, artifacts=artifacts, snapshots=snapshots,
                    csv=dict(encoding='utf-8-sig', delimiter=',', absent='empty field', null='NaN',
                             float_precision='round-trip float64', column_order='descriptor names, explicit components'))
                obsolete = tuple(a for name, a in previous.artifacts.items() if name not in artifacts) if previous else ()
                if previous is not None and previous_path != manifest_path:
                    obsolete += (ExportArtifact(filename=previous_path.name, sha256=digest(previous_path), rows=0, columns=(),
                        source_sha256=source_hash, source_revision=view.revision, run_id=run_id, format='metadata'),)
                check_cancelled(cancelled)
                guides = stage_guides(directory, staging, request.formats)
                publish(directory, staging, manifest_name, manifest, (*generated, *guides), request.keep, obsolete=obsolete)
                if progress:
                    progress(len(selected), len(selected), 'Selected exports saved and validated')
                return ScientificExportResult(run_id=run_id, source_revision=view.revision, source_sha256=source_hash,
                    manifest_path=manifest_path, files=tuple(directory / name for name in generated))
            finally:
                if staging.exists() and not (directory / '.publication.json').exists():
                    remove_staging(directory, staging)


def export_scientific(*, structure, request: ScientificExportRequest, cancelled=None, progress=None):
    result = _export_scientific(structure=structure, request=request, cancelled=cancelled, progress=progress)
    from freemocap.core.recording.parquet_storage.parquet_writer import recording_write_lock
    from freemocap.core.recording.recording_info import write_recording_info
    with recording_write_lock(structure=structure):
        with recording_view(structure.data_parquet_path) as view:
            write_recording_info(structure, view.metadata)
    return result
