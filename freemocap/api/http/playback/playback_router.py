"""
Playback router: serves recording descriptors, numeric windows and video file bytes.
Video decoding and frame caching belong to the playback client.

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
from enum import StrEnum
import logging
from pathlib import Path
from typing import Any, Optional

import tomllib
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from skellycam.core.recorders.videos.video_file_metadata import VideoFileMetadata, probe_video_files
from skellycam.core.timestamps.recording_timing_reader import resolve_camera_timing, camera_timing_path
from freemocap.core.pipeline.posthoc.video_group_helper import VideoHelper
from freemocap.core.recording.playback_queries import (
    PlaybackManifest, PlaybackWindow, PlaybackWindowRequest, StalePlaybackRevision,
    playback_manifest, playback_window, PlaybackMedia, PlaybackTimeline,
)
from pydantic import BaseModel

from freemocap.system.recording_status.recording_status import (
    RecordingStatus,
    compute_recording_status,
    _find_calibration_toml,
)
from freemocap.system.recording_structure.recording_structure import (
    RecordingLayoutValidation,
    RecordingStructure,
)
from freemocap.system.default_paths import (
    ANNOTATED_VIDEOS_FOLDER_NAME,
    SYNCHRONIZED_VIDEOS_FOLDER_NAME,
    get_default_freemocap_recordings_path,
)

_VIEWER_HTML = Path(__file__).parent.parent.parent.parent / "core" / "viz" / "parquet_viewer.html"

logger = logging.getLogger(__name__)

playback_router = APIRouter(prefix="/playback", tags=["Playback"])


@playback_router.get("/{recording_id}/media")
def read_unprocessed_media(
    recording_id: str, recording_parent_directory: str | None = None,
) -> tuple[PlaybackMedia, ...]:
    folder = _resolve_recording_path(recording_id, recording_parent_directory)
    media: list[PlaybackMedia] = []
    for path in _discover_videos(_find_video_folder(folder)).values():
        video = VideoHelper.from_video_path(path)
        try:
            timing = resolve_camera_timing(
                path=camera_timing_path(recording_folder=folder, camera_id=video.metadata.camera_id),
                frame_count=video.metadata.frame_count, fps=video.metadata.fps, offset_s=0.0,
            )
            media.append(PlaybackMedia(
                video_filename=path.name, nominal_fps=video.metadata.fps,
                timeline=PlaybackTimeline(sensor_group="cameras", source=video.metadata.camera_id,
                    frame_numbers=tuple(range(video.metadata.frame_count)), timestamps_s=timing.timestamps_s),
            ))
        finally:
            video.close()
    return _include_annotated_media(folder=folder, media=tuple(media))


def _include_annotated_media(*, folder: Path, media: tuple[PlaybackMedia, ...]) -> tuple[PlaybackMedia, ...]:
    """Frame-preserving annotations inherit the original camera timeline."""
    result = list(media)
    for original in media:
        filename = Path(original.video_filename)
        annotated = folder / ANNOTATED_VIDEOS_FOLDER_NAME / f"{filename.stem}_annotated{filename.suffix}"
        if not annotated.is_file():
            continue
        video = VideoFileMetadata.from_path(path=annotated)
        if len(original.timeline.frame_numbers) != video.reported_frame_count:
            raise ValueError(
                f"Annotated video '{annotated.name}' does not match its source: "
                f"{video.reported_frame_count} frames versus {len(original.timeline.frame_numbers)} source frames."
            )
        result.append(PlaybackMedia(
            video_filename=annotated.name, nominal_fps=original.nominal_fps,
            timeline=original.timeline,
        ))
    return tuple(result)


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


class VideoSourceInfo(BaseModel):
    available: bool
    valid: bool
    video_count: int
    videos: list[VideoInfo] = []


class VideoSourcesResponse(BaseModel):
    preferred_source: str
    sources: dict[str, VideoSourceInfo]


class PlaybackVideoSource(StrEnum):
    SYNCHRONIZED = "synchronized"
    ANNOTATED = "annotated"


def preferred_video_source(*, synchronized: VideoSourceInfo, annotated: VideoSourceInfo) -> PlaybackVideoSource:
    candidates = ((PlaybackVideoSource.SYNCHRONIZED, synchronized), (PlaybackVideoSource.ANNOTATED, annotated))
    for name, source in candidates:
        if source.available and source.valid:
            return name
    for name, source in candidates:
        if source.available:
            return name
    raise ValueError("No playback video source is available")


class RecordingStatusSummary(BaseModel):
    blender_export_ready: bool = False
    has_blend_file: bool = False
    has_annotated_videos: bool = False
    has_calibration_toml: bool = False
    stages_complete: int = 0
    stages_total: int = 0


class RecordingBundle(BaseModel):
    """All playback metadata for a recording in a single response."""
    recording_id: str
    manifest: PlaybackManifest | None
    media: tuple[PlaybackMedia, ...]
    recording_fps: Optional[float] = None
    total_frames: Optional[int] = None
    duration_seconds: Optional[float] = None
    videos: VideoSourcesResponse
    timestamps: dict = {}
    calibration: Optional[dict[str, Any]] = None
    tracker_schema: dict[str, Any]
    status_summary: RecordingStatusSummary


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
    status: Optional[RecordingStatus] = None
    layout_validation: Optional[RecordingLayoutValidation] = None


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
    if recording_path.parent != parent:
        raise HTTPException(status_code=400, detail="Invalid recording_id")

    if not recording_path.is_dir():
        raise HTTPException(
            status_code=404,
            detail=f"Recording directory not found: {recording_path}",
        )
    return recording_path


@playback_router.get("/{recording_id}/manifest")
def get_playback_manifest(recording_id: str, recording_parent_directory: str | None = None) -> PlaybackManifest | None:
    folder = _resolve_recording_path(recording_id, recording_parent_directory)
    structure = RecordingStructure(base_directory=folder.parent, recording_name=folder.name)
    if not structure.data_parquet_path.is_file():
        return None
    try:
        manifest = playback_manifest(structure.data_parquet_path)
        return manifest.model_copy(update={"runs": tuple(
            run.model_copy(update={"media": _include_annotated_media(folder=folder, media=run.media)})
            for run in manifest.runs
        )})
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@playback_router.post("/{recording_id}/window")
def get_playback_window(recording_id: str, request: PlaybackWindowRequest,
    recording_parent_directory: str | None = None) -> PlaybackWindow:
    folder = _resolve_recording_path(recording_id, recording_parent_directory)
    structure = RecordingStructure(base_directory=folder.parent, recording_name=folder.name)
    try:
        return playback_window(path=structure.data_parquet_path, request=request)
    except StalePlaybackRevision as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="Recording data is unavailable") from error


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


def _validate_video_source(
    recording_path: Path,
    source_name: str,
    recording_id: str,
    recording_parent_directory: str | None = None,
) -> VideoSourceInfo:
    """Check video readability and frame counts without assigning camera identities."""
    folder_name = (
        ANNOTATED_VIDEOS_FOLDER_NAME if source_name == "annotated"
        else SYNCHRONIZED_VIDEOS_FOLDER_NAME
    )
    folder = recording_path / folder_name

    if not folder.is_dir():
        return VideoSourceInfo(available=False, valid=False, video_count=0)

    video_paths = sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
    )
    if not video_paths:
        return VideoSourceInfo(available=False, valid=False, video_count=0)

    try:
        metadata = probe_video_files(paths=video_paths)
    except (ValueError, RuntimeError, OSError) as error:
        raise HTTPException(status_code=422, detail=f"Cannot inspect video source '{folder}': {error}") from error
    frame_counts = {path.name: video.reported_frame_count for path, video in metadata.items()}
    if len(set(frame_counts.values())) != 1:
        raise HTTPException(status_code=422, detail={"message": "Video frame counts differ", "files": frame_counts})

    parent_directory_suffix = (
        f"&recording_parent_directory={recording_parent_directory}"
        if recording_parent_directory
        else ""
    )
    videos = [
        VideoInfo(
            video_id=p.stem,
            filename=p.name,
            size_bytes=p.stat().st_size,
            stream_url=(
                f"/freemocap/playback/{recording_id}/videos/{p.stem}"
                f"?source={source_name}{parent_directory_suffix}"
            ),
        )
        for p in video_paths
    ]

    return VideoSourceInfo(
        available=True,
        valid=True,
        video_count=len(videos),
        videos=videos,
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


def _get_recording_stats(
    recording_path: Path,
    video_folder: Path,
    *,
    use_cv2_fallback: bool = True,
) -> dict:
    """Try to extract frame count, duration, and fps from timestamp CSV files.

    When *use_cv2_fallback* is False the cv2 VideoCapture path is skipped
    entirely. Callers that iterate many recordings (e.g. the listing endpoint)
    should pass False to avoid opening video files for every recording on disk.
    """
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

    if not use_cv2_fallback:
        return stats

    # No timestamp CSV found — fall back to reading video metadata with cv2
    logger.warning(
        f"No timestamp CSVs found for '{recording_path.name}'. "
        f"Searched: {[str(d) for d in timestamp_dirs]}. Falling back to cv2."
    )
    try:
        import cv2
        video_files = sorted(
            p for p in video_folder.iterdir()
            if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
        )
        if video_files:
            cap = cv2.VideoCapture(str(video_files[0]))
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            cap.release()
            if frame_count > 0:
                stats["total_frames"] = frame_count
                if fps and fps > 0:
                    stats["fps"] = round(fps, 1)
                    stats["duration_seconds"] = round(frame_count / fps, 2)
                logger.info(
                    f"cv2 fallback for '{recording_path.name}': "
                    f"{frame_count} frames @ {fps:.1f} fps "
                    f"(from '{video_files[0].name}')"
                )
            else:
                logger.warning(
                    f"cv2 read 0 frames from '{video_files[0].name}' — "
                    f"video may be unreadable or empty"
                )
    except Exception as e:
        logger.warning(f"cv2 fallback failed for '{video_folder}': {e}")

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
                stats = _get_recording_stats(child, video_folder, use_cv2_fallback=False)
                status = compute_recording_status(child)
                layout_validation = RecordingStructure(
                    base_directory=child.parent,
                    recording_name=child.name,
                ).validate_layout()

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
                    status=status,
                    layout_validation=layout_validation,
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
    summary="List videos in a recording (annotated + synchronized sources)",
    response_model=VideoSourcesResponse,
)
def list_videos(
    recording_id: str,
    recording_parent_directory: str | None = Query(
        default=None,
        description="Override the default recordings directory",
    ),
) -> VideoSourcesResponse:
    recording_path = _resolve_recording_path(recording_id, recording_parent_directory)

    annotated = _validate_video_source(recording_path, "annotated", recording_id, recording_parent_directory)
    synchronized = _validate_video_source(recording_path, "synchronized", recording_id, recording_parent_directory)

    # Fall back to recording root for layouts where videos live directly in the
    # recording folder (not in synchronized_videos/ or annotated_videos/).
    if not annotated.available and not synchronized.available:
        try:
            video_folder = _find_video_folder(recording_path)
            videos = _discover_videos(video_folder)
            if videos:
                parent_directory_suffix = (
                    f"?recording_parent_directory={recording_parent_directory}"
                    if recording_parent_directory
                    else ""
                )
                video_list = [
                    VideoInfo(
                        video_id=vid_id,
                        filename=path.name,
                        size_bytes=path.stat().st_size,
                        stream_url=f"/freemocap/playback/{recording_id}/videos/{vid_id}{parent_directory_suffix}",
                    )
                    for vid_id, path in videos.items()
                ]
                root_source = VideoSourceInfo(
                    available=True,
                    valid=False,
                    video_count=len(video_list),
                    videos=video_list,
                )
                logger.info(
                    f"Recording '{recording_id}': no subfolder sources; "
                    f"found {len(video_list)} video(s) in recording root"
                )
                return VideoSourcesResponse(
                    preferred_source="synchronized",
                    sources={
                        "annotated": VideoSourceInfo(available=False, valid=False, video_count=0),
                        "synchronized": root_source,
                    },
                )
        except FileNotFoundError:
            pass

        raise HTTPException(
            status_code=404,
            detail=f"No video files found in {recording_path}",
        )

    preferred = preferred_video_source(synchronized=synchronized, annotated=annotated)

    logger.info(
        f"Recording '{recording_id}': annotated={annotated.available}/{annotated.valid}, "
        f"synchronized={synchronized.available}/{synchronized.valid}, "
        f"preferred={preferred}"
    )

    return VideoSourcesResponse(
        preferred_source=preferred,
        sources={
            "annotated": annotated,
            "synchronized": synchronized,
        },
    )


def _resolve_video_source_folder(recording_path: Path, source: str) -> Path:
    """Resolve the folder for a named video source."""
    folder_name = (
        ANNOTATED_VIDEOS_FOLDER_NAME if source == "annotated"
        else SYNCHRONIZED_VIDEOS_FOLDER_NAME
    )
    folder = recording_path / folder_name
    if not folder.is_dir():
        raise HTTPException(
            status_code=404,
            detail=f"Video source '{source}' not found in recording",
        )
    return folder


@playback_router.get(
    "/{recording_id}/videos/{video_id}",
    summary="Stream a video file (supports HTTP range requests for seeking)",
)
def stream_video(
    recording_id: str,
    video_id: str,
    source: str | None = Query(
        default=None,
        description="Video source folder: 'annotated' or 'synchronized'. Defaults to synchronized-first lookup.",
    ),
    recording_parent_directory: str | None = Query(
        default=None,
        description="Override the default recordings directory",
    ),
) -> FileResponse:
    recording_path = _resolve_recording_path(recording_id, recording_parent_directory)

    if source:
        video_folder = _resolve_video_source_folder(recording_path, source)
    else:
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
    summary="Serve the recording's canonical Parquet",
)
def get_recording_parquet(
    recording_id: str,
    recording_parent_directory: str | None = Query(
        default=None,
        description="Override the default recordings directory",
    ),
) -> FileResponse:
    recording_path = _resolve_recording_path(recording_id, recording_parent_directory)
    p = _find_recording_parquet(recording_path)
    if p is None:
        raise HTTPException(
            status_code=404,
            detail=f"No parquet file found in recording: {recording_path}",
        )
    return FileResponse(str(p), media_type="application/octet-stream", filename=p.name)


def _find_recording_parquet(recording_path: Path) -> Path | None:
    """Resolve only the recording's explicitly named canonical dataset."""
    name = recording_path.name
    canonical = recording_path / f"{name}_data.parquet"
    if canonical.is_file():
        logger.info(f"Found canonical parquet: {canonical}")
        return canonical

    return None


