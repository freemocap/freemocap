import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from src.config.home_dir import create_session_id, get_session_folder_path

logger = logging.getLogger(__name__)

session_router = APIRouter()


class SessionCreateModel(BaseModel):
    user_session_tag_str: Optional[str]


class SessionResponse(BaseModel):
    session_id: str
    session_path: str


@session_router.post("/session/create")
async def create_session(session_create_model: SessionCreateModel):
    session_id = create_session_id(session_create_model.user_session_tag_str)
    session_path = Path(get_session_folder_path(session_id))
    logger.info(f'Creating session folder at: {str(session_path)}')
    session_path.mkdir(parents=True, exist_ok=True)
    return SessionResponse(session_id=session_id,
                           session_path=str(session_path))


@session_router.post("session/calibrate")
async def calibrate_session():
    """launch camera calibration (or load previous calibration)"""
    pass
