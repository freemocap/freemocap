"""Typed construction inputs and descriptor factories for observation recordings."""

import hashlib
from collections.abc import Iterable

from freemocap.core.types.channel_kind import ChannelKind
from freemocap.core.reconstruction.posthoc_filtering import PosthocFilterReport
from freemocap.core.tasks.calibration.shared.camera_model import CameraModel
from freemocap.core.recording.sample_encoding.spatial_points import SpatialPointSeries
from freemocap.core.recording.sample_encoding.reconstruction_samples import ReconstructionRecording
from freemocap.core.recording.data_descriptors.recording_model import RecordedModel
from dataclasses import dataclass
from freemocap.core.tasks.triangulation.helpers.reprojection_diagnostics import NamedReprojectionDiagnostics
from freemocap.core.recording.data_descriptors.sample_conventions import (
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
from freemocap.core.recording.data_descriptors.recording_descriptor import (
    Channel,
    Descriptor,
    Source,
    SourceKind,
)


def camera_group_name(camera_ids: Iterable[str]) -> str:
    """The sampling grid these cameras share, as `camera_group:{digest}`.

    A sensor group names a clock, not a pipeline, so it is derived from the camera set
    rather than from what the run was for. The digest is over the SORTED ids, so every
    recording from the same rig lands in the same group and runs stay comparable;
    swapping a camera is a different rig and correctly gets a different group.
    """
    ids = sorted(camera_ids)
    if not ids:
        raise ValueError("A camera group needs at least one camera")
    digest = hashlib.sha256("|".join(ids).encode("utf-8")).hexdigest()[:6]
    return f"camera_group:{digest}"


class TrackerRecordingDefinition(Descriptor):
    """The keypoint model that measured the points, e.g. `keypoint_model:rtmw-x-l_256x192`.

    `name` is the recording's source identity, so it names the MODEL rather than the
    pipeline that ran it — the exact weights are what a reader needs to reproduce the
    numbers. The full configuration rides in the Source definition blob.
    """

    name: str
    point_names: tuple[str, ...]
    configuration: dict[str, JsonValue]

    def to_source(self) -> Source:
        return Source(kind=SourceKind.TRACKER, definition=self.configuration)


class DetectorRecordingDefinition(Descriptor):
    """The object detector that produced the bounding boxes, e.g. `object_detector:yolox-m`.

    Separate from the keypoint model because they ARE separate models: the boxes come
    from YOLOX and the keypoints from RTMPose, and a reader comparing a box against the
    points measured inside it needs to know which produced which.

    A tracker with no object detector has no such source, and therefore records no boxes
    — which is the right answer, because `DetectionStage` synthesizes a full-image box in
    that case and a box covering the whole frame says nothing about where the subject is.
    """

    name: str
    box_names: tuple[str, ...]
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
    reprojection: NamedReprojectionDiagnostics | None
    filtering: PosthocFilterReport | None
    models: tuple[RecordedModel, ...]
    reconstructions: tuple[ReconstructionRecording, ...]
    recording: RecordingInfo
    group: ObservationGroup
    tracker: TrackerRecordingDefinition
    spatial_series: tuple[SpatialPointSeries, ...]
    camera_geometry: tuple[CameraModel, ...]
    # Absent when the tracker runs no object detector (MediaPipe), in which case no
    # BOXES_2D channel is declared and no boxes are recorded.
    detector: DetectorRecordingDefinition | None = None

    def __post_init__(self) -> None:
        if self.reprojection is not None:
            if self.reprojection.source_ids != tuple(self.group.videos):
                raise ValueError("Diagnostic sources must match recording camera order")
            if self.reprojection.values.errors.shape != (
                len(self.group.videos), len(self.group.frames), len(self.reprojection.point_names)
            ):
                raise ValueError("Diagnostics must cover the recording camera/frame/point grid")
        if self.camera_geometry and len(self.camera_geometry) != len(self.group.videos):
            raise ValueError("Published geometry must cover every source in video order")
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
    calibration_camera_id: str | None
    width: int
    height: int

    @property
    def name(self) -> str:
        return f"camera:{self.camera_id}:image"


class CameraRecordingDefinition(Descriptor):
    camera_id: str
    video_filename: str
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
    # None when the tracker runs no object detector: there is no detector to attribute
    # the boxes to, and the box DetectionStage would synthesize covers the whole image.
    boxes: Channel | None = None

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
            boxes=Channel(
                sensor_group=request.group.name,
                source=request.detector.name,
                reference_frame=image.name,
                kind=ChannelKind.BOXES_2D,
                names=request.detector.box_names,
                components=BOX_COMPONENTS,
                stage=ProcessingStage.OBSERVATIONS,
            ) if request.detector is not None else None,
        )


# One row per detection stage per frame. `detector_ran` is 1.0 when the object detector
# produced this box on this frame and 0.0 when it was carried forward from the tracked
# keypoints — the provenance that makes an over-eager redetect policy legible offline.
BOX_COMPONENTS: dict[str, str] = {
    SampleComponent.X1: SampleUnit.PIXELS,
    SampleComponent.Y1: SampleUnit.PIXELS,
    SampleComponent.X2: SampleUnit.PIXELS,
    SampleComponent.Y2: SampleUnit.PIXELS,
    SampleComponent.CONFIDENCE: SampleUnit.DIMENSIONLESS,
    SampleComponent.DETECTOR_RAN: SampleUnit.DIMENSIONLESS,
}


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
