import logging
import multiprocessing
from dataclasses import dataclass, field

from fastapi import FastAPI
from skellycam.core.recorders.videos.recording_info import RecordingInfo

from freemocap.core.pipeline.posthoc_pipelines.posthoc_calibration_pipeline.posthoc_calibration_pipeline import \
    CalibrationTaskConfig, PosthocCalibrationProcessingPipeline
from freemocap.core.pipeline.posthoc_pipelines.posthoc_mocap_pipeline.posthoc_mocap_pipeline import MocapTaskConfig, \
    PosthocMocapProcessingPipeline
from freemocap.core.types.type_overloads import PipelineIdString

logger = logging.getLogger(__name__)


@dataclass
class PosthocPipelineManager:
    global_kill_flag: multiprocessing.Value
    heartbeat_timestamp: multiprocessing.Value
    subprocess_registry: list[multiprocessing.Process]
    lock: multiprocessing.Lock = field(default_factory=multiprocessing.Lock)
    posthoc_pipelines: dict[PipelineIdString, PosthocCalibrationProcessingPipeline] = field(default_factory=dict)

    @classmethod
    def from_fastapi_app(cls, fastapi_app: FastAPI) -> 'RealtimePipelineManager':
        return cls(global_kill_flag=fastapi_app.state.global_kill_flag,
                   heartbeat_timestamp=fastapi_app.state.heartbeat_timestamp,
                   subprocess_registry=fastapi_app.state.subprocess_registry)

    async def create_posthoc_calibration_pipeline(self,
                                                  recording_info: RecordingInfo,
                                                  calibration_task_config: CalibrationTaskConfig) -> PosthocCalibrationProcessingPipeline:
        with self.lock:
            pipeline = PosthocCalibrationProcessingPipeline.from_task_config(
                calibration_task_config=calibration_task_config,
                recording_info=recording_info,
                heartbeat_timestamp=self.heartbeat_timestamp,
                subprocess_registry=self.subprocess_registry,
                global_kill_flag=self.global_kill_flag,
            )
            pipeline.start()
            self.posthoc_pipelines[pipeline.id] = pipeline
            logger.info(
                f"Post-hoc pipeline with ID: {pipeline.id} for recording '{recording_info.recording_name}' created successfully")
            return pipeline

    async def create_posthoc_mocap_pipeline(self, recording_info:RecordingInfo, mocap_task_config:MocapTaskConfig):
        with self.lock:
            pipeline = PosthocMocapProcessingPipeline.from_task_config(
                mocap_task_config=mocap_task_config,
                recording_info=recording_info,
                heartbeat_timestamp=self.heartbeat_timestamp,
                subprocess_registry=self.subprocess_registry,
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

