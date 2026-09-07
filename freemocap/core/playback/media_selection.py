"""Recording video discovery shared by inventory and streaming consumers."""

from enum import StrEnum
from pathlib import Path

from freemocap.system.default_paths import ANNOTATED_VIDEOS_FOLDER_NAME, SYNCHRONIZED_VIDEOS_FOLDER_NAME

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}


class PlaybackVideoSource(StrEnum):
    SYNCHRONIZED = "synchronized"
    ANNOTATED = "annotated"


def video_source_folder(*, recording: Path, source: PlaybackVideoSource) -> Path:
    folder = recording / (ANNOTATED_VIDEOS_FOLDER_NAME if source == PlaybackVideoSource.ANNOTATED
                          else SYNCHRONIZED_VIDEOS_FOLDER_NAME)
    if source == PlaybackVideoSource.SYNCHRONIZED and not folder.is_dir():
        return recording
    return folder


def discover_video_paths(*, folder: Path) -> tuple[Path, ...]:
    return tuple(sorted(path for path in folder.iterdir()
                        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS))
