"""
Playback router: serves pre-recorded video files over HTTP for browser-native
<video> playback. Supports range requests for efficient seeking.

Endpoints are keyed on {recording_id} (the recording folder name). The full
recording path is resolved as {BASE_RECORDINGS_DIRECTORY}/{recording_id},
with an optional `recording_parent_directory` query param to override the base.

Endpoints:
  GET  /playback/recordings                              — list available recordings
  GET  /playback/{recording_id}/videos                   — list videos in a recording
  GET  /playback/{recording_id}/videos/{video_id}        — stream a video file
  GET  /playback/{recording_id}/timestamps               — timestamps for all videos
  GET  /playback/{recording_id}/videos/{video_id}/timestamps — timestamps for one video
"""
import csv
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from freemocap.system.recording_status.recording_status import (
    RecordingStatus,
    compute_recording_status,
)
from freemocap.system.default_paths import get_default_freemocap_recordings_path

_VIEWER_HTML = Path(__file__).parent.parent.parent.parent / "core" / "viz" / "parquet_viewer.html"

logger = logging.getLogger(__name__)

playback_router = APIRouter(prefix="/playback", tags=["Playback"])

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
TIMESTAMP_EXTENSIONS = {".csv"}


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class VideoInfo(BaseModel):
    video_id: str
    filename: str
    size_bytes: int
    stream_url: str


class RecordingStatusSummary(BaseModel):
    blender_export_ready: bool = False
    has_blend_file: bool = False
    has_annotated_videos: bool = False
    has_calibration_toml: bool = False
    stages_complete: int = 0
    stages_total: int = 0


class RecordingListEntry(BaseModel):
    name: str
    path: str
    video_count: int
    total_size_bytes: int = 0
    created_timestamp: Optional[str] = None
    total_frames: Optional[int] = None
    duration_seconds: Optional[float] = None
    fps: Optional[float] = None
    status_summary: RecordingStatusSummary = RecordingStatusSummary()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_recording_path(
    recording_id: str,
    recording_parent_directory: str | None = None,
) -> Path:
    """Resolve the full recording path from recording_id + optional parent dir.

    Raises HTTPException(404) if the directory does not exist.
    Raises HTTPException(400) for path traversal attempts.
    """
    parent = (
        Path(recording_parent_directory)
        if recording_parent_directory
        else Path(get_default_freemocap_recordings_path())
    )
    parent = parent.expanduser().resolve()
    recording_path = (parent / recording_id).resolve()

    # Path traversal guard
    if not str(recording_path).startswith(str(parent)):
        raise HTTPException(status_code=400, detail="Invalid recording_id")

    if not recording_path.is_dir():
        raise HTTPException(
            status_code=404,
            detail=f"Recording directory not found: {recording_path}",
        )
    return recording_path


def _discover_videos(folder: Path) -> dict[str, Path]:
    """Find video files in a folder, keyed by a stable ID derived from the filename stem."""
    videos: dict[str, Path] = {}
    if not folder.is_dir():
        raise FileNotFoundError(f"Not a directory: {folder}")

    for p in sorted(folder.iterdir()):
        if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS:
            video_id = p.stem
            videos[video_id] = p
    return videos


def _find_video_folder(recording_path: Path) -> Path:
    """Resolve the actual folder containing video files.

    Looks for a synchronized_videos/ subfolder first, then falls back to
    videos directly in the recording root.
    """
    synced = recording_path / "synchronized_videos"
    if synced.is_dir():
        if any(p.suffix.lower() in VIDEO_EXTENSIONS for p in synced.iterdir() if p.is_file()):
            return synced

    if any(p.suffix.lower() in VIDEO_EXTENSIONS for p in recording_path.iterdir() if p.is_file()):
        return recording_path

    raise FileNotFoundError(
        f"No video files found in {recording_path} or {recording_path}/synchronized_videos/"
    )


def _get_total_size(video_folder: Path) -> int:
    """Sum of all video file sizes in a folder."""
    total = 0
    for p in video_folder.iterdir():
        if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS:
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


