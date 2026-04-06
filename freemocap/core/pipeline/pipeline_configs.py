"""
Pipeline configuration types.

All detector/task configs live here.
used to tell child processes which detector to instantiate.
"""
from enum import Enum
from typing import Annotated, Any, Union

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag
from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.types.type_overloads import CameraIdString
from skellytracker.trackers.charuco_tracker.charuco_detector import CharucoDetectorConfig
from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseDetectorConfig
from skellytracker.trackers.legacy_mediapipe_tracker.legacy_mediapipe_annotator import LegacyMediapipeAnnotatorConfig
from skellytracker.trackers.mediapipe_tracker import MediapipeDetectorConfig
from skellytracker.trackers.legacy_mediapipe_tracker.legacy_mediapipe_detector_config import LegacyMediapipeDetectorConfig
from skellytracker.trackers.mediapipe_tracker.body.mediapipe_pose_config import MediapipePoseConfig

from skellytracker.trackers.mediapipe_tracker.mediapipe_model_manager import MediapipePoseModelComplexity

from freemocap.core.calibration.pyceres_calibration.helpers.models import PyceresCalibrationSolverConfig
from freemocap.core.mocap.skeleton_dewiggler.realtime_skeleton_filter import RealtimeFilterConfig

# TODO - This should live in skellytracker
def create_detector_from_config(detector_config: BaseDetectorConfig):
    """
    Create a detector instance from a picklable config.
    Called inside child processes — detector class imports are deferred
    to avoid pulling in mediapipe/cv2.aruco during module import.
    """

    match detector_config:
        case CharucoDetectorConfig():
            from skellytracker.trackers.charuco_tracker.charuco_detector import CharucoDetector
            return CharucoDetector.create(config=detector_config)
        case MediapipeDetectorConfig():
            from skellytracker.trackers.mediapipe_tracker import MediapipeDetector
            return MediapipeDetector.create(config=detector_config)
        case LegacyMediapipeDetectorConfig():
            from skellytracker.trackers.legacy_mediapipe_tracker.legacy_mediapipe_detector import LegacyMediapipeDetector
            return LegacyMediapipeDetector.create(config=detector_config)
        case _:
            raise TypeError(f"Unknown detector config type: {type(detector_config).__name__}")


def create_annotator_from_config(config: BaseDetectorConfig):
    """
    Create an image annotator matching the given detector config.
    Called inside child processes for drawing detection results onto frames.
    """

    match config:
        case CharucoDetectorConfig():
            from skellytracker.trackers.charuco_tracker.charuco_annotator import CharucoImageAnnotator, \
                CharucoAnnotatorConfig
            return CharucoImageAnnotator.create(config=CharucoAnnotatorConfig())
        case MediapipeDetectorConfig():
            from skellytracker.trackers.mediapipe_tracker import MediapipeAnnotator, MediapipeAnnotatorConfig
            return MediapipeAnnotator.create(config=MediapipeAnnotatorConfig())
        case LegacyMediapipeDetectorConfig():
            from skellytracker.trackers.legacy_mediapipe_tracker.legacy_mediapipe_annotator import LegacyMediapipeImageAnnotator, LegacyMediapipeAnnotatorConfig
            return LegacyMediapipeImageAnnotator.create(config=LegacyMediapipeAnnotatorConfig())
        case _:
            raise TypeError(f"Unknown detector config type for annotator: {type(config).__name__}")


# ---------------------------------------------------------------------------
# Calibration solver selection
# ---------------------------------------------------------------------------


class CalibrationSolverMethod(str, Enum):
    """Which calibration solver backend to use."""
    ANIPOSE = "anipose"
    PYCERES = "pyceres"


# ---------------------------------------------------------------------------
# Task configs
# ---------------------------------------------------------------------------


class CalibrationPipelineConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    calibration_recording_folder: str | None = Field(
        default=None, alias="calibrationRecordingFolder",
    )
    charuco_board_x_squares: int = Field(gt=0, default=7, alias="charucoBoardXSquares")
    charuco_board_y_squares: int = Field(gt=0, default=5, alias="charucoBoardYSquares")
    # charuco_square_length: float = Field(gt=0, default=1, alias="charucoSquareLength")

    solver_method: CalibrationSolverMethod = Field(
        default=CalibrationSolverMethod.ANIPOSE,
        alias="solverMethod",
        description="Which calibration solver to use: 'anipose' (legacy) or 'pyceres' (new bundle adjustment).",
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

    @property
    def detector_config(self) -> CharucoDetectorConfig:
        return CharucoDetectorConfig(
            squares_x=self.charuco_board_x_squares,
            squares_y=self.charuco_board_y_squares,
            # square_length=self.charuco_square_length,
        )



def _detect_detector_config_type(data: Any) -> str:
    """Inspect raw data to determine which detector config subclass to use."""
    if isinstance(data, BaseDetectorConfig):
        if isinstance(data, CharucoDetectorConfig):
            return "charuco"
        if isinstance(data, MediapipeDetectorConfig):
            return "mediapipe"
        return "legacy_mediapipe"
    if isinstance(data, dict):
        if "squares_x" in data or "aruco_dictionary_name" in data:
            return "charuco"
        if "pose_config" in data or "hand_config" in data or "face_config" in data:
            return "mediapipe"
    return "legacy_mediapipe"

# TODO - move this to skellytracker
DetectorConfig = Annotated[
    Union[
        Annotated[LegacyMediapipeDetectorConfig, Tag("legacy_mediapipe")],
        Annotated[MediapipeDetectorConfig, Tag("mediapipe")],
        Annotated[CharucoDetectorConfig, Tag("charuco")],
    ],
    Discriminator(_detect_detector_config_type),
]


class MocapPipelineConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    detector_config: DetectorConfig = Field(default_factory=LegacyMediapipeDetectorConfig)
    realtime_filter_config: RealtimeFilterConfig = Field(default_factory=RealtimeFilterConfig)
    calibration_toml_path: str | None = Field(
        default=None,
        alias="calibrationTomlPath",
        description="Optional override for calibration TOML file. If None, uses the most recent successful calibration.",
    )

    @classmethod
    def default_realtime(cls) -> "MocapPipelineConfig":
        return cls(detector_config=MediapipeDetectorConfig(
            pose_config=MediapipePoseConfig(model_complexity=MediapipePoseModelComplexity.LITE)
        ))

    @classmethod
    def default_posthoc(cls) -> "MocapPipelineConfig":
        return cls(detector_config=LegacyMediapipeDetectorConfig())





# ---------------------------------------------------------------------------
# Top-level realtime pipeline config
# ---------------------------------------------------------------------------

class RealtimePipelineConfig(BaseModel):
    camera_configs: CameraConfigs
    calibration_config: CalibrationPipelineConfig = Field(
        default_factory=CalibrationPipelineConfig,
    )
    mocap_config: MocapPipelineConfig = Field(
        default_factory=MocapPipelineConfig.default_realtime,
    )
    calibration_detection_enabled: bool = Field(default=True)
    mocap_detection_enabled: bool = Field(default=True)

    @property
    def camera_ids(self) -> list[CameraIdString]:
        return list(self.camera_configs.keys())

    @classmethod
    def from_camera_configs(cls, *, camera_configs: CameraConfigs) -> "RealtimePipelineConfig":
        return cls(camera_configs=camera_configs)
