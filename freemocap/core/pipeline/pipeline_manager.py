import multiprocessing
from dataclasses import dataclass, field

from skellycam.core.camera_group.camera_group import CameraGroup

from freemocap.core.pipeline.pipeline_configs import PipelineConfig
from freemocap.core.pipeline.processing_pipeline import ProcessingPipeline
from freemocap.core.types.type_overloads import PipelineIdString, FrameNumberInt

import logging
logger = logging.getLogger(__name__)

@dataclass
class PipelineManager:
    global_kill_flag: multiprocessing.Value
    pipelines: dict[PipelineIdString, ProcessingPipeline] = field(default_factory=dict)

    def create_pipeline(self,
                        camera_group:CameraGroup,
                        pipeline_config:PipelineConfig ) -> ProcessingPipeline:
        pipeline =  ProcessingPipeline.from_camera_group(camera_group=camera_group,
                                                        pipeline_config=pipeline_config)
        pipeline.start()
        self.pipelines[pipeline.id] = pipeline
        logger.info(f"Created pipeline with ID: {pipeline.id} for camera group ID: {camera_group.id}")
        return pipeline

    def close_all_pipelines(self):
        for pipeline in self.pipelines.values():
            pipeline.shutdown()
        self.pipelines.clear()
        logger.info("All pipelines closed successfully")

    def get_latest_frontend_payloads(self,if_newer_than:FrameNumberInt) -> dict[PipelineIdString, dict]:
        payloads = {}
        for pipeline_id, pipeline in self.pipelines.items():
            payload = pipeline.get_latest_frontend_payload(if_newer_than=if_newer_than)
            if payload is not None:
                payloads[pipeline_id] = payload
        return payloads