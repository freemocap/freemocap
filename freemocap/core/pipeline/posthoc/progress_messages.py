from dataclasses import dataclass

from skellycam.core.types.type_overloads import CameraIdString


@dataclass
class PipelineProgressMessage:
    message_type: str = "posthoc_progress"
    pipeline_id: str = ""
    pipeline_type: str = ""
    phase: str = ""
    progress_fraction: float = 0.0
    detail: str = ""
    recording_name: str = ""
    recording_path: str = ""


@dataclass
class VideoNodeProgressMessage(PipelineProgressMessage):
    camera_id: CameraIdString = ""


@dataclass
class AggregatorNodeProgressMessage(PipelineProgressMessage):
    pass
