import logging
import multiprocessing
from dataclasses import dataclass, field

from fastapi import FastAPI
from skellycam.core.recorders.videos.recording_info import RecordingInfo

from freemocap.core.pipeline.pipeline_configs import PipelineConfig, CalibrationTaskConfig
from freemocap.core.pipeline.posthoc_pipeline.posthoc_calibration_pipeline import PosthocProcessingPipeline
from freemocap.core.types.type_overloads import PipelineIdString

logger = logging.getLogger(__name__)


@dataclass
class PosthocPipelineManager:
    global_kill_flag: multiprocessing.Value
    heartbeat_timestamp: multiprocessing.Value
    subprocess_registry: list[multiprocessing.Process]
    lock: multiprocessing.Lock = field(default_factory=multiprocessing.Lock)
    posthoc_pipelines: dict[PipelineIdString, PosthocProcessingPipeline] = field(default_factory=dict)

    @classmethod
    def from_fastapi_app(cls, fastapi_app: FastAPI) -> 'RealtimePipelineManager':
        return cls(global_kill_flag=fastapi_app.state.global_kill_flag,
                   heartbeat_timestamp=fastapi_app.state.heartbeat_timestamp,
                   subprocess_registry=fastapi_app.state.subprocess_registry)

    async def create_posthoc_calibration_pipeline(self,
                                      recording_info: RecordingInfo,
                                      calibration_task_config: CalibrationTaskConfig) -> PosthocProcessingPipeline:
        with self.lock:
            pipeline = PosthocCalibrationProcessingPipeline.from_config(task_config=calibration_task_config,
                                                             heartbeat_timestamp=self.heartbeat_timestamp,
                                                             subprocess_registry=self.subprocess_registry)
            pipeline.start()
            self.posthoc_pipelines[pipeline.id] = pipeline
            logger.info(f"Post-hoc pipeline with ID: {pipeline.id} for recording '{recording_info.recording_name}' created successfully")
            return pipeline


    def close_all_posthoc_pipelines(self):
        with self.lock:
            for pipeline in self.posthoc_pipelines.values():
                pipeline.shutdown()
            self.posthoc_pipelines.clear()
        logger.info("All pipelines closed successfully")

