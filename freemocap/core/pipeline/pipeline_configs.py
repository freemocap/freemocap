"""
Pipeline configuration types.

All detector/task configs live here. DetectorSpec is the picklable union
used to tell child processes which detector to instantiate.
"""
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field
from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.types.type_overloads import CameraIdString
from skellytracker.trackers.charuco_tracker.charuco_detector import CharucoDetectorConfig
from skellytracker.trackers.mediapipe_tracker.mediapipe_detector_config import (
    MediapipeDetectorConfig,
    MediapipeModelComplexity,
    MEDIAPIPE_TRACKER_REALTIME_PRESET,
    MEDIAPIPE_TRACKER_POSTHOC_PRESET,
)

from freemocap.core.calibration.pyceres_calibration.helpers.models import PyceresCalibrationSolverConfig
from freemocap.core.mocap.skeleton_dewiggler.realtime_skeleton_filter import RealtimeFilterConfig

# ---------------------------------------------------------------------------
# Detector spec: the picklable union that video nodes use to create detectors
# ---------------------------------------------------------------------------

DetectorSpec = CharucoDetectorConfig | MediapipeDetectorConfig


def create_detector_from_spec(spec: DetectorSpec):
    """
    Create a detector instance from a picklable spec.
    Called inside child processes — detector class imports are deferred
    to avoid pulling in mediapipe/cv2.aruco during module import.
    """

    match spec:
        case CharucoDetectorConfig():
            from skellytracker.trackers.charuco_tracker.charuco_detector import CharucoDetector
            return CharucoDetector.create(config=spec)
        case MediapipeDetectorConfig():
            from skellytracker.trackers.mediapipe_tracker.mediapipe_detector import MediapipeDetector
            return MediapipeDetector.create(config=spec)
        case _:
            raise TypeError(f"Unknown detector spec type: {type(spec).__name__}")


def create_annotator_from_spec(spec: DetectorSpec):
    """
    Create an image annotator matching the given detector spec.
    Called inside child processes for drawing detection results onto frames.
    """
    from skellytracker.trackers.charuco_tracker.charuco_annotator import CharucoImageAnnotator, CharucoAnnotatorConfig
    from skellytracker.trackers.mediapipe_tracker.mediapipe_annotator import MediapipeImageAnnotator, MediapipeAnnotatorConfig

    match spec:
        case CharucoDetectorConfig():
            return CharucoImageAnnotator.create(config=CharucoAnnotatorConfig())
        case MediapipeDetectorConfig():
            return MediapipeImageAnnotator.create(config=MediapipeAnnotatorConfig())
        case _:
            raise TypeError(f"Unknown detector spec type for annotator: {type(spec).__name__}")


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
    charuco_board_x_squares: int = Field(gt=0, default=5, alias="charucoBoardXSquares")
    charuco_board_y_squares: int = Field(gt=0, default=3, alias="charucoBoardYSquares")
    charuco_square_length: float = Field(gt=0, default=1, alias="charucoSquareLength")

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
            square_length=self.charuco_square_length,
        )

    @property
    def detector_spec(self) -> DetectorSpec:
        return self.detector_config


class MocapPipelineConfig(BaseModel):
    detector: MediapipeDetectorConfig
    skeleton_filter: RealtimeFilterConfig = Field(default_factory=RealtimeFilterConfig)

    @classmethod
    def default_realtime(cls) -> "MocapPipelineConfig":
        return cls(detector=MEDIAPIPE_TRACKER_REALTIME_PRESET)

    @classmethod
    def default_posthoc(cls) -> "MocapPipelineConfig":
        return cls(detector=MEDIAPIPE_TRACKER_POSTHOC_PRESET)





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