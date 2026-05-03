"""
Enum definitions for all posthoc pipeline phase strings.

These values are sent over the WebSocket to the frontend as-is, so the string
values must stay in sync with the BACKEND_PHASE_MAP in ServerContextProvider.tsx.
"""
from enum import Enum


class _StrValueEnum(str, Enum):
    """Base that makes str() return the value, not 'ClassName.MEMBER'."""
    def __str__(self) -> str:
        return self.value


class VideoNodePhase(_StrValueEnum):
    """Phases emitted by individual video processing nodes."""
    SETTING_UP = "setting_up"
    PROCESSING_IMAGES = "processing_images"
    COMPLETE = "complete"
    FAILED = "failed"


class AggregatorPhase(_StrValueEnum):
    """Phases emitted by the posthoc aggregation node itself."""
    COLLECTING_CAMERA_OUTPUT = "collecting_camera_output"
    COMPLETE = "complete"
    FAILED = "failed"


class MocapStage(_StrValueEnum):
    """Stages within the posthoc mocap task function."""
    BUILDING_RECORDERS = "building_recorders"
    TRIANGULATING = "triangulating"
    EXPORTING_BLENDER = "exporting_blender"


class CalibrationStage(_StrValueEnum):
    """Stages within the posthoc calibration task function."""
    VALIDATING_OBSERVATIONS = "validating_observations"
    RUNNING_SOLVER = "running_solver"
    SAVING_CALIBRATION = "saving_calibration"


class PosthocPipelineType(_StrValueEnum):
    """Identifies what kind of posthoc pipeline is running.

    Sent over the WebSocket in every progress message so the frontend can
    route updates to the correct Redux slice without guessing from phase names.
    Must stay in sync with PipelineType in pipelines-slice.ts.
    """
    CALIBRATION = "calibration"
    MOCAP = "mocap"
