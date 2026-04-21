"""Canonical folder layout for a freemocap recording.

This module is the authoritative source of truth for "what files live where
in a recording folder". Every path reference in the backend should flow
through `RecordingStructure` rather than being hand-assembled from strings.

The frontend mirrors this layout in
`freemocap-ui/src/store/slices/active-recording/recording-structure.ts` — keep
the two in sync.

Layout (target):

    {base_directory}/{recording_name}/
    ├── videos/
    │   ├── raw/                              # was synchronized_videos/
    │   └── annotated/                        # was annotated_videos/
    ├── output/                               # per-stage processed artifacts
    ├── logs/                                 # per-recording logs
    ├── {recording_name}_calibration.toml     # authoritative TOML for this recording
    ├── {recording_name}_recording_info.json  # camera configs + recording_type tags
    ├── {recording_name}_data.parquet         # primary mocap data store
    └── {recording_name}.blend                # optional Blender export

Calibration and mocap are recording-type tags (captured in
`recording_info.json`), not separate sibling folders.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, computed_field

RecordingTypeTag = Literal["calibration", "mocap"]


class RecordingInfo(BaseModel):
    """Contents of `{recording_name}_recording_info.json`.

    Fields beyond the core set are forward-compatible — extend as needed.
    """

    model_config = ConfigDict(extra="allow")

    recording_name: str
    recording_types: list[RecordingTypeTag] = []
    created_at: datetime | None = None
    camera_configs: dict[str, dict] = {}
    base_fps: float | None = None
    duration_seconds: float | None = None
    operator_notes: str | None = None


class FilePresence(BaseModel):
    path: str
    exists: bool
    size_bytes: int | None = None


class RecordingLayoutValidation(BaseModel):
    """Report describing which expected files/dirs are present on disk."""

    full_path: str
    is_legacy_layout: bool = False
    videos_raw: FilePresence
    videos_annotated: FilePresence
    output_dir: FilePresence
    calibration_toml: FilePresence
    recording_info: FilePresence
    data_parquet: FilePresence
    blend: FilePresence


class RecordingStructure(BaseModel):
    """Authoritative model of a freemocap recording folder layout.

    Consumers build one of these at the system boundary (router arg parsing,
    capture thunk completion, etc.) and pass it around instead of raw strings.
    """

    base_directory: Path
    recording_name: str

    @computed_field
    @property
    def full_path(self) -> Path:
        return self.base_directory / self.recording_name

    @computed_field
    @property
    def videos_raw_dir(self) -> Path:
        return self.full_path / "videos" / "raw"

    @computed_field
    @property
    def videos_annotated_dir(self) -> Path:
        return self.full_path / "videos" / "annotated"

    @computed_field
    @property
    def output_dir(self) -> Path:
        return self.full_path / "output"

    @computed_field
    @property
    def logs_dir(self) -> Path:
        return self.full_path / "logs"

    @computed_field
    @property
    def calibration_toml_path(self) -> Path:
        return self.full_path / f"{self.recording_name}_calibration.toml"

    @computed_field
    @property
    def recording_info_path(self) -> Path:
        return self.full_path / f"{self.recording_name}_recording_info.json"

    @computed_field
    @property
    def data_parquet_path(self) -> Path:
        return self.full_path / f"{self.recording_name}_data.parquet"

    @computed_field
    @property
    def blend_path(self) -> Path:
        return self.full_path / f"{self.recording_name}.blend"

    def create_on_disk(self) -> None:
        """Create the expected subdirectory skeleton. Idempotent."""
        for d in (self.videos_raw_dir, self.videos_annotated_dir, self.output_dir, self.logs_dir):
            d.mkdir(parents=True, exist_ok=True)

    def validate_layout(self) -> RecordingLayoutValidation:
        """Check which expected files/dirs exist. Returns a report, does not raise."""
        legacy_sync = self.full_path / "synchronized_videos"
        legacy_annot = self.full_path / "annotated_videos"
        is_legacy = legacy_sync.exists() and not self.videos_raw_dir.exists()

        return RecordingLayoutValidation(
            full_path=str(self.full_path),
            is_legacy_layout=is_legacy,
            videos_raw=_presence(self.videos_raw_dir if not is_legacy else legacy_sync),
            videos_annotated=_presence(
                self.videos_annotated_dir if not is_legacy else legacy_annot
            ),
            output_dir=_presence(self.output_dir),
            calibration_toml=_presence(self.calibration_toml_path),
            recording_info=_presence(self.recording_info_path),
            data_parquet=_presence(self.data_parquet_path),
            blend=_presence(self.blend_path),
        )


def _presence(path: Path) -> FilePresence:
    exists = path.exists()
    size = path.stat().st_size if exists and path.is_file() else None
    return FilePresence(path=str(path), exists=exists, size_bytes=size)
