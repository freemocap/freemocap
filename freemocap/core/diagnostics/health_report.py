"""Validated statistics and explicit assessment criteria shared by diagnostic consumers."""

from dataclasses import asdict, dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from skellyforge.core.skeleton.pose.rigid_body_diagnostics import ResidualAccumulator

from freemocap.core.types.channel_kind import ChannelKind


class DiagnosticModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class MeasurementStatistics(DiagnosticModel):
    sample_count: int = Field(ge=0)
    unavailable_count: int = Field(ge=0)
    mean: float | None
    rms: float | None = Field(ge=0)
    standard_deviation: float | None = Field(ge=0)
    minimum: float | None
    maximum: float | None

    @model_validator(mode="after")
    def validate_availability(self) -> "MeasurementStatistics":
        values = (
            self.mean,
            self.rms,
            self.standard_deviation,
            self.minimum,
            self.maximum,
        )
        if self.sample_count == 0:
            if any(value is not None for value in values):
                raise ValueError("Empty measurements require unavailable statistics")
        elif any(value is None for value in values):
            raise ValueError("Finite measurements require complete statistics")
        if (
            self.minimum is not None
            and self.maximum is not None
            and self.minimum > self.maximum
        ):
            raise ValueError("Minimum cannot exceed maximum")
        return self


@dataclass(slots=True)
class MeasurementAccumulator:
    values: ResidualAccumulator = field(default_factory=ResidualAccumulator)
    minimum: float | None = None
    maximum: float | None = None

    def add(self, *, value: float | None) -> None:
        self.values.add(residual=value)
        if value is not None:
            self.minimum = value if self.minimum is None else min(self.minimum, value)
            self.maximum = value if self.maximum is None else max(self.maximum, value)

    def summary(self) -> MeasurementStatistics:
        return MeasurementStatistics(
            **asdict(self.values.summary()), minimum=self.minimum, maximum=self.maximum
        )


class AssessmentCriterion(DiagnosticModel):
    channel: ChannelKind
    component: str = Field(min_length=1)
    units: str = Field(min_length=1)
    maximum_rms: float = Field(ge=0)
    minimum_available_fraction: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def validate_error_measurement(self) -> "AssessmentCriterion":
        if (self.channel, self.component) not in (
            (ChannelKind.REPROJECTION_ERROR, "error"),
            (ChannelKind.RIGID_BODY_RESIDUALS, "residual"),
        ):
            raise ValueError(
                "Maximum RMS criteria require error or residual measurements"
            )
        return self


class MeasurementAssessment(DiagnosticModel):
    status: Literal["pass", "fail", "insufficient_data", "not_assessed"]
    reason: str
    criterion: AssessmentCriterion | None


def assess_measurement(
    *, statistics: MeasurementStatistics, criterion: AssessmentCriterion | None
) -> MeasurementAssessment:
    if statistics.sample_count == 0:
        return MeasurementAssessment(
            status="insufficient_data",
            reason="No finite measurements are available.",
            criterion=criterion,
        )
    if criterion is None:
        return MeasurementAssessment(
            status="not_assessed",
            reason="No quality criterion is configured for this measurement.",
            criterion=None,
        )
    coverage = statistics.sample_count / (
        statistics.sample_count + statistics.unavailable_count
    )
    if coverage < criterion.minimum_available_fraction:
        return MeasurementAssessment(
            status="insufficient_data",
            reason="Available sample fraction is below the configured minimum.",
            criterion=criterion,
        )
    if statistics.rms is None:
        raise ValueError("Finite measurements require an RMS statistic")
    passed = statistics.rms <= criterion.maximum_rms
    return MeasurementAssessment(
        status="pass" if passed else "fail",
        reason="RMS is within the configured maximum."
        if passed
        else "RMS exceeds the configured maximum.",
        criterion=criterion,
    )
