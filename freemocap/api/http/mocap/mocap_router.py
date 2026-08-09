import logging
import shutil
from copy import deepcopy
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from skellycam.core.recorders.videos.recording_info import RecordingInfo

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
        recording_name = recording_dir.stem

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
            recording_name=recording_dir.stem,
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


class ImportVideosResponse(BaseModel):
    success: bool
    recording_name: str
    recording_path: str
    video_count: int


# ==================== Endpoints ====================


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


@mocap_router.post("/recording/import")
async def import_videos(request: ImportVideosRequest) -> ImportVideosResponse:
    """Create a new recording folder from externally-recorded, pre-synchronized videos."""
    if not request.video_paths:
        raise HTTPException(status_code=400, detail="No video files provided")

    base_directory = (
        Path(request.base_directory).expanduser()
        if request.base_directory
        else Path(get_default_freemocap_recordings_path())
    )
    recording_name = request.recording_name or default_recording_name(string_tag="imported")

    # Legacy layout only — a single `synchronized_videos` folder at the recording root.
    # Not `RecordingStructure.create_on_disk()`: that also creates `videos/annotated`,
    # `output`, and `logs`, which an imported recording (nothing but videos) doesn't need yet.
    recording_path = base_directory / recording_name
    synchronized_videos_dir = recording_path / "synchronized_videos"
    synchronized_videos_dir.mkdir(parents=True, exist_ok=True)

    try:
        for video_path in request.video_paths:
            src = Path(video_path).expanduser()
            if not src.is_file():
                raise HTTPException(status_code=400, detail=f"Video file not found: {video_path}")
            shutil.copy2(src, synchronized_videos_dir / src.name)
    except Exception as e:
        logger.exception(f"Error importing videos into {recording_path}: {e}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e))

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
