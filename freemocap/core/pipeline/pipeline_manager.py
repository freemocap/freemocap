import logging
import multiprocessing
from copy import deepcopy
from dataclasses import dataclass, field

from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.pipeline.pipeline_configs import PipelineConfig, CalibrationTaskConfig
from freemocap.core.pipeline.processing_pipeline import ProcessingPipeline, FrontendPayload
from freemocap.core.tasks.calibration_task.v1_capture_volume_calibration.anipose_camera_calibration.freemocap_anipose import \
    CameraGroup
from freemocap.core.types.type_overloads import PipelineIdString, FrameNumberInt

logger = logging.getLogger(__name__)


@dataclass
class PipelineManager:
    global_kill_flag: multiprocessing.Value
    subprocess_registry: list[multiprocessing.Process]
    lock: multiprocessing.Lock = field(default_factory=multiprocessing.Lock)
    pipelines: dict[PipelineIdString, ProcessingPipeline] = field(default_factory=dict)

    def create_pipeline(self,
                        camera_group:CameraGroup,
                        pipeline_config: PipelineConfig) -> ProcessingPipeline:
        with self.lock:
            # get existing pipeline for the provided camera configs, if it exists
            for pipeline in self.pipelines.values():
                if set(pipeline.camera_ids) == set(pipeline_config.camera_ids):
                    logger.info(
                        f"Found existing pipeline with ID: {pipeline.id} for camera group ID: {pipeline.camera_group_id}")
                    pipeline.update_camera_configs(camera_configs=pipeline_config.camera_configs)
                    return pipeline
            pipeline = ProcessingPipeline.from_config(pipeline_config=pipeline_config,
                                                        camera_group=camera_group,
                                                      subprocess_registry=self.subprocess_registry)
            pipeline.start()
            self.pipelines[pipeline.id] = pipeline
            logger.info(f"Created pipeline with ID: {pipeline.id} for camera group ID: {pipeline.camera_group_id}")
            return pipeline
    def update_pipeline(self,
                                  pipeline_config: PipelineConfig) -> ProcessingPipeline:
        with self.lock:
            # get existing pipeline for the provided camera configs, if it exists
            for pipeline in self.pipelines.values():
                if set(pipeline.camera_ids) == set(pipeline_config.camera_ids):
                    logger.info(
                        f"Found existing pipeline with ID: {pipeline.id} for camera group ID: {pipeline.camera_group_id}")
                    pipeline.update_camera_configs(camera_configs=pipeline_config.camera_configs)
                    return pipeline
        raise RuntimeError("No existing pipeline found for the provided camera configs.")

    def close_all_pipelines(self):
        with self.lock:
            for pipeline in self.pipelines.values():
                pipeline.shutdown()
            self.pipelines.clear()
        logger.info("All pipelines closed successfully")

    def get_latest_frontend_payloads(self, if_newer_than: FrameNumberInt) -> dict[
        PipelineIdString, tuple[bytes | None, FrontendPayload | None]]:
        latest_outputs = {}
        with self.lock:
            for pipeline_id, pipeline in self.pipelines.items():
                output = pipeline.get_latest_frontend_payload(if_newer_than=if_newer_than)
                if not output is None:
                    latest_outputs[pipeline_id] = output
        return latest_outputs

    def pause_unpause_pipelines(self):
        with self.lock:
            for pipeline in self.pipelines.values():
                pipeline.camera_group.pause_unpause()

    def start_recording_all(self, recording_info: RecordingInfo):
        with self.lock:
            for pipeline in self.pipelines.values():
                pipeline.camera_group.start_recording(recording_info=recording_info)

    def stop_recording_all(self):
        with self.lock:
            for pipeline in self.pipelines.values():
                pipeline.camera_group.stop_recording()

    def update_calibration_task_config(self, calibration_task_config: CalibrationTaskConfig):
        with self.lock:
            for pipeline in self.pipelines.values():
                new_config = deepcopy(pipeline.config)
                new_config.calibration_task_config = calibration_task_config
                pipeline.update_pipeline_config(new_config=new_config)

    def start_calibration_calibration_recording(self, recording_info: RecordingInfo, config: CalibrationTaskConfig):
        if len(self.pipelines) == 0:
            raise RuntimeError("No pipelines available to start calibration recording.")
        if len(self.pipelines) > 1:
            raise NotImplementedError(
                "Multiple pipeline selection for calibration recording not implemented - will use 'pipeline_id' parameter in future.")
        with self.lock:
            for pipeline in self.pipelines.values():
                pipeline.start_calibration_recording(config=config,
                                                     recording_info=recording_info)

    def stop_calibration_recording(self):
        if len(self.pipelines) == 0:
            raise RuntimeError("No pipelines available to stop calibration recording.")
        if len(self.pipelines) > 1:
            raise NotImplementedError(
                "Multiple pipeline selection for calibration recording not implemented - will use 'pipeline_id' parameter in future.")
        with self.lock:
            for pipeline in self.pipelines.values():
                pipeline.stop_calibration_recording()

    def get_pipeline_by_camera_ids(self, camera_ids: list[CameraIdString]) -> ProcessingPipeline | None:
        with self.lock:
            for pipeline in self.pipelines.values():
                if set(pipeline.camera_ids) == set(camera_ids):
                    return pipeline
        return None

