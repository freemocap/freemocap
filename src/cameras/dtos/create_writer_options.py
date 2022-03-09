import time
from pathlib import Path

from pydantic import BaseModel


class CreateWriterOptions(BaseModel):
    filename_and_ext: str
    parent_folder: str


def get_canonical_time_str():
    return time.strftime("%Y%m%d_%H%M%S")


def get_base_options():
    return CreateWriterOptions(
        filename_and_ext=f"{get_canonical_time_str()}.avi",
        parent_folder="raw_frame_capture",
    )
