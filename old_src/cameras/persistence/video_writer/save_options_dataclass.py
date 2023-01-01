from dataclasses import dataclass
from pathlib import Path


@dataclass
class SaveOptions:
    path_to_save_video: Path
    camera_name: str
    frame_width: int
    frame_height: int
    frames_per_second: float
    fourcc: str = "MP4V"

    def __post_init__(self):
        self.video_filename = self.camera_name + "_synchronized_raw.mp4"
        path_to_save_video = None

    @property
    def full_path(self):
        return Path().joinpath(self.path_to_save_video, self.video_filename)
