"""Production Blender preparation and saved-file acceptance for dataset runs."""
from pathlib import Path
import subprocess

from freemocap.core.blender.preparation import prepare_blender
from freemocap.core.blender.runtime import executable, run_blender


def preflight_blender(path=None):
    blender = executable(path)
    return blender, prepare_blender(blender)


def open_promoted_recording(recording: Path, blender_path=None, *, close_after_open=False):
    """Open the final location only after the candidate has been promoted."""
    from freemocap.core.blender.export_to_blender import open_blend_file
    blender, package = preflight_blender(blender_path)
    scene = recording / f'{recording.name}.blend'
    expression = None
    if close_after_open:
        # Run after loading the requested scene; a timer exercises the GUI event
        # loop before Blender closes itself. Only this launched instance is owned.
        expression = ("import bpy; from pathlib import Path; "
                      f"assert Path(bpy.data.filepath).resolve() == Path({str(scene)!r}).resolve(); "
                      "bpy.app.timers.register(lambda: bpy.ops.wm.quit_blender(), first_interval=2.0)")
    process = open_blend_file(blender, scene, profile=package.profile, python_expression=expression)
    if not close_after_open:
        return dict(opened=True, closed=False)
    try:
        code = process.wait(timeout=60)
        if code != 0:
            raise RuntimeError(f'Blender GUI validation exited with code {code}')
        return dict(opened=True, closed=True, exit_code=code, method='scene assertion and GUI quit timer')
    except BaseException:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        raise


def validate_blender(recording: Path, validation: dict, *, prepared=None, blender_path=None) -> dict:
    blender, package = prepared or preflight_blender(blender_path)
    result = run_blender(blender, dict(action='validate_scene', package=package.package,
        recording=str(recording), output=str(recording / f'{recording.name}.blend'),
        run_id=validation['run_id'], sensor_group=validation['sensor_group'],
        source_sha256=validation['parquet_sha256']), profile=package.profile)
    return dict(result, executable=str(blender))
