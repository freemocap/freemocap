"""General recording resource response models, independent of playback state."""
from typing import Optional
from pydantic import BaseModel
from freemocap.system.recording_status.recording_status import RecordingStatus
from freemocap.system.recording_structure.recording_structure import RecordingLayoutValidation

class VideoInfo(BaseModel):
    video_id: str
    filename: str
    size_bytes: int
    stream_url: str


class VideoSourceInfo(BaseModel):
    available: bool
    valid: bool
    video_count: int
    videos: list[VideoInfo] = []


class VideoSourcesResponse(BaseModel):
    preferred_source: str
    sources: dict[str, VideoSourceInfo]


class RecordingStatusSummary(BaseModel):
    blender_export_ready: bool = False
    has_blend_file: bool = False
    has_annotated_videos: bool = False
    has_calibration_toml: bool = False
    stages_complete: int = 0
    stages_total: int = 0


class RecordingListEntry(BaseModel):
    name: str
    path: str
    video_count: int
    total_size_bytes: int = 0
    created_timestamp: Optional[str] = None
    total_frames: Optional[int] = None
    duration_seconds: Optional[float] = None
    fps: Optional[float] = None
    status_summary: RecordingStatusSummary = RecordingStatusSummary()
    status: Optional[RecordingStatus] = None
    layout_validation: Optional[RecordingLayoutValidation] = None
