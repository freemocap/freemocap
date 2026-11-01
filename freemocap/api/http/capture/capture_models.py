"""Capture stopping can return a recording and a newly accepted processing task."""
from pathlib import Path

from pydantic import BaseModel


class CaptureStopped(BaseModel):
    success: bool = True
    task_id: str | None = None
    status_url: str | None = None
    recording_id: str | None = None
    recording_parent_directory: str | None = None
    recording_path: str | None = None


class LegacyCaptureStopped(CaptureStopped):
    pipeline_id: str | None = None
    recording_name: str | None = None

    @classmethod
    def completed(cls, *, recording_info, pipeline_id: str):
        path = Path(recording_info.recording_directory).expanduser().resolve() / recording_info.recording_name
        return cls(task_id=pipeline_id, pipeline_id=pipeline_id, status_url=f'/freemocap/tasks/{pipeline_id}',
                   recording_id=path.name, recording_name=path.name,
                   recording_parent_directory=str(path.parent), recording_path=str(path))
