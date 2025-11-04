import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from freemocap.app.freemocap_application import get_freemocap_app
from freemocap.core.pipeline.pipeline_configs import CalibrationTaskConfig


logger = logging.getLogger(__name__)

calibration_router = APIRouter(prefix="/calibration", tags=["Calibration"])


# ==================== Request/Response Models ====================




class CalibrationConfigRequest(BaseModel):
    config: CalibrationTaskConfig

class CalibrationConfigResponse(BaseModel):
    success: bool
    message: str | None = None

class StartRecordingRequest(BaseModel):
    config: CalibrationConfigRequest


class StartRecordingResponse(BaseModel):
    success: bool
    message: str | None = None


class CalibrateRecordingRequest(BaseModel):
    calibration_recording_path: str
    config: CalibrationConfigRequest


class CalibrateRecordingResponse(BaseModel):
    success: bool
    message: str | None = None
    results: dict | None = None


# ==================== Endpoints ====================

@calibration_router.post("/config/update/all")
def update_all_calibration_config(request: CalibrationConfigRequest) -> CalibrationConfigResponse:
    """Update calibration configuration."""
    app = get_freemocap_app()
    try:
        app.pipeline_manager.update_calibration_task_config(request.config)
        return CalibrationConfigResponse(success=True, message="Configuration updated")
    except Exception as e:
        logger.exception(f"Error updating calibration config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@calibration_router.post("/recording/start")
def start_recording(request: StartRecordingRequest) -> StartRecordingResponse:
    """Start calibration recording with given config."""
    app = get_freemocap_app()
    try:
        # TODO: Implement actual recording start logic
        # app.pipeline_manager.start_calibration_recording(request.config)
        logger.info(f"Starting recording with config: {request.config}")
        return StartRecordingResponse(success=True, message="Recording started")
    except Exception as e:
        logger.error(f"Error starting recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@calibration_router.post("/recording/stop")
def stop_recording(request: Request) -> dict[str, bool]:
    """Stop current calibration recording."""
    app = get_freemocap_app()
    try:
        # TODO: Implement actual recording stop logic
        # app.pipeline_manager.stop_calibration_recording()
        logger.info("Stopping recording")
        return {"success": True}
    except Exception as e:
        logger.error(f"Error stopping recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@calibration_router.post("/recording/calibrate")
def calibrate_recording(request: CalibrateRecordingRequest) -> CalibrateRecordingResponse:
    """Process and calibrate a recorded session."""
    app = get_freemocap_app()
    try:
        # TODO: Implement actual calibration logic
        # results = app.pipeline_manager.calibrate_recording(
        #     request.calibration_recording_path,
        #     request.config
        # )
        logger.info(f"Calibrating recording at: {request.calibration_recording_path}")
        return CalibrateRecordingResponse(
            success=True,
            message="Calibration completed",
            results={}
        )
    except Exception as e:
        logger.error(f"Error calibrating recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))