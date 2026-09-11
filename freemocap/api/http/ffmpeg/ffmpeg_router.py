import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from freemocap.core.ffmpeg.check_ffmpeg import check_ffmpeg_available

logger = logging.getLogger(__name__)

ffmpeg_router = APIRouter(prefix="/ffmpeg", tags=["Ffmpeg"])


class DetectFfmpegResponse(BaseModel):
    found: bool
    ffmpeg_path: str | None = None
    ffprobe_path: str | None = None
    message: str | None = None


@ffmpeg_router.get("/detect")
def detect_ffmpeg() -> DetectFfmpegResponse:
    """Check whether ffmpeg/ffprobe are installed and on PATH (required for video synchronization)."""
    try:
        availability = check_ffmpeg_available()
        return DetectFfmpegResponse(
            found=availability.found,
            ffmpeg_path=availability.ffmpeg_path,
            ffprobe_path=availability.ffprobe_path,
            message=availability.message,
        )
    except Exception as e:
        logger.exception(f"Error detecting ffmpeg: {e}")
        raise HTTPException(status_code=500, detail=str(e))
