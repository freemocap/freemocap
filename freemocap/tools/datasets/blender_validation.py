"""Production Blender preparation and saved-file acceptance for dataset runs."""
from pathlib import Path

from freemocap.core.blender.preparation import prepare_blender
from freemocap.core.blender.runtime import executable, run_blender


def preflight_blender(path=None):
    blender = executable(path)
    return blender, prepare_blender(blender)


def validate_blender(recording: Path, validation: dict, *, prepared=None, blender_path=None) -> dict:
    blender, package = prepared or preflight_blender(blender_path)
    result = run_blender(blender, dict(action='validate_scene', package=package.package,
        recording=str(recording), output=str(recording / f'{recording.name}.blend'),
        run_id=validation['run_id'], sensor_group=validation['sensor_group'],
        source_sha256=validation['parquet_sha256']), profile=package.profile)
    return dict(result, executable=str(blender))
