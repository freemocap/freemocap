"""Recording folder health/status checks.

Single source of truth for "is this recording ready to export / open in Blender?"
Owns the list of required Blender-input files and the per-folder checks. Consumed
by the playback router (list + per-recording status), the blender router
(`/blender/open` pre-flight), and `export_to_blender` (pre-flight before subprocess).
"""
from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel

from freemocap.system.default_paths import (
    ANNOTATED_VIDEOS_FOLDER_NAME,
    SYNCHRONIZED_VIDEOS_FOLDER_NAME,
)

OUTPUT_DATA_FOLDER_NAME = "output_data"

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}

REQUIRED_BLENDER_INPUT_FILES: list[str] = [
    "mediapipe_body_3d_xyz.npy",
    "mediapipe_right_hand_right_hand.npy",
    "mediapipe_left_hand_left_hand.npy",
    "mediapipe_face_3d_xyz.npy",
    "mediapipe_body_total_body_center_of_mass.npy",
    "mediapipe_body_segment_center_of_mass.npy",
]

STAGE_RAW_VIDEOS = "Synchronized videos"
STAGE_CALIBRATION = "Calibration"
STAGE_BLENDER_INPUTS = "Blender input data (.npy)"
STAGE_ANNOTATED_VIDEOS = "Annotated videos"
STAGE_BLENDER_SCENE = "Blender scene"


class FileStatus(BaseModel):
    name: str
    path: str | None = None
    exists: bool = False
    size_bytes: int | None = None
    modified_timestamp: str | None = None  # ISO-8601 UTC


class StageStatus(BaseModel):
    name: str
    complete: bool
    present_count: int
    total_count: int
    files: list[FileStatus] = []


class RecordingStatus(BaseModel):
    # Top-level readiness (stable consumers: blender_router, export_to_blender)
    has_blend_file: bool = False
    blend_file_path: str | None = None
    has_annotated_videos: bool = False
    annotated_videos_path: str | None = None
    blender_export_ready: bool = False
    missing_blender_inputs: list[str] = []

    # Richer per-stage breakdown
    stages: list[StageStatus] = []

    # Raw contents summary
    synchronized_video_count: int = 0
    annotated_video_count: int = 0
    calibration_toml_path: str | None = None
    has_calibration_toml: bool = False


def missing_blender_input_files(recording_folder_path: str|Path) -> list[str]:
    output_data = Path(recording_folder_path) / OUTPUT_DATA_FOLDER_NAME
    return [name for name in REQUIRED_BLENDER_INPUT_FILES
            if not (output_data / name).exists()]


def raise_if_not_blender_ready(recording_folder_path: str|Path) -> None:
    """Pre-flight check for export_to_blender. Raises FileNotFoundError listing all missing files."""
    missing = missing_blender_input_files(recording_folder_path)
    if missing:
        output_data = Path(recording_folder_path) / OUTPUT_DATA_FOLDER_NAME
        raise FileNotFoundError(
            f"Missing {len(missing)} required Blender input file(s) in {output_data}: "
            + ", ".join(missing)
        )


def _find_blend_file(recording_folder: str|Path) -> Path | None:
    expected = recording_folder / f"{recording_folder.stem}.blend"
    if expected.is_file():
        return expected
    for p in recording_folder.iterdir():
        if p.is_file() and p.suffix.lower() == ".blend":
            return p
    return None


def _find_calibration_toml(recording_folder: str|Path) -> Path | None:
    for p in recording_folder.iterdir():
        if p.is_file() and p.suffix.lower() == ".toml" and "calibration" in p.name.lower():
            return p
    return None


def _file_status(path: Path, display_name: str | None = None) -> FileStatus:
    name = display_name or path.name
    if not path.exists():
        return FileStatus(name=name, path=str(path), exists=False)
    try:
        stat = path.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(timespec="seconds")
        return FileStatus(
            name=name,
            path=str(path),
            exists=True,
            size_bytes=stat.st_size,
            modified_timestamp=mtime,
        )
    except OSError:
        return FileStatus(name=name, path=str(path), exists=True)


