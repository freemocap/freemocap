from freemocap.core.pipeline.posthoc.pipeline_phases import PosthocPipelineType
import logging
import shutil
import tempfile
from copy import deepcopy
from pathlib import Path, PureWindowsPath

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from skellycam.core.recorders.videos.video_file_metadata import probe_video_files
from skellycam.core.recorders.videos.video_copy_plan import VideoCopyPlan
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skelly_synchronize.core.config import synced_video_filename
from skelly_synchronize.core.models import SyncMethod, SyncRequest, SyncResult, VideoBackendKind

from freemocap.app.freemocap_application import get_freemocap_app
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.system.default_paths import FREEMOCAP_TEST_DATA_PATH, default_recording_name, get_default_freemocap_recordings_path

logger = logging.getLogger(__name__)

mocap_router = APIRouter(prefix="/mocap", tags=["Mocap"])


# ==================== Request/Response Models ====================


class MocapConfigRequest(BaseModel):
    config: PosthocMocapPipelineConfig


class MocapConfigResponse(BaseModel):
    success: bool
    message: str | None = None


class StartMocapRecordingRequest(BaseModel):
    mocap_recording_directory: str = Field(alias="mocapRecordingDirectory")
    mocap_config: PosthocMocapPipelineConfig = Field(alias="mocapTaskConfig")

    def to_recording_info(self) -> RecordingInfo:
        recording_dir = Path(self.mocap_recording_directory).expanduser()
        recording_name = recording_dir.name

        return RecordingInfo(
            recording_directory=str(recording_dir.parent),
            recording_name=recording_name,
            mic_device_index=-1,
        )


class StopMocapRecordingRequest(BaseModel):
    mocap_config: PosthocMocapPipelineConfig = Field(alias="mocapTaskConfig")


def _process_mocap_request_schema_extra(schema: dict) -> None:
    schema["examples"] = [ProcessMocapRecordingRequest.create_test_data_request().model_dump()]


class ProcessMocapRecordingRequest(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra=_process_mocap_request_schema_extra,
    )
    mocap_recording_directory: str = Field(alias="mocapRecordingDirectory")
    mocap_config: PosthocMocapPipelineConfig = Field(
        alias="mocapTaskConfig",
        default_factory=PosthocMocapPipelineConfig,
    )

    @classmethod
    def create_test_data_request(cls) -> "ProcessMocapRecordingRequest":
        config = PosthocMocapPipelineConfig(
            calibration_toml_path=str(
                Path(FREEMOCAP_TEST_DATA_PATH) / "freemocap_test_data_camera_calibration.toml"
            ),
        )
        return cls(
            mocap_recording_directory=FREEMOCAP_TEST_DATA_PATH,
            mocap_config=config,
        )

    def to_recording_info(self) -> RecordingInfo:
        recording_dir = Path(self.mocap_recording_directory).expanduser()
        return RecordingInfo(
            recording_directory=str(recording_dir.parent),
            recording_name=recording_dir.name,
            mic_device_index=-1,
        )


class StartMocapRecordingResponse(BaseModel):
    success: bool
    message: str | None = None


class MocapRecordingResponse(BaseModel):
    success: bool
    message: str | None = None
    results: dict | None = None
    pipeline_id: str | None = None


class ImportVideosRequest(BaseModel):
    video_paths: list[str] = Field(alias="videoPaths")
    recording_name: str | None = Field(default=None, alias="recordingName")
    base_directory: str | None = Field(default=None, alias="baseDirectory")
    # If set, skip the frame-count-equality check and copy the *synchronized*
    # output of this completed sync job (see /recording/synchronize) instead
    # of the raw `video_paths` files.
    sync_job_id: str | None = Field(default=None, alias="syncJobId")


class ImportVideosResponse(BaseModel):
    success: bool
    recording_name: str
    recording_path: str
    video_count: int


class CheckVideoSyncRequest(BaseModel):
    video_paths: list[str] = Field(alias="videoPaths")


class VideoSyncInfo(BaseModel):
    filename: str
    frame_count: int
    fps: float
    duration_seconds: float


class CheckVideoSyncResponse(BaseModel):
    synchronized: bool
    videos: list[VideoSyncInfo]
    detail: str | None = None