def _get_recording_stats(recording_path: Path, video_folder: Path) -> dict:
    """Try to extract frame count, duration, and fps from timestamp CSV files."""
    stats: dict = {
        "total_frames": None,
        "duration_seconds": None,
        "fps": None,
    }

    # Look for timestamp CSV files in various locations
    timestamp_dirs = [
        recording_path / "synchronized_videos" / "timestamps" / "camera_timestamps",
        recording_path / "synchronized_videos" / "timestamps",
        recording_path / "timestamps",
        video_folder,
    ]

    for ts_dir in timestamp_dirs:
        if not ts_dir.is_dir():
            continue
        for ts_file in sorted(ts_dir.iterdir()):
            if ts_file.suffix.lower() != ".csv":
                continue
            try:
                with open(ts_file, "r", newline="") as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    if header is None:
                        continue
                    rows = list(reader)
                    if len(rows) < 2:
                        continue

                    frame_count = len(rows)
                    stats["total_frames"] = frame_count

                    # Try to get timestamps for duration/fps calculation
                    timestamp_col = None
                    for i, col_name in enumerate(header):
                        col_lower = col_name.strip().lower()
                        if any(kw in col_lower for kw in ["timestamp", "time", "elapsed", "seconds"]):
                            timestamp_col = i
                            break

                    if timestamp_col is not None and len(rows) >= 2:
                        try:
                            first_ts = float(rows[0][timestamp_col])
                            last_ts = float(rows[-1][timestamp_col])
                            duration = abs(last_ts - first_ts)

                            # If duration seems to be in nanoseconds or milliseconds, convert
                            if duration > 1e15:  # nanoseconds
                                duration /= 1e9
                            elif duration > 1e6:  # milliseconds
                                duration /= 1e3

                            if duration > 0:
                                stats["duration_seconds"] = round(duration, 2)
                                stats["fps"] = round(frame_count / duration, 1)
                        except (ValueError, IndexError):
                            pass

                    # Found a timestamp file — use it and stop
                    return stats
            except (OSError, csv.Error):
                continue

    return stats


def _get_created_timestamp(recording_path: Path) -> str | None:
    """Try to determine the recording creation time from folder name or file metadata."""
    try:
        stat = recording_path.stat()
        from datetime import datetime
        created = datetime.fromtimestamp(stat.st_mtime)
        return created.isoformat(timespec="seconds")
    except OSError:
        return None


def _read_timestamp_values_for_video(recording_path: Path, video_id: str) -> list[float] | None:
    """Read the timestamp CSV for a video and return the list of float timestamps.

    Returns None if no matching CSV can be found or parsed.
    """
    timestamp_dirs = [
        recording_path / "synchronized_videos" / "timestamps" / "camera_timestamps",
        recording_path / "synchronized_videos" / "timestamps",
        recording_path / "timestamps",
    ]

    for ts_dir in timestamp_dirs:
        if not ts_dir.is_dir():
            continue
        for ts_file in ts_dir.iterdir():
            if ts_file.suffix.lower() != ".csv" or video_id not in ts_file.stem:
                continue
            try:
                with open(ts_file, "r", newline="") as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    if header is None:
                        continue
                    rows = list(reader)
                    if len(rows) < 2:
                        continue

                    # Find the timestamp column
                    timestamp_col: int | None = None
                    for i, col_name in enumerate(header):
                        col_lower = col_name.strip().lower()
                        if any(kw in col_lower for kw in ["timestamp", "time", "elapsed", "seconds"]):
                            timestamp_col = i
                            break

                    if timestamp_col is None:
                        continue

                    values: list[float] = []
                    for row in rows:
                        values.append(float(row[timestamp_col]))
                    return values
            except (OSError, csv.Error, ValueError, IndexError):
                continue

    return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@playback_router.get("/viewer", summary="Parquet skeleton viewer (HTML)", include_in_schema=False)
def parquet_viewer() -> FileResponse:
    if not _VIEWER_HTML.is_file():
        raise HTTPException(status_code=404, detail=f"Viewer HTML not found: {_VIEWER_HTML}")
    return FileResponse(str(_VIEWER_HTML), media_type="text/html")