def _count_videos(folder: Path) -> int:
    if not folder.is_dir():
        return 0
    return sum(
        1 for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
    )


def _list_videos(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
    )


def _build_raw_videos_stage(recording_folder: Path) -> tuple[StageStatus, int]:
    synced_folder = recording_folder / SYNCHRONIZED_VIDEOS_FOLDER_NAME
    videos = _list_videos(synced_folder)
    if not videos:
        videos = _list_videos(recording_folder)
    count = len(videos)
    files = [_file_status(v) for v in videos]
    return (
        StageStatus(
            name=STAGE_RAW_VIDEOS,
            complete=count > 0,
            present_count=count,
            total_count=count,
            files=files,
        ),
        count,
    )


def _build_calibration_stage(recording_folder: Path) -> tuple[StageStatus, Path | None]:
    toml_path = _find_calibration_toml(recording_folder)
    files = [_file_status(toml_path)] if toml_path else []
    return (
        StageStatus(
            name=STAGE_CALIBRATION,
            complete=toml_path is not None,
            present_count=1 if toml_path else 0,
            total_count=1,
            files=files,
        ),
        toml_path,
    )


def _build_blender_inputs_stage(recording_folder: Path) -> StageStatus:
    output_data = recording_folder / OUTPUT_DATA_FOLDER_NAME
    files = [_file_status(output_data / name, display_name=name) for name in REQUIRED_BLENDER_INPUT_FILES]
    present = sum(1 for f in files if f.exists)
    return StageStatus(
        name=STAGE_BLENDER_INPUTS,
        complete=present == len(files),
        present_count=present,
        total_count=len(files),
        files=files,
    )


def _build_annotated_videos_stage(recording_folder: Path) -> tuple[StageStatus, bool, int]:
    annotated_dir = recording_folder / ANNOTATED_VIDEOS_FOLDER_NAME
    videos = _list_videos(annotated_dir)
    count = len(videos)
    has_any = count > 0
    files = [_file_status(v) for v in videos]
    return (
        StageStatus(
            name=STAGE_ANNOTATED_VIDEOS,
            complete=has_any,
            present_count=count,
            total_count=count if has_any else 1,
            files=files,
        ),
        has_any,
        count,
    )


def _build_blender_scene_stage(recording_folder: Path) -> tuple[StageStatus, Path | None]:
    blend_file = _find_blend_file(recording_folder)
    files = [_file_status(blend_file)] if blend_file else []
    return (
        StageStatus(
            name=STAGE_BLENDER_SCENE,
            complete=blend_file is not None,
            present_count=1 if blend_file else 0,
            total_count=1,
            files=files,
        ),
        blend_file,
    )


def compute_recording_status(recording_folder_path: Path) -> RecordingStatus:
    recording_folder = Path(recording_folder_path)
    if not recording_folder.is_dir():
        return RecordingStatus()

    raw_videos_stage, synced_video_count = _build_raw_videos_stage(recording_folder)
    calibration_stage, calibration_toml = _build_calibration_stage(recording_folder)
    blender_inputs_stage = _build_blender_inputs_stage(recording_folder)
    annotated_stage, has_annotated, annotated_count = _build_annotated_videos_stage(recording_folder)
    blender_scene_stage, blend_file = _build_blender_scene_stage(recording_folder)

    annotated_videos_dir = recording_folder / ANNOTATED_VIDEOS_FOLDER_NAME
    missing = [f.name for f in blender_inputs_stage.files if not f.exists]

    return RecordingStatus(
        has_blend_file=blend_file is not None,
        blend_file_path=str(blend_file) if blend_file else None,
        has_annotated_videos=has_annotated,
        annotated_videos_path=str(annotated_videos_dir) if has_annotated else None,
        blender_export_ready=len(missing) == 0,
        missing_blender_inputs=missing,
        stages=[
            raw_videos_stage,
            calibration_stage,
            blender_inputs_stage,
            annotated_stage,
            blender_scene_stage,
        ],
        synchronized_video_count=synced_video_count,
        annotated_video_count=annotated_count,
        calibration_toml_path=str(calibration_toml) if calibration_toml else None,
        has_calibration_toml=calibration_toml is not None,
    )
