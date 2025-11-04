import logging
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import BaseModel, Field
from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera_group.camera_group import CameraConfigs
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraGroupIdString, CameraIdString

from freemocap.core.pipeline.pipeline_configs import PipelineConfig
from freemocap.app.freemocap_application import get_freemocap_app
from freemocap.system.default_paths import default_recording_name, get_default_recording_folder_path

from skellytracker.trackers.charuco_tracker.charuco_detector import CharucoDetectorConfig
logger = logging.getLogger(__name__)

calibration_router = APIRouter(prefix=f"/calibration",
                            tags=["Calibration"], )

class CharucoBoardDefinitionUpdateRequest(BaseModel):
    squares_x: int = Field(default=3, description="Number of squares along the X axis")
    squares_y: int = Field(default=5, description="Number of squares along the Y axis")
    square_length_mm: float = Field(default=54.0, description="Length of a square side in millimeters")




@calibration_router.get("/realtime/tracker/start",
                      summary="Start realtime calibration tracker"
                      )
def start_realtime_calibration_tracker(request: Request) -> bool:
    app = get_freemocap_app()
    try:
        app.pipeline_manager.start_realtime_calibration_tracking()
        return True
    except Exception as e:
        logger.error(f"Error starting realtime calibration tracker: {e}")
        raise HTTPException(status_code=500, detail=str(e))