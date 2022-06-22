import logging
from pathlib import Path
from typing import Optional, Union

from fastapi import APIRouter
from pydantic import BaseModel

from jon_scratch.pupil_calibration_pipeline.qt_gl_laser_skeleton_visualizer import QtGlLaserSkeletonVisualizer
from src.config.home_dir import create_session_id, get_session_folder_path, get_most_recent_session_id
from src.pipelines.calibration_pipeline.calibration_pipeline_orchestrator import CalibrationPipelineOrchestrator
from src.pipelines.session_pipeline.session_pipeline_orchestrator import SessionPipelineOrchestrator, \
    load_mediapipe3d_skeleton_data, load_mediapipe2d_data

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


class SessionIdModel(BaseModel):
    """
    """
    session_id: str = None


@session_router.post("/session/create")
async def create_session(session_create_model: SessionCreateModel = SessionCreateModel()) -> SessionResponse:
    session_id = create_session_id()
    create_session_folder(session_id)
    session_id_model = SessionIdModel(session_id=session_id)

    return SessionResponse(session_id=session_id,
                           session_path=get_session_folder_path(session_id))


@session_router.post("/session/calibrate")
def calibrate_session(session_calibrate_model: SessionCalibrateModel = SessionCalibrateModel()):
    """calibate capture volume - record synchronized videos (from all available camras wtih default parameters for now) and process with Anipose to produce a camera calibration (saved as a `.toml` file in the session folder"""

    if session_calibrate_model.session_id is None or session_id_model.session_id == "string":
        this_session_id = get_most_recent_session_id()
    else:
        this_session_id = session_calibrate_model.session_id

    calibration_orchestrator = CalibrationPipelineOrchestrator(this_session_id)
    calibration_orchestrator.record_videos(show_visualizer_gui=False,
                                           save_video_in_frame_loop=False,
                                           show_camera_views_in_windows=True,
                                           )
    calibration_orchestrator.run_anipose_camera_calibration(
        charuco_square_size=session_calibrate_model.charuco_square_size)


@session_router.post("/session/record")
def record_session(session_id_model: SessionIdModel = SessionIdModel()):
    this_session_orchestrator = SessionPipelineOrchestrator(session_id=session_id_model.session_id)
    this_session_orchestrator.record_new_session()


@session_router.post("/session/mediapipe_track_skeletons_offline")
def mediapipe_track_2D_skeletons_offline(session_id_model: SessionIdModel = SessionIdModel()):
    if session_id_model.session_id is None or session_id_model.session_id == "string":
        this_session_id = get_most_recent_session_id()
        logger.info(f"loading most recent session:{this_session_id}")
    else:
        this_session_id = session_id_model.session_id

    logger.info(f"tracking 2D mediapipe skeletons in videos from session: {this_session_id}")
    this_session_orchestrator = SessionPipelineOrchestrator(session_id=this_session_id)
    this_session_orchestrator.mediapipe_track_skeletons_offline()


@session_router.post("/session/reconstruct_mediapipe3d_offline")
def mediapipe_reconstruct_3D_skeletons_offline(session_id_model: SessionIdModel = None):
    if session_id_model is None or session_id_model.session_id == "string":
        session_id = get_most_recent_session_id()
    else:
        session_id = session_id_model.session_id


    this_session_orchestrator = SessionPipelineOrchestrator(session_id=session_id)
    this_session_orchestrator.anipose_camera_calibration_object = CalibrationPipelineOrchestrator().load_calibration_from_session_id(session_id)
    this_session_orchestrator.mediapipe2d_numCams_numFrames_numTrackedPoints_XY = load_mediapipe2d_data(session_id)
    this_session_orchestrator.reconstruct3d_from_2d_data_offline()


@session_router.post("/session/visualize_offline")
def visualize_session_offline(session_id_model: SessionIdModel = None):
    if session_id_model is None or session_id_model.session_id == "string":
        session_id = get_most_recent_session_id()
    else:
        session_id = session_id_model.session_id

    mediapipe3d_data_payload = load_mediapipe3d_skeleton_data(session_id)

    mediapipe3d_skeleton_nFrames_nTrajectories_xyz = mediapipe3d_data_payload.data3d_numFrames_numTrackedPoints_XYZ
    mediapipe3d_skeleton_nFrames_nTrajectories_reprojectionError = mediapipe3d_data_payload.data3d_numFrames_numTrackedPoint_reprojectionError

    qt_gl_laser_skeleton = QtGlLaserSkeletonVisualizer(
        mediapipe_skel_fr_mar_xyz=mediapipe3d_skeleton_nFrames_nTrajectories_xyz)
    qt_gl_laser_skeleton.start_animation()


if __name__ == "__main__":

    #create_session
    session_id = create_session_id('session_router_as_main')
    session_id_model = SessionIdModel(session_id=session_id)

    # # #calibrate_session
    # session_calibrate_model = SessionCalibrateModel(session_id=session_id,
    #                                                 charuco_square_size=39)
    # calibrate_session(session_calibrate_model)

    #record new session
    record_session(session_id_model)

    # #process_
    # mediapipe_track_2D_skeletons_offline(session_id_model)
    #
    mediapipe_reconstruct_3D_skeletons_offline(session_id_model)
    #
    # #visualize with PyQt/OpenGL
    # visualize_session_offline(session_id_model)
