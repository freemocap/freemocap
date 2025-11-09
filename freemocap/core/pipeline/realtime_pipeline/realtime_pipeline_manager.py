import logging
import multiprocessing
from copy import deepcopy
from dataclasses import dataclass, field

from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.pipeline.frontend_payload import FrontendPayload
from freemocap.core.pipeline.pipeline_configs import PipelineConfig, CalibrationTaskConfig
from freemocap.core.pipeline.posthoc_pipeline.posthoc_calibration_pipeline import PosthocProcessingPipeline
from freemocap.core.pipeline.realtime_pipeline.realtime_pipeline import RealtimeProcessingPipeline
from freemocap.core.tasks.calibration_task.v1_capture_volume_calibration.anipose_camera_calibration.freemocap_anipose import \
    CameraGroup
from freemocap.core.types.type_overloads import PipelineIdString, FrameNumberInt
from fastapi import FastAPI
logger = logging.getLogger(__name__)


@dataclass
class RealtimePipelineManager:
    global_kill_flag: multiprocessing.Value
    heartbeat_timestamp: multiprocessing.Value
    subprocess_registry: list[multiprocessing.Process]
    lock: multiprocessing.Lock = field(default_factory=multiprocessing.Lock)
    realtime_pipelines: dict[PipelineIdString, RealtimeProcessingPipeline] = field(default_factory=dict)
    posthoc_pipelines: dict[PipelineIdString, PosthocProcessingPipeline] = field(default_factory=dict)

    @classmethod
    def from_fastapi_app(cls, fastapi_app:FastAPI) -> 'RealtimePipelineManager':
        return cls(global_kill_flag=fastapi_app.state.global_kill_flag,
                   heartbeat_timestamp=fastapi_app.state.heartbeat_timestamp,
                   subprocess_registry=fastapi_app.state.subprocess_registry)

    async def create_realtime_pipeline(self,
                                       camera_group: CameraGroup,
                                       pipeline_config: PipelineConfig) -> RealtimeProcessingPipeline:
        with self.lock:
            # get existing pipeline for the provided camera configs, if it exists
            for pipeline in self.realtime_pipelines.values():
                if set(pipeline.camera_ids) == set(pipeline_config.camera_ids):
                    logger.info(
                        f"Found existing pipeline with ID: {pipeline.id} for camera group ID: {pipeline.camera_group_id}")
                    await pipeline.update_camera_configs(camera_configs=pipeline_config.camera_configs)
                    return pipeline
            pipeline = RealtimeProcessingPipeline.from_config(pipeline_config=pipeline_config,
                                                              heartbeat_timestamp=self.heartbeat_timestamp,
                                                              camera_group=camera_group,
                                                              subprocess_registry=self.subprocess_registry)
            pipeline.start()
            self.realtime_pipelines[pipeline.id] = pipeline
            logger.info(f"Created pipeline with ID: {pipeline.id} for camera group ID: {pipeline.camera_group_id}")
            return pipeline

    async def update_realtime_pipeline(self,
                                       pipeline_config: PipelineConfig) -> RealtimeProcessingPipeline:
        with self.lock:
            # get existing pipeline for the provided camera configs, if it exists
            for pipeline in self.realtime_pipelines.values():
                if set(pipeline.camera_ids) == set(pipeline_config.camera_ids):
                    logger.info(
                        f"Found existing pipeline with ID: {pipeline.id} for camera group ID: {pipeline.camera_group_id}")
                    await pipeline.update_camera_configs(camera_configs=pipeline_config.camera_configs)
                    return pipeline
        raise RuntimeError("No existing pipeline found for the provided camera configs.")

    def close_all_realtime_pipelines(self):
        with self.lock:
            for pipeline in self.realtime_pipelines.values():
                pipeline.shutdown()
            self.realtime_pipelines.clear()
        logger.info("All pipelines closed successfully")

    def get_latest_frontend_payloads(self, if_newer_than: FrameNumberInt) -> dict[
        PipelineIdString, tuple[bytes | None, FrontendPayload | None]]:
        latest_outputs = {}
        with self.lock:
            for pipeline_id, pipeline in self.realtime_pipelines.items():
                output = pipeline.get_latest_frontend_payload(if_newer_than=if_newer_than)
                if not output is None:
                    latest_outputs[pipeline_id] = output
        return latest_outputs

    def pause_unpause_pipelines(self):
        with self.lock:
            for pipeline in self.realtime_pipelines.values():
                pipeline.camera_group.pause_unpause()

    async def start_recording_all(self, recording_info: RecordingInfo):
        with self.lock:
            for pipeline in self.realtime_pipelines.values():
                await pipeline.camera_group.start_recording(recording_info=recording_info)

    async def stop_recording_all(self):
        with self.lock:
            for pipeline in self.realtime_pipelines.values():
                await pipeline.camera_group.stop_recording()

    def update_calibration_task_config(self, calibration_task_config: CalibrationTaskConfig):
        with self.lock:
            for pipeline in self.realtime_pipelines.values():
                new_config = deepcopy(pipeline.config)
                new_config.calibration_task_config = calibration_task_config
                pipeline.update_pipeline_config(new_config=new_config)

    def get_pipeline_by_camera_ids(self, camera_ids: list[CameraIdString]) -> RealtimeProcessingPipeline | None:
        with self.lock:
            for pipeline in self.realtime_pipelines.values():
                if set(pipeline.camera_ids) == set(camera_ids):
                    return pipeline
        return None

