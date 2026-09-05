"""Adapt shared skeleton reconstruction results to recording channels and fits."""

from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np
from pydantic import model_validator

from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
from freemocap.core.reconstruction.recording_reconstruction import (
    ModelRecordingReconstruction,
)
from freemocap.core.recording.channel_series import ChannelSeries
from freemocap.core.recording.recording_metadata import (
    Channel,
    Descriptor,
    Source,
    SourceKind,
)
from freemocap.core.recording.recording_scale_fit import RecordingScaleFit
from freemocap.core.recording.sample_conventions import SampleComponent, SampleUnit
from freemocap.core.recording.spatial_point_series import SpatialReference
from freemocap.core.skeletons.tracked_skeleton_bundle import TrackedSkeletonBundle
from freemocap.core.types.channel_kind import ChannelKind


class ReconstructionSourceDefinition(Descriptor):
    model_id: str
    tracker: str
    scale_reference_name: str
    landmark_names: tuple[str, ...]
    segment_origins: dict[str, str]
    segment_parents: dict[str, str | None]

    @model_validator(mode="after")
    def validate_layout(self) -> "ReconstructionSourceDefinition":
        if not self.model_id or not self.tracker or not self.scale_reference_name:
            raise ValueError(
                "Reconstruction source identity and scale reference are required"
            )
        if set(self.segment_parents) != set(self.segment_origins):
            raise ValueError("Segment parents and origins must cover the same segments")
        if not set(self.segment_origins.values()).issubset(self.landmark_names):
            raise ValueError("Segment origins must reference declared landmarks")
        if any(
            parent is not None and parent not in self.segment_origins
            for parent in self.segment_parents.values()
        ):
            raise ValueError("Segment parent must reference a declared segment")
        return self

    @classmethod
    def from_bundle(
        cls, bundle: TrackedSkeletonBundle
    ) -> "ReconstructionSourceDefinition":
        return cls(
            model_id=bundle.model_id,
            tracker=bundle.detector_type,
            scale_reference_name=bundle.scale_reference_name,
            landmark_names=tuple(bundle.skeleton.landmarks),
            segment_origins={
                name: segment.frame_definition.origin_point_name
                for name, segment in bundle.skeleton.segments.items()
            },
            segment_parents=dict(bundle.rest_pose.parents),
        )

    def to_source(self) -> Source:
        return Source(kind=SourceKind.INSTANCE, definition=self.model_dump(mode="json"))


@dataclass(frozen=True, slots=True)
class ReconstructionRecording:
    sensor_group: str
    reference: SpatialReference
    definition: ReconstructionSourceDefinition
    result: ModelRecordingReconstruction

    def __post_init__(self) -> None:
        if not self.result.frames:
            raise ValueError("Reconstruction recording requires frames")
        if self.result.scale_fit is not None and set(
            self.result.scale_fit.segment_scales
        ) != set(self.definition.segment_origins):
            raise ValueError("Recording fit must cover the declared segments")
        for frame in self.result.frames:
            if frame is None:
                continue
            if frame.model_id != self.definition.model_id:
                raise ValueError("Reconstruction frame belongs to another model")
            if set(frame.landmarks) - set(self.definition.landmark_names):
                raise ValueError("Reconstruction contains undeclared landmarks")
            if (
                set(frame.segment_rotations_world) | set(frame.segment_rotations_local)
            ) - set(self.definition.segment_origins):
                raise ValueError("Reconstruction contains undeclared segments")

    def to_scale_fit(self) -> RecordingScaleFit:
        return RecordingScaleFit(
            sensor_group=self.sensor_group,
            source=self.definition.model_id,
            reference_frame=self.reference.name,
            units=self.reference.units,
            fit=self.result.scale_fit,
        )

    def channels(self) -> Iterator[Channel]:
        """Declare channel layouts without allocating recording-sized arrays."""
        for kind, names, components in (
            (
                ChannelKind.LANDMARKS_3D,
                self.definition.landmark_names,
                (SampleComponent.X, SampleComponent.Y, SampleComponent.Z),
            ),
            (
                ChannelKind.SEGMENT_ORIGINS,
                tuple(self.definition.segment_origins),
                (SampleComponent.X, SampleComponent.Y, SampleComponent.Z),
            ),
            (
                ChannelKind.ROTATIONS_WORLD,
                tuple(self.definition.segment_origins),
                (
                    SampleComponent.W,
                    SampleComponent.X,
                    SampleComponent.Y,
                    SampleComponent.Z,
                ),
            ),
        ):
            yield Channel(
                sensor_group=self.sensor_group,
                source=self.definition.model_id,
                reference_frame=self.reference.name,
                kind=kind,
                names=names,
                components={
                    component: SampleUnit.DIMENSIONLESS
                    if kind == ChannelKind.ROTATIONS_WORLD
                    else self.reference.units
                    for component in components
                },
                stage=ProcessingStage.RECONSTRUCTION,
            )

    def series(self) -> Iterator[ChannelSeries]:
        """World landmarks and orientations retain float64 precision and missing frames."""
        for channel in self.channels():
            values = np.full(
                (len(self.result.frames), len(channel.names), len(channel.components)),
                np.nan,
                dtype=np.float64,
            )
            for index, frame in enumerate(self.result.frames):
                if frame is None:
                    continue
                positions = (
                    frame.segment_rotations_world
                    if channel.kind == ChannelKind.ROTATIONS_WORLD
                    else frame.landmarks
                )
                for point, name in enumerate(channel.names):
                    key = (
                        self.definition.segment_origins[name]
                        if channel.kind == ChannelKind.SEGMENT_ORIGINS
                        else name
                    )
                    if key in positions:
                        if positions[key].shape != (len(channel.components),):
                            raise ValueError(
                                "Reconstruction value has the wrong component shape"
                            )
                        values[index, point] = positions[key]
            yield ChannelSeries(channel=channel, values=values)