class SynchronizeVideosRequest(BaseModel):
    video_paths: list[str] = Field(alias="videoPaths")
    method: SyncMethod = Field(default=SyncMethod.AUDIO, alias="method")
    # Only used when method == BRIGHTNESS; see skelly_synchronize.core.models.SyncRequest.
    brightness_ratio_threshold: float = Field(default=1000.0, alias="brightnessRatioThreshold")


class SynchronizeVideosStartResponse(BaseModel):
    job_id: str


# ==================== Endpoints ====================


def _check_video_sync(video_paths: list[str]) -> CheckVideoSyncResponse:
    """Check equal frame counts; synchronization itself must be established upstream."""
    paths = sorted(Path(p).expanduser() for p in video_paths)
    for path in paths:
        if not path.is_file():
            raise HTTPException(status_code=400, detail=f"Video file not found: {path}")

    videos = [
        VideoSyncInfo(
            filename=path.name,
            frame_count=metadata.reported_frame_count,
            fps=metadata.reported_fps,
            duration_seconds=metadata.reported_frame_count / metadata.reported_fps,
        )
        for path, metadata in probe_video_files(paths=paths).items()
    ]

    frame_counts = {video.frame_count for video in videos}
    synchronized = len(frame_counts) == 1

    detail = None
    if not synchronized:
        lines = [f"    {video.filename}: {video.frame_count} frames" for video in videos]
        detail = (
            "Selected videos must have the same frame count to be synchronized, but they differ:\n"
            + "\n".join(lines)
        )

    return CheckVideoSyncResponse(synchronized=synchronized, videos=videos, detail=detail)


