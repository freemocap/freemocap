import time
from pathlib import Path

from pydantic import BaseModel


class CreateWriterOptions(BaseModel):
    writer_dir: Path


def get_canonical_time_str():
    return time.strftime("%m_%d_%Y_%H%M%S")


def get_base_options():
    return CreateWriterOptions(
        writer_dir=Path().joinpath(
            "raw_frame_capture", f"{get_canonical_time_str()}.mp4"
        )
    )
