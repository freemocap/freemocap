"""Typed construction inputs and descriptor factories for observation recordings."""

from freemocap.core.types.channel_kind import ChannelKind
from freemocap.core.recording.resolved_camera_geometry import ResolvedCameraGeometry
from freemocap.core.recording.spatial_point_series import SpatialPointSeries
from freemocap.core.recording.reconstruction_recording import ReconstructionRecording
from freemocap.core.recording.recorded_model import RecordedModel
from dataclasses import dataclass
from freemocap.core.recording.sample_conventions import (
    SampleComponent,
    SampleUnit,
    TimingSampleName,
)

from pydantic import JsonValue
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.timestamps.recording_timing_reader import TimingMethod
from skellytracker.core.data_primitives.observation import Observation

from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata
from freemocap.core.recording.recording_metadata import (
    Channel,
    Descriptor,
    Source,
    SourceKind,
)


class TrackerRecordingDefinition(Descriptor):
    name: str
    point_names: tuple[str, ...]
    configuration: dict[str, JsonValue]

    def to_source(self) -> Source:
        return Source(kind=SourceKind.TRACKER, definition=self.configuration)


@dataclass(frozen=True, slots=True)
class ObservationGroup:
    name: str
    frames: list[dict[str, Observation]]
    videos: dict[str, VideoMetadata]

    def __post_init__(self) -> None:
        if not self.frames or not self.videos:
            raise ValueError("Observation ingestion requires frames and cameras")
        if any(set(frame) != set(self.videos) for frame in self.frames):
            raise ValueError("Observation camera set does not match video metadata")

    @property
    def frame_numbers(self) -> tuple[int, ...]:
        camera = next(iter(self.videos))
        return tuple(frame[camera].frame_number for frame in self.frames)


@dataclass(frozen=True, slots=True)
class ObservationRecordingRequest:
    models: tuple[RecordedModel, ...]
    reconstructions: tuple[ReconstructionRecording, ...]
    recording: RecordingInfo
    group: ObservationGroup
    tracker: TrackerRecordingDefinition
    spatial_series: tuple[SpatialPointSeries, ...]
    camera_geometry: tuple[ResolvedCameraGeometry, ...]

    def __post_init__(self) -> None:
        if len({model.model_id for model in self.models}) != len(self.models):
            raise ValueError("Recorded models must be unique")
        model_ids = [item.definition.model_id for item in self.reconstructions]
        if len(set(model_ids)) != len(model_ids):
            raise ValueError("Reconstruction sources must be unique")
        for item in self.reconstructions:
            if item.sensor_group != self.group.name or len(item.result.frames) != len(
                self.group.frames
            ):
                raise ValueError(
                    "Reconstruction must cover the observation group frame grid"
                )
        for series in self.spatial_series:
            if (
                series.definition.sensor_group != self.group.name
                or series.definition.source != self.tracker.name
            ):
                raise ValueError(
                    "Spatial points must belong to the recording group and tracker"
                )
            if series.values.shape[0] != len(self.group.frames):
                raise ValueError("Spatial points must cover the observation frame grid")


class ImageReference(Descriptor):
    camera_id: str
    width: int
    height: int

    @property
    def name(self) -> str:
        return f"camera:{self.camera_id}:image"


class CameraRecordingDefinition(Descriptor):
    camera_id: str
    timing_method: TimingMethod
    nominal_fps: float
    inferred_offset_s: float

    @property
    def source_name(self) -> str:
        return f"camera:{self.camera_id}"

    def to_source(self) -> Source:
        return Source(kind=SourceKind.CAMERA, definition=self.model_dump(mode="json"))


class GroupTimingDefinition(Descriptor):
    method: TimingMethod

    def to_source(self) -> Source:
        return Source(kind=SourceKind.TIMING, definition=self.model_dump(mode="json"))


@dataclass(frozen=True, slots=True)
class CameraObservationChannels:
    overlay: Channel
    capture: Channel

    @classmethod
    def create(
        cls, *, request: ObservationRecordingRequest, image: ImageReference
    ) -> "CameraObservationChannels":
        return cls(
            overlay=Channel(
                sensor_group=request.group.name,
                source=request.tracker.name,
                reference_frame=image.name,
                kind=ChannelKind.OVERLAY_2D,
                names=request.tracker.point_names,
                components={
                    SampleComponent.X: SampleUnit.PIXELS,
                    SampleComponent.Y: SampleUnit.PIXELS,
                    SampleComponent.VISIBILITY: SampleUnit.DIMENSIONLESS,
                },
                stage=ProcessingStage.OBSERVATIONS,
            ),
            capture=create_timing_channel(
                group=request.group.name,
                source=f"camera:{image.camera_id}",
                name=TimingSampleName.CAPTURE,
            ),
        )


def create_timing_channel(
    *, group: str, source: str, name: TimingSampleName
) -> Channel:
    return Channel(
        sensor_group=group,
        source=source,
        reference_frame=None,
        kind=ChannelKind.TIMESTAMPS,
        names=(name,),
        components={SampleComponent.TIMESTAMP: SampleUnit.SECONDS},
        stage=ProcessingStage.TIMING,
    )