@playback_router.get("/parquet", summary="Serve a parquet file by absolute path", include_in_schema=False)
def serve_parquet(
    path: str = Query(..., description="Absolute path to the .parquet file"),
) -> FileResponse:
    p = Path(path).expanduser().resolve()
    if not p.is_file() or p.suffix.lower() != ".parquet":
        raise HTTPException(status_code=404, detail=f"Parquet file not found: {p}")
    return FileResponse(str(p), media_type="application/octet-stream", filename=p.name)


@playback_router.get("/recordings", summary="List available recordings")
def list_recordings(
    recording_parent_directory: str | None = Query(
        default=None,
        description="Override the default recordings directory",
    ),
) -> list[RecordingListEntry]:
    recordings_dir = (
        Path(recording_parent_directory).expanduser().resolve()
        if recording_parent_directory
        else Path(get_default_freemocap_recordings_path())
    )
    if not recordings_dir.is_dir():
        return []

    entries: list[RecordingListEntry] = []
    for child in sorted(recordings_dir.iterdir(), reverse=True):  # newest first by name
        if not child.is_dir():
            continue
        try:
            video_folder = _find_video_folder(child)
            video_count = sum(
                1 for p in video_folder.iterdir()
                if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
            )
            if video_count > 0:
                total_size = _get_total_size(video_folder)
                created_ts = _get_created_timestamp(child)
                stats = _get_recording_stats(child, video_folder)
                status = compute_recording_status(child)

                stages_complete = sum(1 for s in status.stages if s.complete)
                entries.append(RecordingListEntry(
                    name=child.name,
                    path=str(child),
                    video_count=video_count,
                    total_size_bytes=total_size,
                    created_timestamp=created_ts,
                    total_frames=stats.get("total_frames"),
                    duration_seconds=stats.get("duration_seconds"),
                    fps=stats.get("fps"),
                    status_summary=RecordingStatusSummary(
                        blender_export_ready=status.blender_export_ready,
                        has_blend_file=status.has_blend_file,
                        has_annotated_videos=status.has_annotated_videos,
                        has_calibration_toml=status.has_calibration_toml,
                        stages_complete=stages_complete,
                        stages_total=len(status.stages),
                    ),
                ))
        except (FileNotFoundError, PermissionError):
            continue

    return entries


@playback_router.get(
    "/{recording_id}/status",
    summary="Health/readiness status for a recording (blender inputs, blend file, annotated videos)",
)
def get_recording_status(
    recording_id: str,
    recording_parent_directory: str | None = Query(
        default=None,
        description="Override the default recordings directory",
    ),
) -> RecordingStatus:
    recording_path = _resolve_recording_path(recording_id, recording_parent_directory)
    return compute_recording_status(recording_path)


