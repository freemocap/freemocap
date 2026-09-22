"""Metadata shared by calibration results and saved calibration artifacts."""

from pydantic import BaseModel, ConfigDict, Field, model_validator
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition

from freemocap.core.tasks.calibration.calibration_task_config import CalibrationSolverMethod
from freemocap.core.tasks.calibration.shared.calibration_transform import CalibrationTransform
from freemocap.core.tasks.calibration.shared.groundplane_alignment import (
    CalibrationAlignmentMethod,
    GroundPlaneResult,
)


class CalibrationMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    board: CharucoBoardDefinition
    reprojection_error_px: float
    initial_cost: float
    final_cost: float
    n_iterations: int
    time_seconds: float = Field(alias="solver_time_seconds")
    n_observations_used: int
    n_observations_rejected: int
    aligned: bool = False

    # Missing historical provenance remains unknown.
    solver_method: CalibrationSolverMethod | None = None
    recording_info: RecordingInfo | None = None
    alignment_method: CalibrationAlignmentMethod | None = None
    alignment_recording_id: str | None = None
    # Existing estimator evidence; not the applied scene-transform history.
    alignment_result: GroundPlaneResult | None = None
    transformation_history: list[CalibrationTransform] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_alignment(self) -> "CalibrationMetadata":
        if not self.aligned and (
            self.alignment_method is not None
            or self.alignment_recording_id is not None
            or self.alignment_result is not None
            or self.transformation_history
        ):
            raise ValueError("Alignment provenance requires aligned=True")
        if (
            self.alignment_result is not None
            and self.alignment_method is not None
            and self.alignment_result.method != self.alignment_method
        ):
            raise ValueError("Alignment method disagrees with its recorded result")
        return self
