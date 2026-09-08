"""
Playback router: serves recording descriptors, numeric windows and video file bytes.
Browser playback uses original video bytes or an in-memory codec compatibility stream.

Endpoints are keyed on {recording_id} (the recording folder name). The full
recording path is resolved as {BASE_RECORDINGS_DIRECTORY}/{recording_id},
with an optional `recording_parent_directory` query param to override the base.

Endpoints:
  GET  /playback/recordings                              — list available recordings
  GET  /playback/{recording_id}/videos                   — list videos in a recording
  GET  /playback/{recording_id}/videos/{video_id}        — stream a video file
"""
import json
import anyio
from collections.abc import AsyncIterator
from starlette.concurrency import run_in_threadpool
from skellycam.core.recorders.videos.browser_stream import BrowserStreamRequest, browser_video_chunks
from urllib.parse import quote, urlencode
import logging
from skellycam.core.recorders.videos.recording_statistics import read_recording_statistics
from pathlib import Path
from freemocap.core.playback.media_selection import (
    PlaybackVideoSource, VIDEO_EXTENSIONS, video_source_folder, discover_video_paths,
)
from typing import Any, Optional

import tomllib
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from skellycam.core.recorders.videos.video_file_metadata import VideoFileMetadata, probe_video_files
from skellycam.core.timestamps.recording_timing_reader import resolve_camera_timing, recorded_camera_timing_path
from skellycam.core.recorders.videos.video_associations import VideoAssociations
from skellycam.core.recorders.videos.video_derivation import VideoDerivation
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

from freemocap.api.http.playback.resource_loading import RecordingResource, ResourceFailure, resource_boundary

logger = logging.getLogger(__name__)

playback_router = APIRouter(prefix="/playback", tags=["Playback"])


@playback_router.get("/{recording_id}/media")
def read_unprocessed_media(
    recording_id: str, recording_parent_directory: str | None = None,
) -> tuple[PlaybackMedia, ...]:
    folder = _resolve_recording_path(recording_id, recording_parent_directory)
    media: list[PlaybackMedia] = []
    associations = VideoAssociations.from_recording_folder(recording_folder=folder)
    video_folder = _find_video_folder(folder)
    for path, metadata in probe_video_files(paths=_discover_videos(video_folder).values()).items():
        source = associations.source_for_path(video_folder=video_folder, video_path=path) if associations else None
        timestamps = tuple(frame / metadata.reported_fps for frame in range(metadata.reported_frame_count))
        if source is not None:
            timestamps = resolve_camera_timing(
                path=recorded_camera_timing_path(recording_folder=folder, camera_id=source),
                frame_count=metadata.reported_frame_count, fps=metadata.reported_fps, offset_s=0.0,
            ).timestamps_s
        media.append(PlaybackMedia(
            video_source=PlaybackVideoSource.SYNCHRONIZED,            video_filename=path.name, nominal_fps=metadata.reported_fps,
            timeline=PlaybackTimeline(sensor_group="cameras", source=source or path.name,
                frame_numbers=tuple(range(metadata.reported_frame_count)), timestamps_s=timestamps),
        ))
    return _include_annotated_media(folder=folder, media=tuple(media))


def _include_annotated_media(*, folder: Path, media: tuple[PlaybackMedia, ...]) -> tuple[PlaybackMedia, ...]:
    raw_folder = video_source_folder(recording=folder, source=PlaybackVideoSource.SYNCHRONIZED)
    originals = {(raw_folder / item.video_filename).resolve(): item for item in media}
    result = list(media)
    directory = folder / ANNOTATED_VIDEOS_FOLDER_NAME
    if not directory.is_dir():
        return media
    for path in discover_video_paths(folder=directory):
        relationship = VideoDerivation.from_video(path=path)
        if relationship is None:
            continue
        original = originals.get((folder / relationship.source_video).resolve())
        if original is None:
            continue
        properties = VideoFileMetadata.from_path(path=path)
        if properties.reported_frame_count != relationship.frame_count or relationship.frame_count != len(original.timeline.frame_numbers):
            raise ValueError(f"Annotated video frame count disagrees with its declared source: {path}")
        result.append(PlaybackMedia(video_source=PlaybackVideoSource.ANNOTATED, video_filename=path.name, nominal_fps=original.nominal_fps, timeline=original.timeline))
    return tuple(result)


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


