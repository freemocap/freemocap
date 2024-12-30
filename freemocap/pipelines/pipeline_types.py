from enum import Enum

from freemocap.pipelines.calibration_pipeline.calibration_pipeline_main import CalibrationPipeline
from freemocap.pipelines.dummy_pipeline import DummyPipeline


class PipelineTypes(Enum):
    DUMMY = DummyPipeline
    CALIBRATION = CalibrationPipeline
