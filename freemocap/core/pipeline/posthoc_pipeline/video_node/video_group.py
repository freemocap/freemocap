from pathlib import Path

from pydantic import BaseModel, ConfigDict, model_validator

from freemocap.core.pipeline.posthoc_pipeline.video_node.video_helper import VideoHelper
from freemocap.core.types.type_overloads import VideoIdString


class VideoGroup(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True,
        extra="forbid",
        frozen=True
    )
    videos: dict[VideoIdString,VideoHelper]

    @property
    def video_ids(self) -> list[VideoIdString]:
        return list(self.videos.keys())

    @property
    def video_metadata_by_id(self) -> dict[VideoIdString, object]:
        return {video_id: video.metadata for video_id, video in self.videos.items()}

    @model_validator(mode="after")
    def validate_videos(self):
        if len(self.videos) == 0:
            raise ValueError("VideoGroup must contain at least one video.")
        if len(set(video.metadata.frame_count for video in self.videos.values())) != 1:
            raise ValueError("All videos in VideoGroup must have the same frame count.")
        return self


    @classmethod
    def from_video_paths(cls, video_paths: list[VideoIdString], close_videos:bool=True) -> "VideoGroup":

        return cls(
            videos={video_path: VideoHelper.from_video_path(Path(video_path)) for video_path in video_paths}
        )

    @classmethod
    def from_video_folder_path(cls, video_folder_path: Path) -> "VideoGroup":
        video_paths = sorted([str(p) for p in video_folder_path.iterdir() if p.suffix.lower() in {'.mp4', '.avi', '.mov', '.mkv'}])
        return cls.from_video_paths(video_paths)


    @classmethod
    def from_recording_path(cls, recording_path: str, video_subfolder_name:str='synchronized_videos') -> "VideoGroup":
        return cls.from_video_folder_path(Path(recording_path) / video_subfolder_name)


    def close(self):
        for video in self.videos.values():
            video.close()