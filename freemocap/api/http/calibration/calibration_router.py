import json
import logging
from copy import deepcopy
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from skellycam.core.recorders.videos.parse_video_filename import VIDEO_EXTENSIONS
from skellycam.core.recorders.videos.recording_info import RecordingInfo

from freemocap.app.freemocap_application import get_freemocap_app
from freemocap.core.tasks.calibration.calibration_task_config import PosthocCalibrationPipelineConfig
from freemocap.pubsub.pubsub_topics import (
    CalibrationRecordingStateMessage,
    CalibrationRecordingStateTopic,
)
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
    pipeline_id: str | None = None


# ==================== Helpers ====================


def _reject_if_recording_directory_not_empty(recording_info: RecordingInfo) -> None:
    """Refuse to start a NEW calibration recording into a directory that already holds videos.

    Starting a recording in a populated `synchronized_videos/` would mix videos from
    different capture sessions (different camera sets / frame counts), which silently breaks
    the posthoc calibration pipeline. Under normal operation the frontend mints a fresh
    timestamped directory, so this only fires on a regression or a misbehaving client.

    Builds the path manually rather than via `RecordingInfo.videos_folder` /
    `full_recording_path`, because those properties `mkdir(...)` as a side effect and a
    refusal must not create empty directories.
    """
    videos_dir = (
        Path(recording_info.recording_directory).expanduser()
        / recording_info.recording_name
        / "synchronized_videos"
    )
    if not videos_dir.is_dir():
        return
    existing_videos = sorted(
        p for p in videos_dir.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
    )
    if existing_videos:
        file_list = ", ".join(p.name for p in existing_videos)
        raise HTTPException(
            status_code=409,
            detail=(
                f"Refusing to start a calibration recording in '{videos_dir.parent}': its "
                f"synchronized_videos/ already contains {len(existing_videos)} video file(s) "
                f"({file_list}). Starting a new recording here would mix videos from different "
                f"sessions. Use a fresh recording directory."
            ),
        )


# ==================== Endpoints ====================


@calibration_router.post("/recording/start")
async def start_calibration_recording(
        request: CalibrateRecordingRequest,
) -> StartCalibrationRecordingResponse:
    """Start calibration recording with given config."""
    try:
        recording_info = request.to_recording_info()
        _reject_if_recording_directory_not_empty(recording_info)
        await get_freemocap_app().start_recording_all(recording_info=recording_info)
        logger.info(f"Starting calibration recording: {recording_info}")

        # Notify realtime pipelines that a calibration recording has started
        # so the CharucoRecorderNode can begin buffering observations.
        app = get_freemocap_app()
        for pipeline in app.realtime_pipeline_manager.pipelines.values():
            if pipeline.alive:
                pipeline.pubsub.publish(
                    CalibrationRecordingStateTopic,
                    CalibrationRecordingStateMessage(
                        recording_info=recording_info,
                        is_active=True,
                    ),
                )
                logger.debug(
                    f"Published CalibrationRecordingState(is_active=True) "
                    f"to pipeline [{pipeline.id}]"
                )
                # Pause skeleton inference so the realtime pipeline keeps up and
                # caches as many Charuco observations as possible. Best-effort —
                # a failure here must NOT abort the calibration recording, since
                # posthoc calibration re-detects any frame the cache lacks.
                try:
                    pipeline.enter_calibration_charuco_only_mode()
                except Exception:
                    logger.exception(
                        f"Failed to enter Charuco-only mode for pipeline "
                        f"[{pipeline.id}] — continuing with skeleton inference on"
                    )

        return StartCalibrationRecordingResponse(success=True, message="Recording started")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error starting calibration recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@calibration_router.post("/recording/stop")
async def stop_calibration_recording(
        request: StopCalibrationRecordingRequest,
) -> dict:
    """Stop current calibration recording and launch posthoc calibration pipeline."""
    app = get_freemocap_app()
    try:
        recording_info = await app.stop_recording_all()
        if recording_info is None:
            logger.warning("No active recording to stop")
            return {"success": True}

        # Notify realtime pipelines that calibration recording has stopped
        # so the CharucoRecorderNode flushes its buffer to the cache file.
        for pipeline in app.realtime_pipeline_manager.pipelines.values():
            if pipeline.alive:
                pipeline.pubsub.publish(
                    CalibrationRecordingStateTopic,
                    CalibrationRecordingStateMessage(
                        recording_info=recording_info,
                        is_active=False,
                    ),
                )
                logger.debug(
                    f"Published CalibrationRecordingState(is_active=False) "
                    f"to pipeline [{pipeline.id}]"
                )
                # Restore skeleton inference paused at recording start.
                try:
                    pipeline.exit_calibration_charuco_only_mode()
                except Exception:
                    logger.exception(
                        f"Failed to restore skeleton inference for pipeline "
                        f"[{pipeline.id}]"
                    )

        logger.info(f"Recording stopped - saved to: {recording_info.full_recording_path}")
        pipeline = await app.create_posthoc_calibration_pipeline(
            recording_info=recording_info,
            calibration_config=request.calibration_config,
        )
        logger.info("Calibration recording stopped, posthoc calibration pipeline launched")
        return {
            "success": True,
            "pipeline_id": pipeline.id,
            "recording_name": recording_info.recording_name,
            "recording_path": str(recording_info.full_recording_path),
        }
    except Exception as e:
        logger.exception(f"Error stopping calibration recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@calibration_router.post("/recording/calibrate")
async def calibrate_recording(request: CalibrateRecordingRequest) -> CalibrateRecordingResponse:
    """Process and calibrate a previously recorded session."""
    app = get_freemocap_app()
    try:

        recording_info = request.to_recording_info()
        pipeline = await app.create_posthoc_calibration_pipeline(
            recording_info=recording_info,
            calibration_config=request.calibration_config,
        )
        logger.info(f"Calibrating recording at: {recording_info.full_recording_path} with calibration config:\n {request.calibration_config.model_dump_json(indent=2)}")
        return CalibrateRecordingResponse(
            success=True,
            message="Calibration pipeline launched",
            results={},
            pipeline_id=pipeline.id,
        )
    except Exception as e:
        logger.exception(f"Error calibrating recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))
