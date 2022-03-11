from pathlib import Path

from pydantic import BaseModel


class SaveOptions(BaseModel):
    writer_dir: Path
    filename: str = "movie.mp4"
    fps: float
    fourcc: str = "MP4V"
    frame_width: int
    frame_height: int

    @property
    def full_path(self):
        return Path().joinpath(self.writer_dir, self.filename)
