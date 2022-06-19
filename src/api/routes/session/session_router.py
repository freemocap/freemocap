import logging
from pathlib import Path
from typing import Optional, Union

from fastapi import APIRouter
from pydantic import BaseModel

from src.config.home_dir import create_session_id, get_session_folder_path
from src.pipelines.calibration_pipeline.calibration_pipeline_orchestrator import CalibrationPipelineOrchestrator
from src.pipelines.session_pipeline.session_pipeline_orchestrator import SessionPipelineOrchestrator

logger = logging.getLogger(__name__)

session_router = APIRouter()


class SessionCreateModel(BaseModel):
    user_session_tag_str: Optional[str]


class SessionResponse(BaseModel):
    session_id: str
    session_path: str


class SessionCalibrateModel(BaseModel):
    """
    session_id: str, ID for the session we're calibrating
    charuco_square_size:Union[int, float], the size of one of the black squares on the charuco board (preferably) in milimeters
    """
    session_id: str = None
    charuco_square_size: Union[int, float] = 39


class SessionRecordModel(BaseModel):
    """
    """
    session_id: str = None




@session_router.post("/session/create")
async def create_session(session_create_model: SessionCreateModel):
    session_id = create_session_id(session_create_model.user_session_tag_str)
    session_path = Path(get_session_folder_path(session_id))
    logger.info(f'Creating session folder at: {str(session_path)}')
    session_path.mkdir(parents=True, exist_ok=True)
    return SessionResponse(session_id=session_id,
                           session_path=str(session_path))


@session_router.post("/session/calibrate")
async def calibrate_session(session_calibrate_model: SessionCalibrateModel = SessionCalibrateModel()):
    """calibate capture volume - record synchronized videos (from all available camras wtih default parameters for now) and process with Anipose to produce a camera calibration (saved as a `.toml` file in the session folder"""

    calibration_orchestrator = CalibrationPipelineOrchestrator(session_calibrate_model.session_id)
    calibration_orchestrator.record_videos(show_visualizer_gui=False,
                                           save_video_in_frame_loop=False,
                                           show_camera_views_in_windows=True,
                                           )
    calibration_orchestrator.run_anipose_camera_calibration(charuco_square_size=session_calibrate_model.charuco_square_size)

@session_router.post("/session/record")
async def record_session(session_record_model: SessionRecordModel = SessionRecordModel()):
    this_session_orchestrator = SessionPipelineOrchestrator(session_id=session_record_model.session_id)
    this_session_orchestrator.record_new_session()



if __name__ == "__main__":
    pass