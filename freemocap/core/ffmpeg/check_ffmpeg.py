import logging
import shutil
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FfmpegAvailability:
    found: bool
    ffmpeg_path: str | None
    ffprobe_path: str | None
    message: str


def check_ffmpeg_available() -> FfmpegAvailability:
    """Check whether `ffmpeg` and `ffprobe` are on the system PATH.

    Video synchronization (skelly_synchronize) shells out to both binaries, so
    a missing install only surfaces as a `FileNotFoundError` once a sync job is
    already running - this lets the UI warn the user up front instead.
    """
    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")

    if ffmpeg_path and ffprobe_path:
        return FfmpegAvailability(
            found=True,
            ffmpeg_path=ffmpeg_path,
            ffprobe_path=ffprobe_path,
            message=f"Found ffmpeg at: {ffmpeg_path}",
        )

    missing = [name for name, path in (("ffmpeg", ffmpeg_path), ("ffprobe", ffprobe_path)) if not path]
    message = f"Could not find {' and '.join(missing)} on your system PATH - install ffmpeg to enable video synchronization"
    logger.warning(message)
    return FfmpegAvailability(
        found=False,
        ffmpeg_path=ffmpeg_path,
        ffprobe_path=ffprobe_path,
        message=message,
    )
