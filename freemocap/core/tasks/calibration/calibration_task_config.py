from enum import Enum

from pydantic import BaseModel, ConfigDict, Field
from skellytracker.core import DetectionStageConfig, TrackerConfig
from skellytracker.core.detectors.keypoint_detectors.charuco import (
    CharucoBoardDefinition,
    CharucoDetectorConfig,
)

from freemocap.core.tasks.calibration.pyceres_calibration.helpers.models import PyceresCalibrationSolverConfig
from freemocap.core.tasks.triangulation.helpers.triangulation_config import TriangulationConfig


class CalibrationSolverMethod(str, Enum):
    """Which calibration solver backend to use."""
    ANIPOSE = "anipose"
    PYCERES = "pyceres"


class PosthocCalibrationPipelineConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    calibration_recording_folder: str | None = Field(
        default=None, alias="calibrationRecordingFolder",
    )
    charuco_board: CharucoBoardDefinition = Field(default_factory=CharucoBoardDefinition.create_letter_size_5x3,
                                                  alias="charucoBoard",
                                                  description="Definition of the charuco board used for calibration")
    solver_method: CalibrationSolverMethod = Field(
        default=CalibrationSolverMethod.ANIPOSE,
        alias="solverMethod",
        description="Which calibration solver to use: 'anipose' (legacy) or 'pyceres' ( untested bundle adjustment based calibration method).",
    )

    pyceres_solver_config: PyceresCalibrationSolverConfig = Field(
        default_factory=PyceresCalibrationSolverConfig,
        alias="pyceresSolverConfig",
        description="Configuration for the pyceres bundle adjustment solver. Only used when solver_method='pyceres'.",
    )

    use_groundplane: bool = Field(
        default=False,
        alias="useGroundplane",
        description="Align world frame to charuco board plane after calibration.",
    )

    triangulation_config: TriangulationConfig = Field(
        default_factory=TriangulationConfig,
        alias="triangulationConfig",
        description=(
            "Configuration for the post-calibration triangulator: simple DLT "
            "vs. subset-ensemble outlier rejection, plus the outlier-rejection knobs."
        ),
    )

    @property
    def detector_config(self) -> TrackerConfig:
        return TrackerConfig(
            stages=[
                DetectionStageConfig(
                    name="charuco",
                    keypoint_detectors=[CharucoDetectorConfig(board=self.charuco_board)],
                )
            ]
        )
