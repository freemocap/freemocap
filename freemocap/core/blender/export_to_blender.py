"""Export through an explicitly installed Blender package."""
from pathlib import Path
import subprocess
from freemocap.core.blender.blender_export_config import BlenderExportConfig

from freemocap.core.blender.runtime import executable, environment, run_blender
from freemocap.system.recording_status.recording_status import raise_if_not_blender_ready

ROUTES = ('auto', 'legacy_npy', 'parquet_segments', 'parquet_constraints')


def export_to_blender(recording_folder_path, detector=None, blend_file_path=None,
                      blender_exe_path=None, open_file_on_completion=True, *, route='auto',
                      package=None, trajectory_channel='LANDMARKS_3D', run_id=None, sensor_group=None, blender_export_config=None):
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
    result = run_blender(blender, dict(action='export', recording=str(recording), output=str(output),
                                      route=route, package=package, config=options, trajectory_channel=trajectory_channel,
                                      run_id=run_id, sensor_group=sensor_group))
    if result.get('output') != str(output) or not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError('Blender did not confirm a nonempty output: ' + str(output))
    if open_file_on_completion:
        subprocess.Popen([str(blender), str(output)], cwd=output.parent, env=environment(), shell=False)
    return str(output)
