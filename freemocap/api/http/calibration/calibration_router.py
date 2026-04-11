import json
import logging
from copy import deepcopy
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from skellycam.core.recorders.videos.recording_info import RecordingInfo

from freemocap.app.freemocap_application import get_freemocap_app
from freemocap.core.tasks.calibration.calibration_task_config import PosthocCalibrationPipelineConfig
from freemocap.system.default_paths import FREEMOCAP_TEST_DATA_PATH

logger = logging.getLogger(__name__)

calibration_router = APIRouter(prefix="/calibration", tags=["Capture Volume Calibration"])


# ==================== Request/Response Models ====================


class CalibrationConfigRequest(BaseModel):
    config: PosthocCalibrationPipelineConfig


class CalibrationConfigResponse(BaseModel):
    success: bool
    message: str | None = None


def _calibrate_request_schema_extra(schema: dict) -> None:
    schema["examples"] = [CalibrateRecordingRequest.create_test_data_request().model_dump(by_alias=True)]


class CalibrateRecordingRequest(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra=_calibrate_request_schema_extra,
    )
    calibration_config: PosthocCalibrationPipelineConfig = Field(
        alias="calibrationTaskConfig",
        default_factory=PosthocCalibrationPipelineConfig,
    )
    calibration_recording_directory: str | None = Field(
        alias="calibrationRecordingDirectory",
        description="Optional directory for calibration recording, if None/null use most recent successful recording", )

    def to_recording_info(self) -> RecordingInfo:
        if self.calibration_recording_directory is None:
            raise RuntimeError("CalibrationConfig.calibration_recording_directory not set")
        recording_dir = Path(self.calibration_recording_directory).expanduser()
        return RecordingInfo(
            recording_directory=str(recording_dir.parent),
            recording_name=recording_dir.stem,
            mic_device_index=-1,
        )

    @classmethod
    def create_test_data_request(cls) -> "CalibrateRecordingRequest":
        config = PosthocCalibrationPipelineConfig()

        config.charuco_board.squares_x = 7
        config.charuco_board.squares_y = 5
        config.charuco_board.square_length_mm = 54
        return cls(calibration_config=config,
                   calibration_recording_directory=FREEMOCAP_TEST_DATA_PATH)


class StopCalibrationRecordingRequest(BaseModel):
    calibration_config: PosthocCalibrationPipelineConfig = Field(alias="calibrationTaskConfig")


class StartCalibrationRecordingResponse(BaseModel):
    success: bool
    message: str | None = None


class CalibrateRecordingResponse(BaseModel):
    success: bool
    message: str | None = None
    results: dict | None = None


# ==================== Endpoints ====================


@calibration_router.post("/recording/start")
async def start_calibration_recording(
        request: CalibrateRecordingRequest,
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
        logger.exception(f"Error stopping calibration recording: {e}")
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
        logger.info(f"Calibrating recording at: {recording_info.full_recording_path} with calibration config:\n {request.calibration_config.model_dump_json(indent=2)}")
        return CalibrateRecordingResponse(
            success=True,
            message="Calibration pipeline launched",
            results={},
        )
    except Exception as e:
        logger.exception(f"Error calibrating recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))
