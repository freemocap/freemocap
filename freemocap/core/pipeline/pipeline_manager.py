import multiprocessing
from dataclasses import dataclass, field

from skellycam.core.camera_group.camera_group import CameraGroup

from freemocap.core.pipeline.pipeline_configs import PipelineConfig
from freemocap.core.pipeline.processing_pipeline import ProcessingPipeline, FrontendPayload
from freemocap.core.pubsub.pubsub_topics import AggregationNodeOutputMessage
from freemocap.core.types.type_overloads import PipelineIdString, FrameNumberInt

import logging
logger = logging.getLogger(__name__)

@dataclass
class PipelineManager:
    global_kill_flag: multiprocessing.Value
    pipelines: dict[PipelineIdString, ProcessingPipeline] = field(default_factory=dict)

    def create_pipeline(self,
                        pipeline_config:PipelineConfig ) -> ProcessingPipeline:
        pipeline =  ProcessingPipeline.from_config(pipeline_config=pipeline_config,
                                                    global_kill_flag=self.global_kill_flag)
        pipeline.start()
        self.pipelines[pipeline.id] = pipeline
        logger.info(f"Created pipeline with ID: {pipeline.id} for camera group ID: {pipeline.camera_group_id}")
        return pipeline

    def close_all_pipelines(self):
        for pipeline in self.pipelines.values():
            pipeline.shutdown()
        self.pipelines.clear()
        logger.info("All pipelines closed successfully")

    def get_latest_frontend_payloads(self, if_newer_than:int) -> dict[PipelineIdString,  tuple[bytes | None, FrontendPayload | None]]:
        latest_outputs = {}
        for pipeline_id, pipeline in self.pipelines.items():
            output = pipeline.get_latest_frontend_payload(if_newer_than=if_newer_than)
            if not output is None:
                latest_outputs[pipeline_id] = output
        return latest_outputs