"""Prepare Blender automatically, export, and open using the same verified profile."""
from pathlib import Path
import subprocess
from freemocap.core.blender.blender_export_config import BlenderExportConfig

from freemocap.core.blender.runtime import executable, environment, run_blender, start_external
from freemocap.core.blender.preparation import prepare_blender
from freemocap.system.recording_status.recording_status import raise_if_not_blender_ready

ROUTES = ('auto', 'legacy_npy', 'parquet_segments', 'parquet_constraints')


def export_to_blender(recording_folder_path, detector=None, blend_file_path=None,
                      blender_exe_path=None, open_file_on_completion=True, *, route='auto',
                      package=None, trajectory_channel='LANDMARKS_3D', run_id=None, sensor_group=None, blender_export_config=None, development_build_hash=None, progress=None):
    recording = Path(recording_folder_path).expanduser().resolve()
    if not recording.is_dir():
        raise ValueError('Recording directory does not exist: ' + str(recording))
    if route not in ROUTES:
        raise ValueError('Unknown Blender import route: ' + route)
    if trajectory_channel not in ('LANDMARKS_3D', 'MAPPED_KEYPOINTS_3D'):
        raise ValueError('Unknown trajectory channel')
    parquets = sorted(recording.glob('*_data.parquet'))
    if route == 'auto':
        route = 'parquet_segments' if parquets else 'legacy_npy'
    if route == 'legacy_npy':
        if detector not in (None, 'mediapipe'):
            raise ValueError('Legacy NPY export requires MediaPipe; use a Parquet route for other trackers')
        raise_if_not_blender_ready(recording, detector='mediapipe')
    elif len(parquets) != 1:
        raise ValueError('Parquet export requires exactly one *_data.parquet in the recording folder')
    options = BlenderExportConfig.model_validate(blender_export_config or {}).addon_payload(route)
    blender = executable(blender_exe_path)
    output = Path(blend_file_path).expanduser().resolve() if blend_file_path else recording / (recording.name + '.blend')
    if output.suffix.lower() != '.blend' or not output.parent.is_dir():
        raise ValueError('Choose a .blend output in an existing directory')
    prepared = prepare_blender(blender, package, development_build_hash, progress=progress)
    source_sha256 = None
    if route != 'legacy_npy':
        from freemocap.core.recording.exports.publication import digest
        source_sha256 = digest(parquets[0])
    if progress:
        progress('Exporting the recording to Blender')
    result = run_blender(blender, dict(action='export', recording=str(recording), output=str(output),
                                      route=route, package=prepared.package, config=options, trajectory_channel=trajectory_channel,
                                      run_id=run_id, sensor_group=sensor_group, source_sha256=source_sha256,
                                      development_build_hash=development_build_hash), profile=prepared.profile)
    if source_sha256 is not None and digest(parquets[0]) != source_sha256:
        raise RuntimeError('Parquet changed during Blender export; retry the saved result')
    if result.get('output') != str(output) or not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError('Blender did not confirm a nonempty output: ' + str(output))
    if open_file_on_completion:
        if progress:
            progress('Opening the recording in Blender')
        start_external([str(blender), str(output)], cwd=output.parent, env=environment(prepared.profile), shell=False)
    return str(output)