def preferred_video_source(*, synchronized: VideoSourceInfo, annotated: VideoSourceInfo) -> PlaybackVideoSource:
    candidates = ((PlaybackVideoSource.ANNOTATED, annotated), (PlaybackVideoSource.SYNCHRONIZED, synchronized))
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
    errors: list[ResourceFailure]
    media: tuple[PlaybackMedia, ...]
    recording_fps: Optional[float] = None
    total_frames: Optional[int] = None
    duration_seconds: Optional[float] = None
    videos: VideoSourcesResponse
    calibration: Optional[dict[str, Any]] = None
    tracker_schema: dict[str, Any] | None
    status_summary: RecordingStatusSummary | None


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
    """Find video files in a folder, keyed by complete filename, including extension."""
    videos: dict[str, Path] = {}
    if not folder.is_dir():
        raise FileNotFoundError(f"Not a directory: {folder}")

    for p in sorted(folder.iterdir()):
        if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in VIDEO_EXTENSIONS:
            video_id = p.name
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
            video_id=p.name,
            filename=p.name,
            size_bytes=p.stat().st_size,
            stream_url=(
                f'/freemocap/playback/{quote(recording_id, safe="")}/videos/{quote(p.name, safe="")}'
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
        if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in VIDEO_EXTENSIONS:
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


def _get_recording_stats(recording_path: Path, video_folder: Path, *, use_cv2_fallback: bool = True) -> dict:
    return read_recording_statistics(recording_folder=recording_path, video_folder=video_folder,
                                     inspect_video=use_cv2_fallback)


def _get_created_timestamp(recording_path: Path) -> str | None:
    """Try to determine the recording creation time from folder name or file metadata."""
    try:
        stat = recording_path.stat()
        from datetime import datetime
        created = datetime.fromtimestamp(stat.st_mtime)
        return created.isoformat(timespec="seconds")
    except OSError:
        return None


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
        headers={"Cache-Control": "no-cache"},
    )


