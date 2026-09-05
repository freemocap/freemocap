"""Bind a SkellyForge recording fit to its source and spatial units."""

from pydantic import BaseModel, ConfigDict, model_validator
from skellyforge.core.skeleton.pose.model_scale_fitting import ModelScaleFit

from freemocap.core.recording.sample_conventions import SampleUnit


class RecordingScaleFit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    sensor_group: str
    source: str
    reference_frame: str
    units: SampleUnit
    fit: ModelScaleFit | None

    @model_validator(mode="after")
    def validate_units(self) -> "RecordingScaleFit":
        if self.units not in (SampleUnit.PIXELS, SampleUnit.MILLIMETERS):
            raise ValueError("Recording scale requires spatial units")
        return self
