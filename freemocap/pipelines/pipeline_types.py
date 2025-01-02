from enum import Enum

from freemocap.pipelines.calibration_pipeline.__calibration_pipeline import CalibrationPipeline
from freemocap.pipelines.dummy_pipeline import DummyPipeline


class PipelineTypes(Enum):
    DUMMY = DummyPipeline
    CALIBRATION = CalibrationPipeline
