"""Explicit boundaries and result retention for posthoc processing."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProcessingStage(StrEnum):
    TIMING = "timing"
    OBSERVATIONS = "observations"
    CALIBRATION = "calibration"
    TRIANGULATION = "triangulation"
    FILTERING = "filtering"
    SCALE_FIT = "scale_fit"
    RECONSTRUCTION = "reconstruction"
    BIOMECHANICS = "biomechanics"


STAGE_ORDER = tuple(ProcessingStage)


class ProcessingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    base_run_id: int = Field(default=0, ge=0)
    keep: bool = False
    solve_calibration: bool = False
    start_stage: ProcessingStage = ProcessingStage.TIMING
    stop_stage: ProcessingStage = ProcessingStage.BIOMECHANICS
    sensor_groups: tuple[str, ...]

    @model_validator(mode="after")
    def validate_scope(self) -> "ProcessingRequest":
        if not self.sensor_groups or len(set(self.sensor_groups)) != len(
            self.sensor_groups
        ):
            raise ValueError("sensor_groups must be nonempty and unique")
        if any(not group for group in self.sensor_groups):
            raise ValueError("sensor group names must not be empty")
        if STAGE_ORDER.index(self.start_stage) > STAGE_ORDER.index(self.stop_stage):
            raise ValueError("start_stage must precede stop_stage")
        return self
