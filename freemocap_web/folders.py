from dataclasses import dataclass
from pathlib import Path


@dataclass
class Folders:
    Root: Path
    SyncVideos: Path
    MediaPipeData: Path
    Annotated: Path
    OutputData: Path

    @staticmethod
    def from_video_path(video_path: Path):
        root = video_path.parent / 'mocap'
        return Folders(
            Root=root,
            SyncVideos=root / 'synchronized_videos',
            OutputData=root / 'output_data',
            MediaPipeData=root / 'output_data' / 'raw_data',
            Annotated=root / 'annotated_videos')

    def __post_init__(self):
        for path in [self.Root, self.SyncVideos, self.OutputData, self.MediaPipeData, self.Annotated]:
            path.mkdir(exist_ok=True)
