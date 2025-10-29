import multiprocessing
from dataclasses import dataclass, field

from skellycam.core.camera_group.camera_group import CameraGroup

from freemocap.core.pipeline.pipeline_configs import PipelineConfig
from freemocap.core.pipeline.processing_pipeline import ProcessingPipeline
from freemocap.core.pubsub.pubsub_topics import AggregationNodeOutputMessage
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

    def get_latest_output(self) -> dict[PipelineIdString,  AggregationNodeOutputMessage]:
        latest_outputs = {}
        for pipeline_id, pipeline in self.pipelines.items():
            aggregation_node_message: AggregationNodeOutputMessage|None = None
            while not pipeline.aggregation_node_subscription.empty():
                aggregation_node_message = pipeline.aggregation_node_subscription.get_nowait()
            if aggregation_node_message is None:
                continue
            latest_outputs[pipeline_id] = aggregation_node_message
        return latest_outputs