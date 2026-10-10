"""Compact human-readable companion; measurements and full definitions stay in Parquet."""
import json
import hashlib
import os
from pathlib import Path
import tempfile


def write_recording_info(structure, metadata):
    """Caller holds the recording lock. Preserve capture and unknown user fields."""
    path = structure.recording_info_path
    legacy = structure.full_path / f'{structure.recording_name}_info.json'
    existing = path if path.exists() else legacy
    if path.is_symlink() or existing.is_symlink():
        raise ValueError('Recording info must not be a link')
    info = json.loads(existing.read_text(encoding='utf-8')) if existing.exists() else dict(metadata.recording_info)
    if not isinstance(info, dict):
        raise ValueError('Recording info must be a JSON object')
    runs = {}
    for run_id, run in metadata.runs.items():
        runs[str(run_id)] = dict(
            sensor_groups={key: value.model_dump(mode='json') for key, value in run.sensor_groups.items()},
            cameras=[key.removeprefix('camera:') for key, source in run.sources.items() if source.kind == 'camera'],
            reference_frames=run.reference_frames,
            data=[dict(channel=str(c.kind), source=c.source, sensor_group=c.sensor_group,
                       reference_frame=c.reference_frame, names=c.names, components=c.components)
                  for c in run.channels if c.kind in {'LANDMARKS_3D', 'KEYPOINTS_3D', 'RAW_KEYPOINTS_3D',
                                                     'OVERLAY_2D', 'SEGMENT_ORIGINS', 'ROTATIONS_WORLD'}])
    with structure.data_parquet_path.open('rb') as stream:
        parquet_sha256 = hashlib.file_digest(stream, 'sha256').hexdigest()
    info['processed'] = dict(schema_version=1, parquet_sha256=parquet_sha256, recording_id=metadata.recording_id,
        parquet=structure.data_parquet_path.name, selected_run_id=metadata.selected_run_id, runs=runs,
        conventions=dict(quaternion_order='wxyz', segment_pose='saved origin and world orientation',
                         units='per component', coordinates='per reference frame', array_order='frames, names, components'),
        export_inventories=[p.relative_to(structure.full_path).as_posix()
                            for p in sorted(structure.exports_dir.glob('**/*_recording_info.json'))])
    descriptor, name = tempfile.mkstemp(dir=structure.full_path, suffix='.info.tmp')
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(info, stream, ensure_ascii=False, allow_nan=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