@playback_router.get(
    "/{recording_id}/videos",
    summary="List videos in a recording",
)
def list_videos(
    recording_id: str,
    recording_parent_directory: str | None = Query(
        default=None,
        description="Override the default recordings directory",
    ),
) -> list[VideoInfo]:
    recording_path = _resolve_recording_path(recording_id, recording_parent_directory)

    try:
        video_folder = _find_video_folder(recording_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    videos = _discover_videos(video_folder)
    if not videos:
        raise HTTPException(status_code=404, detail=f"No video files found in {video_folder}")

    logger.info(f"Discovered {len(videos)} videos in recording '{recording_id}'")
    return [
        VideoInfo(
            video_id=vid_id,
            filename=path.name,
            size_bytes=path.stat().st_size,
            stream_url=f"/freemocap/playback/{recording_id}/videos/{vid_id}",
        )
        for vid_id, path in videos.items()
    ]


@playback_router.get(
    "/{recording_id}/videos/{video_id}",
    summary="Stream a video file (supports HTTP range requests for seeking)",
)
def stream_video(
    recording_id: str,
    video_id: str,
    recording_parent_directory: str | None = Query(
        default=None,
        description="Override the default recordings directory",
    ),
) -> FileResponse:
    recording_path = _resolve_recording_path(recording_id, recording_parent_directory)

    try:
        video_folder = _find_video_folder(recording_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    videos = _discover_videos(video_folder)
    if video_id not in videos:
        raise HTTPException(status_code=404, detail=f"Video '{video_id}' not found in recording '{recording_id}'")

    video_path = videos[video_id]
    if not video_path.is_file():
        raise HTTPException(status_code=404, detail=f"Video file no longer exists: {video_path}")

    suffix = video_path.suffix.lower()
    media_types = {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".avi": "video/x-msvideo",
        ".mov": "video/quicktime",
        ".mkv": "video/x-matroska",
    }
    media_type = media_types.get(suffix, "application/octet-stream")

    return FileResponse(
        path=str(video_path),
        media_type=media_type,
        filename=video_path.name,
    )


@playback_router.get(
    "/{recording_id}/parquet",
    summary="Serve the recording's freemocap_data_by_frame.parquet",
)
def get_recording_parquet(
    recording_id: str,
    recording_parent_directory: str | None = Query(
        default=None,
        description="Override the default recordings directory",
    ),
) -> FileResponse:
    recording_path = _resolve_recording_path(recording_id, recording_parent_directory)
    p = recording_path / "output_data" / "freemocap_data_by_frame.parquet"
    if not p.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"Parquet file not found: {p}",
        )
    return FileResponse(str(p), media_type="application/octet-stream", filename=p.name)


@playback_router.get(
    "/{recording_id}/timestamps",
    summary="Get timestamps for all videos in a recording",
)
def get_all_timestamps(
    recording_id: str,
    recording_parent_directory: str | None = Query(
        default=None,
        description="Override the default recordings directory",
    ),
) -> dict:
    """Return frame timestamps for every video in the recording.

    Response shape: {"timestamps": {"<video_id>": [t0, t1, ...], ...}, "warnings": [...]}
    Videos without discoverable timestamp CSVs produce a warning instead of an error.
    """
    recording_path = _resolve_recording_path(recording_id, recording_parent_directory)

    try:
        video_folder = _find_video_folder(recording_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    videos = _discover_videos(video_folder)
    all_timestamps: dict[str, list[float]] = {}
    warnings: list[str] = []

    for vid_id in videos:
        ts_values = _read_timestamp_values_for_video(recording_path, video_id=vid_id)
        if ts_values is not None:
            all_timestamps[vid_id] = ts_values
        else:
            warnings.append(f"No timestamp data found for video '{vid_id}'")

    return {"timestamps": all_timestamps, "warnings": warnings}


@playback_router.get(
    "/{recording_id}/videos/{video_id}/timestamps",
    summary="Get timestamp data for a specific video in a recording",
)
def get_video_timestamps(
    recording_id: str,
    video_id: str,
    recording_parent_directory: str | None = Query(
        default=None,
        description="Override the default recordings directory",
    ),
) -> dict:
    """Return timestamp CSV info for a specific video.

    Returns a warning instead of 404 when timestamps are not found,
    since not all recordings have timestamp data.
    """
    recording_path = _resolve_recording_path(recording_id, recording_parent_directory)

    timestamp_dirs = [
        recording_path / "synchronized_videos" / "timestamps" / "camera_timestamps",
        recording_path / "synchronized_videos" / "timestamps",
        recording_path / "timestamps",
    ]

    for ts_dir in timestamp_dirs:
        if not ts_dir.is_dir():
            continue
        for ts_file in ts_dir.iterdir():
            if ts_file.suffix.lower() == ".csv" and video_id in ts_file.stem:
                lines = ts_file.read_text().strip().split("\n")
                if len(lines) < 2:
                    continue
                headers = lines[0].split(",")
                rows = [line.split(",") for line in lines[1:]]
                return {
                    "video_id": video_id,
                    "headers": headers,
                    "row_count": len(rows),
                    "file": ts_file.name,
                }

    return {
        "video_id": video_id,
        "warning": f"No timestamp data found for video '{video_id}'",
        "headers": [],
        "row_count": 0,
    }
