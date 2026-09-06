"""Recording-wide fit evidence and the exact numerical inputs it describes."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field
from skellyforge.core.skeleton.pose.model_scale_fitting import ModelScaleFit

from freemocap.core.recording.input_signatures import (
    definition_signature,
    point_array_signature,
)
from freemocap.core.recording.recorded_model import RecordedModel


class RecordingFitInputs(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    algorithm_version: int = Field(ge=1)
    keypoint_names: tuple[str, ...]
    points: str = Field(min_length=64, max_length=64)
    model: str = Field(min_length=64, max_length=64)

    @classmethod
    def from_points(
        cls,
        *,
        names: tuple[str, ...],
        values: NDArray[np.float64],
        model: RecordedModel,
    ) -> "RecordingFitInputs":
        # Increment when recording-wide fitting or its evidence-selection rules change.
        return cls(
            algorithm_version=1,
            keypoint_names=names,
            points=point_array_signature(values),
            model=definition_signature(model),
        )


@dataclass(frozen=True, slots=True)
class FittedRecordingScale:
    inputs: RecordingFitInputs
    fit: ModelScaleFit | None
