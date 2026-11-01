"""Resolve a recording's folder identity without creating or modifying files."""

from pathlib import Path, PureWindowsPath

from freemocap.system.default_paths import get_default_freemocap_recordings_path
from freemocap.system.recording_structure.recording_structure import RecordingStructure


def recording_parent(directory: str | Path | None = None) -> Path:
    return Path(directory or get_default_freemocap_recordings_path()).expanduser().resolve()


def resolve_recording(
    recording_id: str, parent_directory: str | Path | None = None, *, must_exist: bool = True,
) -> RecordingStructure:
    """A recording ID is one folder name within the selected parent on any OS."""
    if (not recording_id or recording_id in {'.', '..'}
            or PureWindowsPath(recording_id).name != recording_id
            or any(character in recording_id for character in '/\\:')
            or recording_id.endswith((' ', '.'))):
        raise ValueError('Invalid recording_id: expected a single folder name')
    parent = recording_parent(parent_directory)
    folder = (parent / recording_id).resolve()
    if folder.parent != parent:
        raise ValueError('Invalid recording_id: path escapes its parent directory')
    if must_exist and not folder.is_dir():
        raise FileNotFoundError(f'Recording directory not found: {folder}')
    return RecordingStructure(base_directory=parent, recording_name=folder.name)


def recording_from_path(path: str | Path, *, must_exist: bool = True) -> RecordingStructure:
    folder = Path(path).expanduser().resolve()
    return resolve_recording(folder.name, folder.parent, must_exist=must_exist)
