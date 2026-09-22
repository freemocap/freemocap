"""Metadata shared by calibration results and saved calibration artifacts."""

from pydantic import BaseModel, ConfigDict, Field
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition

from freemocap.core.tasks.calibration.calibration_task_config import CalibrationSolverMethod
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
    groundplane_aligned: bool = Field(default=False, alias="groundplane_applied")

    # Missing historical provenance remains unknown.
    solver_method: CalibrationSolverMethod | None = None
    recording_info: RecordingInfo | None = None
    groundplane_method: CalibrationAlignmentMethod | None = None
    groundplane_recording_id: str | None = None
    groundplane_result: GroundPlaneResult | None = None
