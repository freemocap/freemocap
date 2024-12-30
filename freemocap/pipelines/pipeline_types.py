from enum import Enum

from freemocap.pipelines.calibration_pipeline.calibration_pipeline_main import CalibrationPipeline


class PipelineTypes(Enum):
    DUMMY = None
    CALIBRATION = CalibrationPipeline
