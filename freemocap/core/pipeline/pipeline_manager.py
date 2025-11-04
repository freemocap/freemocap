import logging
import multiprocessing
from copy import deepcopy
from dataclasses import dataclass, field

from skellycam.core.recorders.videos.recording_info import RecordingInfo

from freemocap.core.pipeline.pipeline_configs import PipelineConfig, CalibrationTaskConfig
from freemocap.core.pipeline.processing_pipeline import ProcessingPipeline, FrontendPayload
from freemocap.core.types.type_overloads import PipelineIdString

logger = logging.getLogger(__name__)

@dataclass
class PipelineManager:
    global_kill_flag: multiprocessing.Value
    subprocess_registry: list[multiprocessing.Process]
    lock: multiprocessing.Lock = field(default_factory=multiprocessing.Lock)
    pipelines: dict[PipelineIdString, ProcessingPipeline] = field(default_factory=dict)

    def create_or_update_pipeline(self,
                                  pipeline_config:PipelineConfig) -> ProcessingPipeline:
        with self.lock:
            # get existing pipeline for the provided camera configs, if it exists
            for pipeline in self.pipelines.values():
                if set(pipeline.camera_ids) == set(pipeline_config.camera_ids):
                    logger.info(f"Found existing pipeline with ID: {pipeline.id} for camera group ID: {pipeline.camera_group_id}")
                    pipeline.update_camera_configs(camera_configs=pipeline_config.camera_configs)
                    return pipeline
            pipeline =  ProcessingPipeline.from_config(pipeline_config=pipeline_config,
                                                       subprocess_registry=self.subprocess_registry,
                                                        global_kill_flag=self.global_kill_flag)
            pipeline.start()
            self.pipelines[pipeline.id] = pipeline
            logger.info(f"Created pipeline with ID: {pipeline.id} for camera group ID: {pipeline.camera_group_id}")
            return pipeline

    def close_all_pipelines(self):
        with self.lock:
            for pipeline in self.pipelines.values():
                pipeline.shutdown()
            self.pipelines.clear()
        logger.info("All pipelines closed successfully")

    def get_latest_frontend_payloads(self) -> dict[PipelineIdString,  tuple[bytes | None, FrontendPayload | None]]:
        latest_outputs = {}
        with self.lock:
            for pipeline_id, pipeline in self.pipelines.items():
                output = pipeline.get_latest_frontend_payload()
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



    def update_calibration_task_config(self, calibration_task_config:CalibrationTaskConfig):
        with self.lock:
            for pipeline in self.pipelines.values():
                new_config = deepcopy(pipeline.config)
                new_config.calibration_task_config = calibration_task_config
                pipeline.update_pipeline_config(new_config=new_config)