@playback_router.get(
    "/{recording_id}/calibration",
    summary="Return parsed calibration data (camera poses) for a recording",
)
def get_recording_calibration(
    recording_id: str,
    recording_parent_directory: str | None = Query(
        default=None,
        description="Override the default recordings directory",
    ),
) -> dict[str, Any]:
    """Parse the recording's calibration TOML and return camera pose data.

    Returns JSON matching the frontend LoadedCalibration shape:
      { path, mtimeMs, cameras: [...], metadata }
    Returns 404 if no calibration TOML is present in the recording folder.
    """
    recording_path = _resolve_recording_path(recording_id, recording_parent_directory)
    toml_path = _find_calibration_toml(recording_path)
    if toml_path is None:
        raise HTTPException(
            status_code=404,
            detail=f"No calibration TOML found in recording: {recording_path}",
        )

    try:
        raw = toml_path.read_text(encoding="utf-8")
        parsed = tomllib.loads(raw)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse calibration TOML: {e}")

    mtime_ms = toml_path.stat().st_mtime * 1000

    cameras = []
    for key, val in parsed.items():
        if key == "metadata" or not isinstance(val, dict):
            continue
        if "world_position" not in val or "world_orientation" not in val:
            continue
        cameras.append({
            "id": key,
            "name": str(val.get("name", key)),
            "size": val.get("size"),
            "matrix": val.get("matrix"),
            "distortions": val.get("distortions"),
            "rotation": val.get("rotation"),
            "translation": val.get("translation"),
            "world_orientation": val["world_orientation"],
            "world_position": val["world_position"],
        })

    return {
        "path": str(toml_path),
        "mtimeMs": mtime_ms,
        "cameras": cameras,
        "metadata": parsed.get("metadata", None),
    }


