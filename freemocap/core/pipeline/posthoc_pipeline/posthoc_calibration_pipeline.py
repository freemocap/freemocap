import logging
import multiprocessing
import uuid
from abc import ABC
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, ConfigDict

from freemocap.core.pipeline.pipeline_configs import PipelineConfig, PipelineTaskConfigABC, CalibrationTaskConfig
from freemocap.core.pipeline.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.posthoc_pipeline.posthoc_aggregation_node import PosthocCalibrationAggregationNode
from freemocap.core.pipeline.posthoc_pipeline.video_node.video_group import VideoGroup
from freemocap.core.pipeline.posthoc_pipeline.video_node.calibration_video_node import VideoNodeState, CalibrationVideoNode
from freemocap.core.pipeline.realtime_pipeline.realtime_aggregation_node import AggregationNode, \
    RealtimeAggregationNodeState
from freemocap.core.types.type_overloads import PipelineIdString, TopicSubscriptionQueue
from freemocap.pubsub.pubsub_topics import AggregationNodeOutputTopic

from skellycam.core.recorders.videos.recording_info import RecordingInfo
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

class PosthocCalibrationProcessingPipeline(BaseModel):
    id: PipelineIdString
    recording_info:RecordingInfo
    task_config: PipelineTaskConfigABC
    video_nodes: dict[VideoIdString, CalibrationVideoNode]
    aggregation_node: AggregationNode
    video_node_subscriptions: dict[VideoIdString, TopicSubscriptionQueue]
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
    def from_task_config(cls,
                    recording_info:RecordingInfo,
                    heartbeat_timestamp: multiprocessing.Value,
                    subprocess_registry: list[multiprocessing.Process],
                    calibration_task_config: CalibrationTaskConfig,
                    global_kill_flag: multiprocessing.Value,
                    ):
        #validate with video_group object
        video_group = VideoGroup.from_recording_path(recording_path=recording_info.full_recording_path)
        pipeline_id = str(uuid.uuid4())[:6]
        ipc = PipelineIPC.create(global_kill_flag=global_kill_flag,
                                 heartbeat_timestamp=heartbeat_timestamp
                                 )
        video_nodes = {video_id: CalibrationVideoNode.create(video_path=video_helper.video_path,  #recreate in node worker
                                                             subprocess_registry=subprocess_registry,
                                                             calibration_task_config=calibration_task_config,
                                                             ipc=ipc)
                       for video_id, video_helper in video_group.videos.items()}
        aggregation_node = PosthocCalibrationAggregationNode.create(subprocess_registry=subprocess_registry,
                                                                    calibration_task_config=calibration_task_config,
                                                                    video_metadata=video_group.video_metadata_by_id,
                                                                    ipc=ipc,
                                                                    recording_info=recording_info,
                                                                    pipeline_id=pipeline_id
                                                                    )
        video_group.close()  # close here, videos reopened in video nodes
        return cls(video_nodes=video_nodes,
                   aggregation_node=aggregation_node,
                   ipc=ipc,
                   task_config=task_config,
                   aggregation_node_subscription=ipc.pubsub.topics[
                       AggregationNodeOutputTopic].get_subscription(),
                   id=str(uuid.uuid4())[:6],
                   )

    def start(self) -> None:
        self.started = True
        logger.debug(f"Starting Pipeline (id:{self.id} with  for recording: {self.recording_info.recording_name}")
        try:
            logger.debug("Starting video nodes...")
            [node.start() for node in self.video_nodes.values()]
        except Exception as e:
            logger.error(f"Failed to start video nodes: {type(e).__name__} - {e}")
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


        logger.info(f"All pipeline workers started successfully")

    def shutdown(self):
        logger.debug(f"Shutting down {self.__class__.__name__}...")

        self.ipc.shutdown_pipeline()
        for video_id, video_node in self.video_nodes.items():
            video_node.shutdown()
        self.aggregation_node.shutdown()
