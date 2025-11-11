import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pydantic import Field
from skellycam.core.recorders.videos.recording_info import RecordingInfo

from freemocap.app.freemocap_application import get_freemocap_app
from freemocap.core.pipeline.posthoc_pipelines.posthoc_calibration_pipeline.posthoc_calibration_pipeline import \
    CalibrationpipelineConfig

logger = logging.getLogger(__name__)

calibration_router = APIRouter(prefix="/calibration", tags=["Calibration"])


# ==================== Request/Response Models ====================


class CalibrationConfigRequest(BaseModel):
    config: CalibrationpipelineConfig


class CalibrationConfigResponse(BaseModel):
    success: bool
    message: str | None = None


class StartCalibrationRecordingRequest(BaseModel):
    calibration_recording_directory: str = Field(alias="calibrationRecordingDirectory")
    calibration_pipeline_config: CalibrationpipelineConfig = Field(alias="calibrationTaskConfig")

    def to_recording_info(self) -> RecordingInfo:
        recordings_directory = Path(self.calibration_recording_directory).parent
        recording_name = Path(self.calibration_recording_directory).stem
        if not recording_name.endswith('_calibration'):
            recording_name += '_calibration'
        return RecordingInfo(
            recording_directory=str(recordings_directory),
            recording_name=recording_name,
            mic_device_index=-1
        )


class StopCalibrationRecordingRequest(BaseModel):
    calibration_pipeline_config: CalibrationpipelineConfig = Field(alias="calibrationTaskConfig")


class CalibrateRecordingRequest(BaseModel):
    calibration_recording_directory: str = Field(alias="calibrationRecordingDirectory")
    calibration_pipeline_config: CalibrationpipelineConfig = Field(alias="calibrationTaskConfig")

    def to_recording_info(self) -> RecordingInfo:
        return RecordingInfo(
            recording_directory=str(Path(self.calibration_recording_directory).parent),
            recording_name=Path(self.calibration_recording_directory).stem,
            mic_device_index=-1
        )


class StartCalibrationRecordingResponse(BaseModel):
    success: bool
    message: str | None = None


class CalibrateRecordingResponse(BaseModel):
    success: bool
    message: str | None = None
    results: dict | None = None


# ==================== Endpoints ====================

@calibration_router.post("/config/update/all")
def update_all_calibration_config(request: CalibrationConfigRequest) -> CalibrationConfigResponse:
    """Update calibration configuration."""
    try:
        get_freemocap_app().realtime_pipeline_manager.update_calibration_task_config(request.config)
        return CalibrationConfigResponse(success=True, message="Configuration updated")
    except Exception as e:
        logger.exception(f"Error updating calibration config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@calibration_router.post("/recording/start")
async def start_calibration_recording(request: StartCalibrationRecordingRequest) -> StartCalibrationRecordingResponse:
    """Start calibration recording with given config."""
    try:
        recording_info = request.to_recording_info()
        if not recording_info.recording_name.endswith('_calibration'):
            recording_info.recording_name += '_calibration'

        # await get_freemocap_app().create_or_update_realtime_calibration_pipeline(request.calibration_pipeline_config)
        await get_freemocap_app().start_recording_all(recording_info=recording_info, )
        logger.info(f"Starting recording : {recording_info}")
        return StartCalibrationRecordingResponse(success=True, message="Recording started")
    except Exception as e:
        logger.exception(f"Error starting recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@calibration_router.post("/recording/stop")
async def stop_calibration_recording(request: StopCalibrationRecordingRequest) -> dict[str, bool]:
    """Stop current calibration recording."""
    app = get_freemocap_app()
    try:
        recording_info = await app.stop_recording_all()
        await app.create_posthoc_calibration_pipeline(recording_info=recording_info,
                                                      calibration_pipeline_config=request.calibration_pipeline_config)
        logger.info("Stopping recording")
        return {"success": True}
    except Exception as e:
        logger.error(f"Error stopping recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@calibration_router.post("/recording/calibrate")
async def calibrate_recording(request: CalibrateRecordingRequest) -> CalibrateRecordingResponse:
    """Process and calibrate a recorded session."""
    app = get_freemocap_app()
    try:
        recording_info = request.to_recording_info()
        await app.create_posthoc_calibration_pipeline(recording_info=recording_info,
                                                      calibration_pipeline_config=request.calibration_pipeline_config)
        logger.info(f"Calibrating recording at: {recording_info.full_recording_path}")
        return CalibrateRecordingResponse(
            success=True,
            message="Calibration completed",
            results={}
        )
    except Exception as e:
        logger.error(f"Error calibrating recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))