@playback_router.get(
    "/{recording_id}/tracker-schema",
    summary="Return the tracker schema (tracked points + connections) for a recording",
)
def get_tracker_schema(
    recording_id: str,
    recording_parent_directory: str | None = Query(
        default=None,
        description="Override the default recordings directory",
    ),
) -> dict[str, Any]:
    """Serve the tracker_schema.json saved alongside the mocap outputs.

    Returns the TrackedObjectDefinition (name, tracker_type, landmark_schema,
    tracked_points, connections) so the frontend can render skeleton lines
    without hardcoding any tracker schema.

    Returns 404 for older recordings that predate schema saving.
    """
    import json

    recording_path = _resolve_recording_path(recording_id, recording_parent_directory)
    schema_path = recording_path / "tracker_schema.json"
    if not schema_path.is_file():
        logger.warning(f"No tracker_schema.json in {recording_path}, returning fallback")
        return {
            "name": "fallback",
            "tracker_type": "unknown",
            "tracked_points": [],
            "connections": [],
            "landmark_schema": "generic",
        }
    return json.loads(schema_path.read_text(encoding="utf-8"))


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


# ---------------------------------------------------------------------------
# Bundle endpoint — single call for all playback metadata
# ---------------------------------------------------------------------------

@playback_router.get(
    "/{recording_id}/bundle",
    summary="All playback metadata for a recording in a single response",
)
def get_recording_bundle(
    recording_id: str,
    recording_parent_directory: str | None = Query(
        default=None,
        description="Override the default recordings directory",
    ),
) -> RecordingBundle:
    """Return videos, timestamps, calibration, tracker schema, and status
    in one response. Individual resources are best-effort — calibration
    returns null if no TOML is present, tracker schema returns a fallback
    if no schema file exists. Only path resolution can produce a 404.
    """
    import json

    recording_path = _resolve_recording_path(recording_id, recording_parent_directory)

    # --- videos ---
    annotated = _validate_video_source(recording_path, "annotated", recording_id, recording_parent_directory)
    synchronized = _validate_video_source(recording_path, "synchronized", recording_id, recording_parent_directory)

    if not annotated.available and not synchronized.available:
        try:
            video_folder = _find_video_folder(recording_path)
            videos_dict = _discover_videos(video_folder)
            if videos_dict:
                parent_directory_suffix = (
                    f"?recording_parent_directory={recording_parent_directory}"
                    if recording_parent_directory
                    else ""
                )
                video_list = [
                    VideoInfo(
                        video_id=vid_id,
                        filename=path.name,
                        size_bytes=path.stat().st_size,
                        stream_url=f"/freemocap/playback/{recording_id}/videos/{vid_id}{parent_directory_suffix}",
                    )
                    for vid_id, path in videos_dict.items()
                ]
                root_source = VideoSourceInfo(
                    available=True,
                    valid=False,
                    video_count=len(video_list),
                    videos=video_list,
                )
                videos_response = VideoSourcesResponse(
                    preferred_source="synchronized",
                    sources={
                        "annotated": VideoSourceInfo(available=False, valid=False, video_count=0),
                        "synchronized": root_source,
                    },
                )
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"No video files found in {recording_path}",
                )
        except FileNotFoundError:
            raise HTTPException(
                status_code=404,
                detail=f"No video files found in {recording_path}",
            )
    else:
        preferred = preferred_video_source(synchronized=synchronized, annotated=annotated)
        videos_response = VideoSourcesResponse(
            preferred_source=preferred,
            sources={
                "annotated": annotated,
                "synchronized": synchronized,
            },
        )

    # --- timestamps ---
    timestamps_result: dict = {}
    stats_video_folder = None
    try:
        stats_video_folder = _find_video_folder(recording_path)
        all_timestamps: dict[str, list[float]] = {}
        warnings: list[str] = []
        for vid_id in _discover_videos(stats_video_folder):
            ts_values = _read_timestamp_values_for_video(recording_path, video_id=vid_id)
            if ts_values is not None:
                all_timestamps[vid_id] = ts_values
            else:
                warnings.append(f"No timestamp data found for video '{vid_id}'")
        timestamps_result = {"timestamps": all_timestamps, "warnings": warnings}
    except FileNotFoundError:
        pass

    # --- calibration ---
    calibration_result: dict[str, Any] | None = None
    toml_path = _find_calibration_toml(recording_path)
    if toml_path is not None:
        try:
            raw = toml_path.read_text(encoding="utf-8")
            parsed = tomllib.loads(raw)
            mtime_ms = toml_path.stat().st_mtime * 1000
            cameras = []
            for key, val in parsed.items():
                if key == "metadata" or not isinstance(val, dict):
                    continue
                if "world_position" not in val or "world_orientation" not in val:
                    continue
                cameras.append({
                    "id": key,
                    "name": str(val.get("name", key)),
                    "size": val.get("size"),
                    "matrix": val.get("matrix"),
                    "distortions": val.get("distortions"),
                    "rotation": val.get("rotation"),
                    "translation": val.get("translation"),
                    "world_orientation": val["world_orientation"],
                    "world_position": val["world_position"],
                })
            calibration_result = {
                "path": str(toml_path),
                "mtimeMs": mtime_ms,
                "cameras": cameras,
                "metadata": parsed.get("metadata", None),
            }
        except Exception:
            logger.warning(f"Failed to parse calibration TOML for '{recording_id}'", exc_info=True)

    # --- tracker schema ---
    schema_path = recording_path / "tracker_schema.json"
    if schema_path.is_file():
        try:
            tracker_schema_result = json.loads(schema_path.read_text(encoding="utf-8"))
        except Exception:
            tracker_schema_result = {
                "name": "fallback",
                "tracker_type": "unknown",
                "tracked_points": [],
                "connections": [],
                "landmark_schema": "generic",
            }
    else:
        tracker_schema_result = {
            "name": "fallback",
            "tracker_type": "unknown",
            "tracked_points": [],
            "connections": [],
            "landmark_schema": "generic",
        }

    # --- recording stats ---
    stats = {}
    if stats_video_folder is not None:
        try:
            stats = _get_recording_stats(recording_path, stats_video_folder)
        except Exception:
            pass

    # --- status summary ---
    status = compute_recording_status(recording_path)
    status_summary = RecordingStatusSummary(
        blender_export_ready=status.blender_export_ready,
        has_blend_file=status.has_blend_file,
        has_annotated_videos=status.has_annotated_videos,
        has_calibration_toml=status.has_calibration_toml,
        stages_complete=sum(1 for s in status.stages if s.complete),
        stages_total=len(status.stages),
    )

    manifest = get_playback_manifest(recording_id=recording_id, recording_parent_directory=recording_parent_directory)
    media = read_unprocessed_media(recording_id=recording_id, recording_parent_directory=recording_parent_directory) if manifest is None else next(
        run.media for run in manifest.runs if run.run_id == manifest.selected_run_id
    )
    return RecordingBundle(
        manifest=manifest,
        media=media,
        recording_id=recording_id,
        recording_fps=stats.get("fps"),
        total_frames=stats.get("total_frames"),
        duration_seconds=stats.get("duration_seconds"),
        videos=videos_response,
        timestamps=timestamps_result,
        calibration=calibration_result,
        tracker_schema=tracker_schema_result,
        status_summary=status_summary,
    )
