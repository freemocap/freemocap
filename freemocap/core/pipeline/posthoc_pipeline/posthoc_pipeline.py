import logging
import multiprocessing
import uuid
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from freemocap.core.pipeline.pipeline_configs import PipelineConfig
from freemocap.core.pipeline.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.posthoc_pipeline.posthoc_aggregation_node import PosthocAggregationNode
from freemocap.core.pipeline.posthoc_pipeline.video_node.video_group import VideoGroup
from freemocap.core.pipeline.posthoc_pipeline.video_node.video_node import VideoNodeState, VideoNode
from freemocap.core.pipeline.realtime_pipeline.realtime_aggregation_node import AggregationNode, \
    RealtimeAggregationNodeState
from freemocap.core.types.type_overloads import PipelineIdString, TopicSubscriptionQueue
from freemocap.pubsub.pubsub_topics import AggregationNodeOutputTopic

VideoIdString = str

logger = logging.getLogger(__name__)


class PosthocPipelineState(BaseModel):
    """Serializable representation of a processing pipeline state."""
    model_config = ConfigDict(
        validate_assignment=True,
        frozen=True
    )
    id: PipelineIdString
    video_node_states: dict[VideoIdString, VideoNodeState]
    aggregation_node_state: RealtimeAggregationNodeState
    alive: bool


@dataclass
class PosthocProcessingPipeline:
    id: PipelineIdString
    config: PipelineConfig
    video_nodes: dict[VideoIdString, VideoNode]
    aggregation_node: AggregationNode
    aggregation_node_subscription: TopicSubscriptionQueue
    ipc: PipelineIPC
    started: bool = False

    @property
    def alive(self) -> bool:
        return all([video_node.worker.is_alive() for video_node in
                    self.video_nodes.values()]) and self.aggregation_node.worker.is_alive()

    @property
    def video_ids(self) -> list[VideoIdString]:
        return list(self.video_nodes.keys())

    @classmethod
    def from_config(cls,
                    recording_folder_path: str,
                    heartbeat_timestamp: multiprocessing.Value,
                    subprocess_registry: list[multiprocessing.Process],
                    pipeline_config: PipelineConfig,
                    global_kill_flag: multiprocessing.Value,
                    ):
        #validate with video_group object
        video_group = VideoGroup.from_recording_path(recording_path=recording_folder_path)

        ipc = PipelineIPC.create(global_kill_flag=global_kill_flag,
                                 heartbeat_timestamp=heartbeat_timestamp
                                 )
        video_nodes = {video_id: VideoNode.create(video_path=video_helper.video_path, #recreate in node worker
                                                  subprocess_registry=subprocess_registry,
                                                  config=pipeline_config,
                                                  ipc=ipc)
                       for video_id, video_helper in video_group.videos.items()}
        video_group.close()  # close here, videos reopened in video nodes
        aggregation_node = PosthocAggregationNode.create(subprocess_registry=subprocess_registry,
                                                         config=pipeline_config,
                                                         ipc=ipc,
                                                         )

        return cls(video_nodes=video_nodes,
                   aggregation_node=aggregation_node,
                   ipc=ipc,
                   config=pipeline_config,
                   aggregation_node_subscription=ipc.pubsub.topics[
                       AggregationNodeOutputTopic].get_subscription(),
                   id=str(uuid.uuid4())[:6],
                   )

    def start(self) -> None:
        self.started = True
        logger.debug(
            f"Starting Pipeline (id:{self.id} with video group (id:{self.video_group_id} for video ids: {list(self.video_nodes.keys())}...")
        try:
            logger.debug("Starting video group...")
            [node.start() for node in self.video_nodes.values()]
        except Exception as e:
            logger.error(f"Failed to start video group: {type(e).__name__} - {e}")
            logger.exception(e)
            raise

        try:
            logger.debug("Starting aggregation node...")
            self.aggregation_node.start()
            logger.debug(f"Aggregation node worker started: alive={self.aggregation_node.worker.is_alive()}")
        except Exception as e:
            logger.error(f"Failed to start aggregation node: {type(e).__name__} - {e}")
            logger.exception(e)
            raise

        for video_id, video_node in self.video_nodes.items():
            try:
                logger.debug(f"Starting video node {video_id}...")
                video_node.start()
                logger.debug(f"Video node {video_id} worker started: alive={video_node.worker.is_alive()}")
            except Exception as e:
                logger.error(f"Failed to start video node {video_id}: {type(e).__name__} - {e}")
                logger.exception(e)
                raise

        logger.info(f"All pipeline workers started successfully")

    def shutdown(self):
        logger.debug(f"Shutting down {self.__class__.__name__}...")

        self.ipc.shutdown_pipeline()
        for video_id, video_node in self.video_nodes.items():
            video_node.shutdown()
        self.aggregation_node.shutdown()
        self.video_group.close()
