import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from skellycam.core.recorders.videos.recording_info import RecordingInfo

from freemocap.app.freemocap_application import get_freemocap_app
from freemocap.core.pipeline.pipeline_configs import MocapPipelineConfig

logger = logging.getLogger(__name__)

mocap_router = APIRouter(prefix="/mocap", tags=["Mocap"])


# ==================== Request/Response Models ====================


class MocapConfigRequest(BaseModel):
    config: MocapPipelineConfig


class MocapConfigResponse(BaseModel):
    success: bool
    message: str | None = None


class StartMocapRecordingRequest(BaseModel):
    mocap_recording_directory: str = Field(alias="mocapRecordingDirectory")
    mocap_config: MocapPipelineConfig = Field(alias="mocapTaskConfig")

    def to_recording_info(self) -> RecordingInfo:
        recording_dir = Path(self.mocap_recording_directory).expanduser()
        recording_name = recording_dir.stem
        if not recording_name.endswith("_mocap"):
            recording_name += "_mocap"
        return RecordingInfo(
            recording_directory=str(recording_dir.parent),
            recording_name=recording_name,
            mic_device_index=-1,
        )


class StopMocapRecordingRequest(BaseModel):
    mocap_config: MocapPipelineConfig = Field(alias="mocapTaskConfig")


class ProcessMocapRecordingRequest(BaseModel):
    mocap_recording_directory: str = Field(alias="mocapRecordingDirectory")
    mocap_config: MocapPipelineConfig = Field(alias="mocapTaskConfig")

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


# ==================== Endpoints ====================


@mocap_router.post("/config/update/all")
def update_all_mocap_config(request: MocapConfigRequest) -> MocapConfigResponse:
    """Update mocap configuration on all active realtime pipelines."""
    try:
        app = get_freemocap_app()
        from copy import deepcopy
        with app.pipeline_manager.lock:
            for pipeline in app.pipeline_manager.realtime_pipelines.values():
                new_config = deepcopy(pipeline.config)
                new_config.mocap_config = request.config
                pipeline.update_config(new_config=new_config)
        return MocapConfigResponse(success=True, message="Mocap configuration updated")
    except Exception as e:
        logger.exception(f"Error updating mocap config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        await app.create_posthoc_mocap_pipeline(
            recording_info=recording_info,
            mocap_config=request.mocap_config,
        )
        logger.info("Mocap recording stopped, posthoc mocap pipeline launched")
        return {"success": True}
    except Exception as e:
        logger.error(f"Error stopping mocap recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@mocap_router.post("/recording/process")
async def process_mocap_recording(request: ProcessMocapRecordingRequest) -> MocapRecordingResponse:
    """Process a previously recorded session with mocap pipeline."""
    app = get_freemocap_app()
    try:
        recording_info = request.to_recording_info()
        await app.create_posthoc_mocap_pipeline(
            recording_info=recording_info,
            mocap_config=request.mocap_config,
        )
        logger.info(f"Processing mocap recording at: {recording_info.full_recording_path}")
        return MocapRecordingResponse(
            success=True,
            message="Mocap processing pipeline launched",
            results={},
        )
    except Exception as e:
        logger.error(f"Error processing mocap recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))