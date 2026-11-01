"""Translate recording lookup failures at the HTTP boundary."""

from pathlib import Path

from fastapi import HTTPException

from freemocap.core.recording.recording_location import resolve_recording, recording_from_path
from freemocap.system.recording_structure.recording_structure import RecordingStructure


def recording_location(recording_id: str, recording_parent_directory: str | None = None,
                       *, must_exist: bool = True) -> RecordingStructure:
    try:
        return resolve_recording(recording_id, recording_parent_directory, must_exist=must_exist)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(404, str(error)) from error


def recording_path_location(path: str | Path) -> RecordingStructure:
    try:
        return recording_from_path(path)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(404, str(error)) from error
