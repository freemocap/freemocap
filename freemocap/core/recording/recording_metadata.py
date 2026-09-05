"""The descriptors required to interpret each retained recording result."""

from typing import Literal
from enum import StrEnum
import math

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
from freemocap.core.types.channel_kind import ChannelKind
from freemocap.core.recording.resolved_camera_geometry import ResolvedCameraGeometry
from freemocap.core.recording.recording_scale_fit import RecordingScaleFit
from freemocap.core.recording.recorded_model import RecordedModel


class Descriptor(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SensorGroup(Descriptor):
    clock_description: str = Field(min_length=1)
    sample_count: int = Field(ge=0)


class SourceKind(StrEnum):
    INSTANCE = "instance"
    TRACKER = "tracker"
    CAMERA = "camera"
    TIMING = "timing"


class Source(Descriptor):
    kind: SourceKind
    definition: dict[str, JsonValue]


class Channel(Descriptor):
    sensor_group: str
    source: str
    reference_frame: str | None
    kind: ChannelKind
    names: tuple[str, ...]
    components: dict[str, str]
    stage: ProcessingStage

    @model_validator(mode="after")
    def validate_names(self) -> "Channel":
        if not self.kind or not self.names or not self.components:
            raise ValueError("channel kind, names and components are required")
        if len(set(self.names)) != len(self.names) or any(
            not name for name in self.names
        ):
            raise ValueError("channel names must be unique and nonempty")
        if any(
            not component or not units for component, units in self.components.items()
        ):
            raise ValueError("component names and units must be nonempty")
        if self.kind in ("ROTATIONS_LOCAL", "ROTATIONS_WORLD"):
            if self.components != {"w": "1", "x": "1", "y": "1", "z": "1"}:
                raise ValueError(
                    "Rotation channels require dimensionless wxyz components"
                )
            if self.reference_frame is None:
                raise ValueError("Rotation channels require a reference frame")
        return self


class StageCheckpoint(Descriptor):
    sensor_group: str
    stage: ProcessingStage
    signature: str = Field(min_length=1)


class StaticChannel(Descriptor):
    channel: Channel
    values: dict[str, dict[str, float]]

    @model_validator(mode="after")
    def validate_values(self) -> "StaticChannel":
        if set(self.values) != set(self.channel.names):
            raise ValueError("static channel names do not match its definition")
        for components in self.values.values():
            if set(components) != set(self.channel.components):
                raise ValueError(
                    "static channel components do not match its definition"
                )
            if any(not math.isfinite(value) for value in components.values()):
                raise ValueError("Static measurements must be finite")
        return self


def channel_key(*, channel: Channel) -> tuple[str, str, str | None, str]:
    return channel.sensor_group, channel.source, channel.reference_frame, channel.kind


class RunDescriptor(Descriptor):
    scale_fits: tuple[RecordingScaleFit, ...] = ()
    camera_geometry: dict[str, tuple[ResolvedCameraGeometry, ...]] = Field(
        default_factory=dict
    )
    sensor_groups: dict[str, SensorGroup]
    sources: dict[str, Source]
    reference_frames: dict[str, dict[str, JsonValue]]
    models: dict[str, RecordedModel]
    processing: dict[str, JsonValue]
    channels: tuple[Channel, ...]
    static_channels: tuple[StaticChannel, ...] = ()
    checkpoints: tuple[StageCheckpoint, ...] = ()

    @model_validator(mode="after")
    def validate_references(self) -> "RunDescriptor":
        if any(name != model.model_id for name, model in self.models.items()):
            raise ValueError("Recorded models must be keyed by their model ID")
        fit_keys = [(fit.sensor_group, fit.source) for fit in self.scale_fits]
        if len(set(fit_keys)) != len(fit_keys):
            raise ValueError("Duplicate recording scale fit")
        for fit in self.scale_fits:
            if (
                fit.sensor_group not in self.sensor_groups
                or fit.source not in self.sources
                or fit.reference_frame not in self.reference_frames
            ):
                raise ValueError(
                    "Unknown group/source/reference in recording scale fit"
                )
            if self.reference_frames[fit.reference_frame].get("units") != fit.units:
                raise ValueError(
                    "Recording fit units disagree with its spatial reference"
                )
        if not set(self.camera_geometry).issubset(self.sensor_groups):
            raise ValueError("Unknown camera geometry sensor group")
        for cameras in self.camera_geometry.values():
            if len({camera.camera_id for camera in cameras}) != len(cameras):
                raise ValueError("Duplicate resolved camera geometry")
        keys: set[tuple[str, str, str | None, str]] = set()
        for channel in (
            *self.channels,
            *(static.channel for static in self.static_channels),
        ):
            key = channel_key(channel=channel)
            if channel.kind in (
                ChannelKind.MODEL_SCALE,
                ChannelKind.SEGMENT_SCALES,
                ChannelKind.SEGMENT_LENGTHS,
            ) and any(
                fit.fit is not None
                and fit.source == channel.source
                and fit.sensor_group == channel.sensor_group
                for fit in self.scale_fits
            ):
                raise ValueError(
                    "Fitted measurements must be derived from the stored fit, not duplicated"
                )
            if key in keys:
                raise ValueError(f"Duplicate channel declaration: {key}")
            keys.add(key)
            if (
                channel.sensor_group not in self.sensor_groups
                or channel.source not in self.sources
            ):
                raise ValueError(f"Unknown group/source in channel {key}")
            if (
                channel.reference_frame is not None
                and channel.reference_frame not in self.reference_frames
            ):
                raise ValueError(f"Unknown reference frame in channel {key}")
        checkpoints = [(item.sensor_group, item.stage) for item in self.checkpoints]
        if len(set(checkpoints)) != len(checkpoints):
            raise ValueError("Duplicate stage checkpoint")
        if any(group not in self.sensor_groups for group, _ in checkpoints):
            raise ValueError("Unknown checkpoint sensor group")
        return self


class RecordingMetadata(Descriptor):
    schema_version: Literal[1] = 1
    recording_id: str = Field(min_length=1)
    selected_run_id: int = Field(ge=0)
    recording_info: dict[str, JsonValue] = Field(default_factory=dict)
    runs: dict[int, RunDescriptor]

    @model_validator(mode="after")
    def validate_runs(self) -> "RecordingMetadata":
        if self.selected_run_id not in self.runs or any(
            run_id < 0 for run_id in self.runs
        ):
            raise ValueError("selected_run_id must name a retained nonnegative run")
        return self
