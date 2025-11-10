import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pydantic import Field
from skellycam.core.recorders.videos.recording_info import RecordingInfo

from freemocap.app.freemocap_application import get_freemocap_app
from freemocap.core.pipeline.posthoc_pipelines.posthoc_mocap_pipeline.posthoc_mocap_pipeline import \
    MocapTaskConfig

logger = logging.getLogger(__name__)

mocap_router = APIRouter(prefix="/mocap", tags=["Mocap"])


# ==================== Request/Response Models ====================


class MocapConfigRequest(BaseModel):
    config: MocapTaskConfig


class MocapConfigResponse(BaseModel):
    success: bool
    message: str | None = None


class StartMocapRecordingRequest(BaseModel):
    mocap_recording_directory: str = Field(alias="mocapRecordingDirectory")
    mocap_task_config: MocapTaskConfig = Field(alias="mocapTaskConfig")

    def to_recording_info(self) -> RecordingInfo:
        recordings_directory = Path(self.mocap_recording_directory).parent
        recording_name = Path(self.mocap_recording_directory).stem
        if not recording_name.endswith('_mocap'):
            recording_name += '_mocap'
        return RecordingInfo(
            recording_directory=str(recordings_directory),
            recording_name=recording_name,
            mic_device_index=-1
        )


class StopMocapRecordingRequest(BaseModel):
    mocap_task_config: MocapTaskConfig = Field(alias="mocapTaskConfig")


class ProcessMocapRecordingRequest(BaseModel):
    mocap_recording_directory: str = Field(alias="mocapRecordingDirectory")
    mocap_task_config: MocapTaskConfig = Field(alias="mocapTaskConfig")

    def to_recording_info(self) -> RecordingInfo:
        return RecordingInfo(
            recording_directory=str(Path(self.mocap_recording_directory).parent),
            recording_name=Path(self.mocap_recording_directory).stem,
            mic_device_index=-1
        )


class StartMocapRecordingResponse(BaseModel):
    success: bool
    message: str | None = None


class MocapRecordingResponse(BaseModel):
    success: bool
    message: str | None = None
    results: dict | None = None


# ==================== Endpoints ====================

@mocap_router.post("/config/update/all")
def update_all_mocap_config(request: MocapConfigRequest) -> MocapConfigResponse:
    """Update mocap configuration."""
    try:
        get_freemocap_app().realtime_pipeline_manager.update_mocap_task_config(request.config)
        return MocapConfigResponse(success=True, message="Mocap Configuration updated")
    except Exception as e:
        logger.exception(f"Error updating mocap config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@mocap_router.post("/recording/start")
async def start_mocap_recording(request: StartMocapRecordingRequest) -> StartMocapRecordingResponse:
    """Start mocap recording with given config."""
    try:
        recording_info = request.to_recording_info()
        if not recording_info.recording_name.endswith('_mocap'):
            recording_info.recording_name += '_mocap'

        # await get_freemocap_app().create_or_update_realtime_mocap_pipeline(request.mocap_task_config)
        await get_freemocap_app().start_recording_all(recording_info=recording_info, )
        logger.info(f"Starting mocap recording : {recording_info}")
        return StartMocapRecordingResponse(success=True, message="Mocap recording started")
    except Exception as e:
        logger.exception(f"Error starting recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@mocap_router.post("/recording/stop")
async def stop_mocap_recording(request: StopMocapRecordingRequest) -> dict[str, bool]:
    """Stop current mocap recording."""
    app = get_freemocap_app()
    try:
        recording_info = await app.stop_recording_all()
        await app.posthoc_pipeline_manager.create_posthoc_mocap_pipeline(recording_info=recording_info,
                                                                         mocap_task_config=request.mocap_task_config)
        logger.info("Stopping recording")
        return {"success": True}
    except Exception as e:
        logger.error(f"Error stopping recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@mocap_router.post("/recording/process")
async def calibrate_recording(request: ProcessMocapRecordingRequest) -> MocapRecordingResponse:
    """Process and calibrate a recorded session."""
    app = get_freemocap_app()
    try:
        recording_info = request.to_recording_info()
        await app.posthoc_pipeline_manager.create_posthoc_mocap_pipeline(recording_info=recording_info,
                                                                         mocap_task_config=request.mocap_task_config)
        logger.info(f"Calibrating recording at: {recording_info.full_recording_path}")
        return MocapRecordingResponse(
            success=True,
            message="Mocap processing pipeline completed",
            results={}
        )
    except Exception as e:
        logger.error(f"Error calibrating recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))
