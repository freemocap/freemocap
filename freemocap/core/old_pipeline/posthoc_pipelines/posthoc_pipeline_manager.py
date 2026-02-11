import logging
import multiprocessing
from dataclasses import dataclass, field

from fastapi import FastAPI
from freemocap.core.pipeline.posthoc_pipelines.posthoc_calibration_pipeline.posthoc_calibration_pipeline import \
    CalibrationpipelineConfig, PosthocCalibrationProcessingPipeline
from freemocap.core.pipeline.posthoc_pipelines.posthoc_mocap_pipeline.posthoc_mocap_pipeline import \
    MocapPipelineTaskConfig, \
    PosthocMocapProcessingPipeline
from skellycam.core.ipc.process_management.process_registry import ProcessRegistry
from skellycam.core.recorders.videos.recording_info import RecordingInfo

from freemocap.core.types.type_overloads import PipelineIdString

logger = logging.getLogger(__name__)


@dataclass
class PosthocPipelineManager:
    global_kill_flag: multiprocessing.Value
    process_registry: ProcessRegistry
    lock: multiprocessing.Lock = field(default_factory=multiprocessing.Lock)
    posthoc_pipelines: dict[PipelineIdString, PosthocCalibrationProcessingPipeline|PosthocMocapProcessingPipeline] = field(default_factory=dict)

    @classmethod
    def from_fastapi_app(cls, fastapi_app: FastAPI):
        return cls(global_kill_flag=fastapi_app.state.global_kill_flag,
                   process_registry=fastapi_app.state.process_registry)

    async def create_posthoc_calibration_pipeline(self,
                                                  recording_info: RecordingInfo,
                                                  calibration_pipeline_config: CalibrationpipelineConfig) -> PosthocCalibrationProcessingPipeline:
        with self.lock:
            pipeline = PosthocCalibrationProcessingPipeline.from_config(
                calibration_pipeline_config=calibration_pipeline_config,
                recording_info=recording_info,
                process_registry=self.process_registry,
                global_kill_flag=self.global_kill_flag,
            )
            pipeline.start()
            self.posthoc_pipelines[pipeline.id] = pipeline
            logger.info(
                f"Post-hoc pipeline with ID: {pipeline.id} for recording '{recording_info.recording_name}' created successfully")
            return pipeline

    async def create_posthoc_mocap_pipeline(self, recording_info:RecordingInfo, mocap_task_config:MocapPipelineTaskConfig):
        with self.lock:
            pipeline = PosthocMocapProcessingPipeline.from_task_config(
                mocap_task_config=mocap_task_config,
                recording_info=recording_info,
                process_registry=self.process_registry,
                global_kill_flag=self.global_kill_flag,
            )
            pipeline.start()
            self.posthoc_pipelines[pipeline.id] = pipeline
            logger.info(
                f"Post-hoc pipeline with ID: {pipeline.id} for recording '{recording_info.recording_name}' created successfully")
            return pipeline

    def close_all_posthoc_pipelines(self):
        with self.lock:
            for pipeline in self.posthoc_pipelines.values():
                pipeline.shutdown()
            self.posthoc_pipelines.clear()
        logger.info("All pipelines closed successfully")

