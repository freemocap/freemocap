from enum import Enum
from freemocap.core.tracking.board_selection import CharucoBoardMode
from freemocap.core.tasks.calibration.shared.groundplane_alignment import CalibrationAlignmentMethod

from pydantic import BaseModel, ConfigDict, Field
from skellytracker.core import DetectionStageConfig, TrackerConfig
from skellytracker.core.detectors.keypoint_detectors.charuco import (
    CharucoBoardDefinition,
    CharucoDetectorConfig,
)

from freemocap.core.tasks.triangulation.helpers.triangulation_config import TriangulationConfig


class CalibrationSolverMethod(str, Enum):
    """Which calibration solver backend to use."""
    ANIPOSE = "anipose"


class PosthocCalibrationPipelineConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    calibration_recording_folder: str | None = Field(
        default=None, alias="calibrationRecordingFolder",
    )
    board_mode: CharucoBoardMode = Field(default=CharucoBoardMode.AUTO, alias="boardMode")
    charuco_board: CharucoBoardDefinition = Field(default_factory=CharucoBoardDefinition.create_letter_size_5x3,
                                                  alias="charucoBoard",
                                                  description="Definition of the charuco board used for calibration")
    solver_method: CalibrationSolverMethod = Field(
        default=CalibrationSolverMethod.ANIPOSE,
        alias="solverMethod",
        description="Calibration solver method.",
    )

    alignment_method: CalibrationAlignmentMethod | None = Field(
        default=None,
        alias="alignmentMethod",
        description="ChArUco alignment runs during calibration; person alignment runs during mocap processing.",
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
    def use_groundplane(self) -> bool:
        return self.alignment_method is CalibrationAlignmentMethod.CHARUCO

    @property
    def detector_config(self) -> TrackerConfig:
        if self.board_mode == CharucoBoardMode.AUTO:
            raise ValueError("Resolve AUTO board selection before constructing calibration detectors")
        return TrackerConfig(
            stages=[
                DetectionStageConfig(
                    name="charuco",
                    keypoint_detectors=[CharucoDetectorConfig(board=self.charuco_board)],
                )
            ]
        )
