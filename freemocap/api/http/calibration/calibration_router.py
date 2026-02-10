import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from skellycam.core.recorders.videos.recording_info import RecordingInfo

from freemocap.app.freemocap_application import get_freemocap_app
from freemocap.core.pipeline.shared.pipeline_configs import CalibrationPipelineConfig

logger = logging.getLogger(__name__)

calibration_router = APIRouter(prefix="/calibration", tags=["Calibration"])


# ==================== Request/Response Models ====================


class CalibrationConfigRequest(BaseModel):
    config: CalibrationPipelineConfig


class CalibrationConfigResponse(BaseModel):
    success: bool
    message: str | None = None


class StartCalibrationRecordingRequest(BaseModel):
    calibration_recording_directory: str = Field(alias="calibrationRecordingDirectory")
    calibration_config: CalibrationPipelineConfig = Field(alias="calibrationTaskConfig")

    def to_recording_info(self) -> RecordingInfo:
        recording_dir = Path(self.calibration_recording_directory).expanduser()
        recording_name = recording_dir.stem
        if not recording_name.endswith("_calibration"):
            recording_name += "_calibration"
        return RecordingInfo(
            recording_directory=str(recording_dir.parent),
            recording_name=recording_name,
            mic_device_index=-1,
        )


class StopCalibrationRecordingRequest(BaseModel):
    calibration_config: CalibrationPipelineConfig = Field(alias="calibrationTaskConfig")


class CalibrateRecordingRequest(BaseModel):
    calibration_recording_directory: str = Field(alias="calibrationRecordingDirectory")
    calibration_config: CalibrationPipelineConfig = Field(alias="calibrationTaskConfig")

    def to_recording_info(self) -> RecordingInfo:
        recording_dir = Path(self.calibration_recording_directory).expanduser()
        return RecordingInfo(
            recording_directory=str(recording_dir.parent),
            recording_name=recording_dir.stem,
            mic_device_index=-1,
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
    """Update calibration configuration on all active realtime pipelines."""
    try:
        app = get_freemocap_app()
        from copy import deepcopy
        with app.pipeline_manager.lock:
            for pipeline in app.pipeline_manager.realtime_pipelines.values():
                new_config = deepcopy(pipeline.config)
                new_config.calibration_config = request.config
                pipeline.update_config(new_config=new_config)
        return CalibrationConfigResponse(success=True, message="Configuration updated")
    except Exception as e:
        logger.exception(f"Error updating calibration config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@calibration_router.post("/recording/start")
async def start_calibration_recording(
    request: StartCalibrationRecordingRequest,
) -> StartCalibrationRecordingResponse:
    """Start calibration recording with given config."""
    try:
        recording_info = request.to_recording_info()
        await get_freemocap_app().start_recording_all(recording_info=recording_info)
        logger.info(f"Starting calibration recording: {recording_info}")
        return StartCalibrationRecordingResponse(success=True, message="Recording started")
    except Exception as e:
        logger.exception(f"Error starting calibration recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@calibration_router.post("/recording/stop")
async def stop_calibration_recording(
    request: StopCalibrationRecordingRequest,
) -> dict[str, bool]:
    """Stop current calibration recording and launch posthoc calibration pipeline."""
    app = get_freemocap_app()
    try:
        recording_info = await app.stop_recording_all()
        if recording_info is None:
            raise RuntimeError("No active recording to stop")
        await app.create_posthoc_calibration_pipeline(
            recording_info=recording_info,
            calibration_config=request.calibration_config,
        )
        logger.info("Calibration recording stopped, posthoc calibration pipeline launched")
        return {"success": True}
    except Exception as e:
        logger.error(f"Error stopping calibration recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@calibration_router.post("/recording/calibrate")
async def calibrate_recording(request: CalibrateRecordingRequest) -> CalibrateRecordingResponse:
    """Process and calibrate a previously recorded session."""
    app = get_freemocap_app()
    try:
        recording_info = request.to_recording_info()
        await app.create_posthoc_calibration_pipeline(
            recording_info=recording_info,
            calibration_config=request.calibration_config,
        )
        logger.info(f"Calibrating recording at: {recording_info.full_recording_path}")
        return CalibrateRecordingResponse(
            success=True,
            message="Calibration pipeline launched",
            results={},
        )
    except Exception as e:
        logger.error(f"Error calibrating recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))