@mocap_router.post("/recording/start")
async def start_mocap_recording(
    request: StartMocapRecordingRequest,
) -> StartMocapRecordingResponse:
    """Start mocap recording with given config."""
    try:
        recording_info = request.to_recording_info()
        await get_freemocap_app().start_recording_all(recording_info=recording_info)
        logger.info(f"Starting mocap recording: {recording_info}")
        return StartMocapRecordingResponse(success=True, message="Mocap recording started")
    except Exception as e:
        logger.exception(f"Error starting mocap recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@mocap_router.post("/recording/stop")
async def stop_mocap_recording(request: StopMocapRecordingRequest) -> dict[str, bool]:
    """Stop current mocap recording and launch posthoc mocap pipeline."""
    app = get_freemocap_app()
    try:
        recording_info = await app.stop_recording_all()
        if recording_info is None:
            raise RuntimeError("No active recording to stop")
        pipeline = await app.create_posthoc_mocap_pipeline(
            recording_info=recording_info,
            mocap_config=request.mocap_config,
        )
        logger.info("Mocap recording stopped, posthoc mocap pipeline launched")
        return {
            "success": True,
            "pipeline_id": pipeline.id,
            "recording_name": recording_info.recording_name,
            "recording_path": str(recording_info.full_recording_path),
        }
    except Exception as e:
        logger.exception(f"Error stopping mocap recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@mocap_router.post("/recording/check_sync")
async def check_video_sync(request: CheckVideoSyncRequest) -> CheckVideoSyncResponse:
    """Check whether a set of externally-recorded videos share a frame count (i.e. are synchronized)."""
    if not request.video_paths:
        raise HTTPException(status_code=400, detail="No video files provided")
    return _check_video_sync(request.video_paths)


@mocap_router.post("/recording/synchronize", status_code=201)
async def synchronize_videos(request: SynchronizeVideosRequest) -> SynchronizeVideosStartResponse:
    """Start a background job that aligns/trims a group of videos to a shared frame count.

    Runs skelly_synchronize's audio-cross-correlation or brightness-flash detection
    pipeline in a worker process; poll GET /recording/synchronize/{job_id} (or watch the
    "sync" pipeline-progress websocket messages) for status, then pass the returned job_id
    as `syncJobId` to POST /recording/import to finish the import with the synced output.
    """
    if not request.video_paths:
        raise HTTPException(status_code=400, detail="No video files provided")

    paths = [Path(p).expanduser() for p in request.video_paths]
    for path in paths:
        if not path.is_file():
            raise HTTPException(status_code=400, detail=f"Video file not found: {path}")

    # skelly_synchronize discovers videos by globbing a folder, not an explicit file
    # list, and the user's selected files may live in different source directories —
    # so stage copies under one job-local temp root (raw/ and synchronized/ side by
    # side, so cleanup after import is a single rmtree of the root).
    job_tmp_dir = Path(tempfile.mkdtemp(prefix="freemocap_sync_"))
    raw_folder = job_tmp_dir / "raw"
    raw_folder.mkdir(parents=True)
    try:
        VideoCopyPlan.create(
            source_files=tuple(paths), destination_folder=job_tmp_dir / "synchronized",
            destination_names=tuple(synced_video_filename(raw_video_filename=path.stem) for path in paths),
        )
        staging = VideoCopyPlan.create(
            source_files=tuple(paths), destination_folder=raw_folder,
            destination_names=tuple(path.name for path in paths),
        )
        staging.copy_files()
    except (ValueError, FileNotFoundError, FileExistsError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    sync_request = SyncRequest(
        raw_video_folder_path=raw_folder,
        synchronized_video_folder_path=job_tmp_dir / "synchronized",
        method=request.method,
        video_handler=VideoBackendKind.FFMPEG,
        brightness_ratio_threshold=request.brightness_ratio_threshold,
        create_debug_artifacts=True,
    )
    job = get_freemocap_app().create_sync_job(sync_request)
    job.import_sources = dict(zip(staging.sources, staging.destinations, strict=True))
    logger.info(f"Started sync job [{job.id}] for {len(paths)} video(s), method={request.method}")
    return SynchronizeVideosStartResponse(job_id=job.id)


@mocap_router.get("/recording/synchronize/{job_id}")
async def get_synchronize_result(job_id: str) -> SyncResult:
    """Return the completed result of a sync job started via POST /recording/synchronize."""
    job = get_freemocap_app().sync_job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Sync job not found: {job_id}")
    if job.error is not None:
        raise HTTPException(status_code=500, detail=job.error)
    if not job.finished:
        raise HTTPException(status_code=425, detail="Synchronization still in progress")
    assert job.result is not None
    return job.result


@mocap_router.post("/recording/import")
async def import_videos(request: ImportVideosRequest) -> ImportVideosResponse:
    """Create a new recording folder from externally-recorded videos.

    If `sync_job_id` is set, copies the *synchronized* output of that completed sync
    job (see /recording/synchronize) instead of requiring `video_paths` to already
    share a frame count.
    """
    if not request.video_paths:
        raise HTTPException(status_code=400, detail="No video files provided")

    sync_result: SyncResult | None = None
    if request.sync_job_id:
        job = get_freemocap_app().sync_job_manager.get_job(request.sync_job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Sync job not found: {request.sync_job_id}")
        if job.error is not None:
            raise HTTPException(status_code=500, detail=job.error)
        if not job.finished:
            raise HTTPException(status_code=425, detail="Synchronization still in progress")
        selected_paths = {Path(path).expanduser().resolve() for path in request.video_paths}
        if not job.import_sources or selected_paths != set(job.import_sources):
            raise HTTPException(status_code=400, detail="Selected videos do not match the synchronization job inputs")
        sync_result = job.result
    else:
        check_result = _check_video_sync(request.video_paths)
        if not check_result.synchronized:
            raise HTTPException(status_code=400, detail=check_result.detail)

    base_directory = (
        Path(request.base_directory).expanduser()
        if request.base_directory
        else Path(get_default_freemocap_recordings_path())
    )
    recording_name = request.recording_name or default_recording_name(string_tag="imported")

    if PureWindowsPath(recording_name).name != recording_name or recording_name in {".", ".."}:
        raise HTTPException(status_code=400, detail="Recording name must be a single folder name")
    recording_path = base_directory / recording_name
    synchronized_videos_dir = recording_path / "synchronized_videos"
    if recording_path.exists():
        raise HTTPException(status_code=409, detail=f"Recording already exists: {recording_path}")

    try:
        if sync_result is not None:
            outputs = {video.filepath.name: video.filepath for video in sync_result.videos_after}
            if len(outputs) != len(sync_result.videos_after):
                raise ValueError("Synchronization returned duplicate output filenames")
            source_files: list[Path] = []
            destination_names: list[str] = []
            for video_path in request.video_paths:
                src = Path(video_path).expanduser()
                synced_video = outputs.get(synced_video_filename(raw_video_filename=job.import_sources[src.resolve()].stem))
                if synced_video is None:
                    raise HTTPException(
                        status_code=500,
                        detail=f"No synchronized output found for '{src.name}'",
                    )
                source_files.append(synced_video)
                destination_names.append(f"{src.stem}.mp4")
        else:
            source_files = [Path(path).expanduser() for path in request.video_paths]
            destination_names = [path.name for path in source_files]
        copy_plan = VideoCopyPlan.create(
            source_files=tuple(source_files), destination_folder=synchronized_videos_dir,
            destination_names=tuple(destination_names),
        )
        copy_plan.copy_files()
    except (ValueError, FileNotFoundError, FileExistsError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as e:
        logger.exception(f"Error importing videos into {recording_path}: {e}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e))

    if sync_result is not None and request.sync_job_id:
        # job_tmp_dir is the shared parent of both `raw/` and `synchronized/`
        # (see synchronize_videos()) — one rmtree cleans up both.
        shutil.rmtree(sync_result.synchronized_video_folder_path.parent, ignore_errors=True)
        get_freemocap_app().sync_job_manager.cleanup_job(request.sync_job_id)

    logger.info(f"Imported {len(request.video_paths)} video(s) into {recording_path}")
    return ImportVideosResponse(
        success=True,
        recording_name=recording_name,
        recording_path=str(recording_path),
        video_count=len(request.video_paths),
    )


@mocap_router.post("/recording/process")
async def process_mocap_recording(request: ProcessMocapRecordingRequest) -> MocapRecordingResponse:
    """Process a previously recorded session with mocap pipeline."""
    app = get_freemocap_app()
    try:
        recording_info = request.to_recording_info()
        logger.info(
            f"Processing mocap recording with detector_type='{request.mocap_config.detector_type}', "
            f"tracker_config stages: {[s.name for s in request.mocap_config.tracker_config.stages]}, "
            f"keypoint_detectors: {[[d.detector_type for d in s.keypoint_detectors] for s in request.mocap_config.tracker_config.stages]}"
        )
        pipeline = await app.create_posthoc_mocap_pipeline(
            recording_info=recording_info,
            mocap_config=request.mocap_config,
        )
        logger.info(f"Processing mocap recording at: {recording_info.full_recording_path}")
        return MocapRecordingResponse(
            success=True,
            message="Mocap processing pipeline launched",
            results={},
            pipeline_id=pipeline.id,
        )
    except Exception as e:
        logger.exception(f"Error processing mocap recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@mocap_router.delete("/posthoc/pipelines/{pipeline_id}")
def cancel_posthoc_pipeline(pipeline_id: str) -> None:
    if not get_freemocap_app().posthoc_pipeline_manager.stop_pipeline(
        pipeline_id=pipeline_id, pipeline_type=PosthocPipelineType.MOCAP,
    ):
        raise HTTPException(status_code=404, detail="Pipeline not found in mocap/posthoc")


@mocap_router.delete("/posthoc/pipelines")
def cancel_posthoc_pipelines() -> None:
    get_freemocap_app().posthoc_pipeline_manager.stop_all_pipelines(pipeline_type=PosthocPipelineType.MOCAP)

@mocap_router.delete("/realtime/pipelines/{pipeline_id}")
def cancel_realtime_pipeline(pipeline_id: str) -> None:
    if not get_freemocap_app().realtime_pipeline_manager.stop_pipeline(pipeline_id=pipeline_id):
        raise HTTPException(status_code=404, detail="Pipeline not found in mocap/realtime")


@mocap_router.delete("/realtime/pipelines")
def cancel_realtime_pipelines() -> None:
    get_freemocap_app().realtime_pipeline_manager.shutdown()


@mocap_router.delete("/synchronization/jobs/{job_id}")
def cancel_synchronization_job(job_id: str) -> None:
    if not get_freemocap_app().sync_job_manager.stop_job(job_id=job_id):
        raise HTTPException(status_code=404, detail="Synchronization job not found")
