"""Typed spatial point arrays and their bounded canonical serialization."""

from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from numpy.typing import NDArray
import pyarrow as pa
from pydantic import model_validator

from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
from freemocap.core.recording.channel_series import ChannelSeries, SeriesSampling
from freemocap.core.recording.recording_metadata import Channel, Descriptor
from freemocap.core.recording.sample_conventions import SampleComponent, SampleUnit
from freemocap.core.types.channel_kind import ChannelKind


class SpatialReferenceName(StrEnum):
    CALIBRATED_WORLD = "calibrated_world"
    CAMERA_PLANE = "camera_plane"


class SpatialBasis(StrEnum):
    BLENDER = "blender_x_right_y_forward_z_up"


class SpatialReference(Descriptor):
    name: SpatialReferenceName
    basis: SpatialBasis = SpatialBasis.BLENDER
    units: SampleUnit

    @model_validator(mode="after")
    def validate_units(self) -> "SpatialReference":
        expected = (
            SampleUnit.PIXELS
            if self.name == SpatialReferenceName.CAMERA_PLANE
            else SampleUnit.MILLIMETERS
        )
        if self.units != expected:
            raise ValueError(f"Spatial reference {self.name} requires {expected}")
        return self

    @classmethod
    def for_camera_count(cls, camera_count: int) -> "SpatialReference":
        if camera_count < 1:
            raise ValueError("Spatial output requires at least one camera")
        return cls(
            name=SpatialReferenceName.CAMERA_PLANE
            if camera_count == 1
            else SpatialReferenceName.CALIBRATED_WORLD,
            units=SampleUnit.PIXELS if camera_count == 1 else SampleUnit.MILLIMETERS,
        )


class PointSeriesDefinition(Descriptor):
    sensor_group: str
    source: str
    names: tuple[str, ...]
    reference: SpatialReference

    def to_channel(self) -> Channel:
        return Channel(
            sensor_group=self.sensor_group,
            source=self.source,
            reference_frame=self.reference.name,
            kind=ChannelKind.RAW_KEYPOINTS_3D,
            names=self.names,
            components={
                component: self.reference.units
                for component in (
                    SampleComponent.X,
                    SampleComponent.Y,
                    SampleComponent.Z,
                )
            },
            stage=ProcessingStage.TRIANGULATION,
        )


@dataclass(frozen=True, slots=True)
class SpatialPointSeries:
    definition: PointSeriesDefinition
    values: NDArray[np.float64]

    def __post_init__(self) -> None:
        self.definition.to_channel()
        if self.values.ndim != 3 or self.values.shape[1:] != (
            len(self.definition.names),
            3,
        ):
            raise ValueError("Point series must have shape (frames, named points, 3)")
        if np.isinf(self.values).any():
            raise ValueError("Point series cannot contain infinite coordinates")

    def batches(self, sampling: SeriesSampling) -> Iterator[pa.RecordBatch]:
        yield from ChannelSeries(
            channel=self.definition.to_channel(), values=self.values
        ).batches(sampling)