@playback_router.get("/{recording_id}/videos/{video_id}/browser")
async def browser_video_stream(
    recording_id: str,
    video_id: str,
    start_seconds: float = Query(ge=0, allow_inf_nan=False),
    duration_seconds: float = Query(gt=0, allow_inf_nan=False),
    source: str | None = None,
    recording_parent_directory: str | None = None,
) -> StreamingResponse:
    file = await run_in_threadpool(stream_video, recording_id=recording_id, video_id=video_id,
        source=source, recording_parent_directory=recording_parent_directory)
    chunks = browser_video_chunks(request=BrowserStreamRequest(path=Path(file.path),
        start_seconds=start_seconds, duration_seconds=duration_seconds))
    try:
        first = await run_in_threadpool(next, chunks)
    except Exception as error:
        await run_in_threadpool(chunks.close)
        raise HTTPException(status_code=422, detail=f"Cannot prepare video playback: {error}") from error

    async def body() -> AsyncIterator[bytes]:
        try:
            yield first
            while (chunk := await run_in_threadpool(next, chunks, None)) is not None:
                yield chunk
        finally:
            with anyio.CancelScope(shield=True):
                await run_in_threadpool(chunks.close)

    return StreamingResponse(body(), media_type="video/mp4", headers={"Cache-Control": "no-store"})


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
    """Load independent resources and return explicit errors beside viable data."""
    recording_path = _resolve_recording_path(recording_id, recording_parent_directory)
    errors: list[ResourceFailure] = []
    sources: dict[str, VideoSourceInfo] = {}
    media: list[PlaybackMedia] = []
    associations = None
    with resource_boundary(resource=RecordingResource.MEDIA_ASSOCIATIONS, item=recording_id, errors=errors):
        associations = VideoAssociations.from_recording_folder(recording_folder=recording_path)
    raw_folder = video_source_folder(recording=recording_path, source=PlaybackVideoSource.SYNCHRONIZED)

    for source, resource in ((PlaybackVideoSource.SYNCHRONIZED, RecordingResource.RAW_VIDEO),
                             (PlaybackVideoSource.ANNOTATED, RecordingResource.ANNOTATED_VIDEO)):
        sources[source] = VideoSourceInfo(available=False, valid=False, video_count=0)
        folder = video_source_folder(recording=recording_path, source=source)
        paths: tuple[Path, ...] = ()
        with resource_boundary(resource=resource, item=str(folder), errors=errors):
            if folder.is_dir():
                paths = discover_video_paths(folder=folder)
        videos: list[VideoInfo] = []
        frame_counts: dict[str, int] = {}
        properties: dict[str, VideoFileMetadata] = {}
        for path in paths:
            with resource_boundary(resource=resource, item=path.name, errors=errors):
                metadata = VideoFileMetadata.from_path(path=path)
                parameters = {"source": source} if folder != recording_path else {}
                if recording_parent_directory:
                    parameters["recording_parent_directory"] = recording_parent_directory
                videos.append(VideoInfo(video_id=path.name, filename=path.name, size_bytes=path.stat().st_size,
                    stream_url=f"/freemocap/playback/{quote(recording_id, safe='')}/videos/{quote(path.name, safe='')}?{urlencode(parameters)}"))
                frame_counts[path.name] = metadata.reported_frame_count
                properties[path.name] = metadata
        valid = len(videos) == len(paths) and len(set(frame_counts.values())) == 1
        if videos and not valid:
            errors.append(ResourceFailure(resource=resource, item=str(folder),
                message=f"Synchronized group is incomplete or has unequal frame counts: {frame_counts}"))
        sources[source] = VideoSourceInfo(available=bool(videos), valid=valid, video_count=len(videos), videos=videos)
        for video_info in sources[source].videos:
            with resource_boundary(resource=resource, item=video_info.filename, errors=errors):
                metadata = properties[video_info.filename]
                source_id = None
                timestamps = tuple(frame / metadata.reported_fps for frame in range(metadata.reported_frame_count))
                with resource_boundary(resource=RecordingResource.TIMING, item=video_info.filename, errors=errors):
                    if associations is not None:
                        source_id = associations.source_for_path(
                            video_folder=raw_folder, video_path=folder / video_info.filename,
                        )
                    if source_id is not None:
                        timestamps = resolve_camera_timing(
                            path=recorded_camera_timing_path(recording_folder=recording_path, camera_id=source_id),
                            frame_count=metadata.reported_frame_count, fps=metadata.reported_fps, offset_s=0.0,
                        ).timestamps_s
                media.append(PlaybackMedia(video_source=source, video_filename=video_info.filename, nominal_fps=metadata.reported_fps,
                    timeline=PlaybackTimeline(sensor_group="cameras", source=source_id or video_info.filename,
                        frame_numbers=tuple(range(metadata.reported_frame_count)), timestamps_s=timestamps)))

    manifest = None
    with resource_boundary(resource=RecordingResource.RECONSTRUCTION, item=recording_id, errors=errors):
        structure = RecordingStructure(base_directory=recording_path.parent, recording_name=recording_path.name)
        if structure.data_parquet_path.is_file():
            manifest = playback_manifest(structure.data_parquet_path)
    if manifest is not None:
        selected = next(run for run in manifest.runs if run.run_id == manifest.selected_run_id)
        saved_media = {(item.video_source, item.video_filename): item for item in selected.media}
        media = [saved_media.get((item.video_source, item.video_filename), item) for item in media]

    originals = {(raw_folder / item.video_filename).resolve(): item for item in media
                 if item.video_source == PlaybackVideoSource.SYNCHRONIZED}
    for index, item in enumerate(media):
        if item.video_source != PlaybackVideoSource.ANNOTATED:
            continue
        with resource_boundary(resource=RecordingResource.MEDIA_ASSOCIATIONS, item=item.video_filename, errors=errors):
            path = recording_path / ANNOTATED_VIDEOS_FOLDER_NAME / item.video_filename
            relationship = VideoDerivation.from_video(path=path)
            if relationship is None:
                continue
            original = originals.get((recording_path / relationship.source_video).resolve())
            if original is None:
                continue
            if len(original.timeline.frame_numbers) != relationship.frame_count or len(item.timeline.frame_numbers) != relationship.frame_count:
                raise ValueError(f"Annotated video frame count disagrees with its declared source: {path}")
            media[index] = item.model_copy(update={"timeline": original.timeline, "nominal_fps": original.nominal_fps})

    calibration = None
    with resource_boundary(resource=RecordingResource.CALIBRATION, item=recording_id, errors=errors):
        if _find_calibration_toml(recording_path) is not None:
            calibration = get_recording_calibration(recording_id=recording_id, recording_parent_directory=recording_parent_directory)
    tracker_schema = None
    with resource_boundary(resource=RecordingResource.TRACKER_SCHEMA, item=recording_id, errors=errors):
        schema_path = recording_path / "tracker_schema.json"
        if schema_path.is_file():
            tracker_schema = json.loads(schema_path.read_text(encoding="utf-8"))
            if not isinstance(tracker_schema, dict):
                tracker_schema = None
                raise ValueError("Tracker schema must be an object")
    stats: dict[str, Any] = {}
    with resource_boundary(resource=RecordingResource.STATISTICS, item=recording_id, errors=errors):
        if media:
            stats = _get_recording_stats(recording_path, _find_video_folder(recording_path))
    status_summary = None
    with resource_boundary(resource=RecordingResource.STATUS, item=recording_id, errors=errors):
        status = compute_recording_status(recording_path)
        status_summary = RecordingStatusSummary(
            blender_export_ready=status.blender_export_ready, has_blend_file=status.has_blend_file,
            has_annotated_videos=status.has_annotated_videos, has_calibration_toml=status.has_calibration_toml,
            stages_complete=sum(1 for stage in status.stages if stage.complete), stages_total=len(status.stages))
    preferred = preferred_video_source(synchronized=sources[PlaybackVideoSource.SYNCHRONIZED],
        annotated=sources[PlaybackVideoSource.ANNOTATED]) if any(source.available for source in sources.values()) else PlaybackVideoSource.SYNCHRONIZED
    return RecordingBundle(
        recording_id=recording_id, manifest=manifest, errors=errors, media=tuple(media),
        videos=VideoSourcesResponse(preferred_source=preferred, sources=sources),
        recording_fps=stats.get("fps"), total_frames=stats.get("total_frames"), duration_seconds=stats.get("duration_seconds"),
        calibration=calibration, tracker_schema=tracker_schema, status_summary=status_summary,
    )
