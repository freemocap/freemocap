from dataclasses import dataclass
from freemocap_web.core.config import Config
from freemocap_web.folders import Folders, Path


@dataclass
class Project:
    InputVideo: Path
    Folders: Folders
    Config: Config

    @staticmethod
    def from_video(video: str):
        input_video = Path(video)

        folders = Folders.from_video_path(video_path=input_video)

        sync_video_copy = folders.SyncVideos / input_video.name
        sync_video_copy.write_bytes(input_video.read_bytes())

        return Project(
            InputVideo=input_video,
            Folders=folders,
            Config=Config.default())
