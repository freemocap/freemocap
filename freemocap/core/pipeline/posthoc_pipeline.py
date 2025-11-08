import logging
import multiprocessing
import time
import uuid
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.recorders.videos.recording_info import RecordingInfo

from freemocap.core.pipeline.frontend_payload import FrontendPayload
from freemocap.core.pipeline.nodes.aggregation_node import AggregationNode, AggregationNodeState
from freemocap.core.pipeline.nodes.video_node.video_group import VideoGroup
from freemocap.core.pipeline.nodes.video_node.video_node import VideoNode, VideoNodeState
from freemocap.core.pipeline.pipeline_configs import PipelineConfig, CalibrationTaskConfig
from freemocap.core.pipeline.pipeline_ipc import PipelineIPC
from freemocap.core.types.type_overloads import PipelineIdString, TopicSubscriptionQueue, FrameNumberInt
from freemocap.pubsub.pubsub_topics import AggregationNodeOutputTopic, AggregationNodeOutputMessage, \
    PipelineConfigUpdateMessage, \
    PipelineConfigUpdateTopic, ShouldCalibrateMessage, ShouldCalibrateTopic

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
    aggregation_node_state: AggregationNodeState
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
        video_group = VideoGroup.from_recording_path(recording_path=recording_folder_path)
        ipc = PipelineIPC.create(global_kill_flag=global_kill_flag,
                                 heartbeat_timestamp=heartbeat_timestamp
                                 )
        video_nodes = {video_id: VideoNode.create(video_id=video_id,
                                                  subprocess_registry=subprocess_registry,
                                                  config=pipeline_config,
                                                  ipc=ipc)
                       for video_id, config in video_group.configs.items()}
        aggregation_node = AggregationNode.create(video_group_id=video_group.id,
                                                  subprocess_registry=subprocess_registry,
                                                  config=pipeline_config,
                                                  ipc=ipc,
                                                  )

        return cls(video_nodes=video_nodes,
                   aggregation_node=aggregation_node,
                   ipc=ipc,
                   config=pipeline_config,
                   aggregation_node_subscription=ipc.pubsub.topics[
                       AggregationNodeOutputTopic].get_subscription(),
                   video_group=video_group,
                   id=str(uuid.uuid4())[:6],
                   )

    def start(self) -> None:
        self.started = True
        logger.debug(
            f"Starting Pipeline (id:{self.id} with video group (id:{self.video_group_id} for video ids: {list(self.video_nodes.keys())}...")
        if not self.video_group.started:
            try:
                logger.debug("Starting video group...")
                self.video_group.start()
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

    async def update_video_configs(self, video_configs: VideoConfigs) -> VideoConfigs:
        return await self.video_group.update_video_settings(requested_configs=video_configs)

    def get_latest_frontend_payload(self, if_newer_than: FrameNumberInt) -> tuple[bytes, FrontendPayload | None] | None:
        if not self.alive:
            if self.video_group.alive:
                _, _, frames_bytearray = self.video_group.get_latest_frontend_payload(if_newer_than=if_newer_than)
                if frames_bytearray is not None:
                    return (frames_bytearray,
                            None)
            return None
        aggregation_output: AggregationNodeOutputMessage | None = None
        while not self.aggregation_node_subscription.empty():
            aggregation_output = self.aggregation_node_subscription.get()
        if aggregation_output is None:
            return None
        frames_bytearray = self.video_group.get_frontend_payload_by_frame_number(
            frame_number=aggregation_output.frame_number,
        )

        return (frames_bytearray,
                FrontendPayload.from_aggregation_output(aggregation_output=aggregation_output))

    def update_pipeline_config(self, new_config: PipelineConfig) -> None:
        self.config = new_config
        self.ipc.pubsub.topics[PipelineConfigUpdateTopic].publish(
            PipelineConfigUpdateMessage(pipeline_config=self.config)
        )

    def start_calibration_recording(self, recording_info: RecordingInfo, config: CalibrationTaskConfig):
        # TODO - I don't love this method of getting the config and path here, wanna fix it later
        config.calibration_recording_folder = recording_info.full_recording_path
        logger.info(
            f"Starting calibration recording: {recording_info.full_recording_path} with config: {config.model_dump_json(indent=2)}")
        self.config.calibration_task_config = config
        self.ipc.pubsub.topics[PipelineConfigUpdateTopic].publish(
            PipelineConfigUpdateMessage(pipeline_config=self.config))
        self.video_group.start_recording(recording_info=recording_info)
        logger.info("Calibration recording started.")

    def stop_calibration_recording(self):
        logger.info("Stopping calibration recording...")
        # TODO - I don't love this method of getting the config and path here, wanna fix it later
        self.video_group.stop_recording()
        time.sleep(1)  # give it a sec to wrap up
        logger.info(
            f"Calibration recording stopped - sending calibration start message - config: {self.config.calibration_task_config.model_dump_json(indent=2)}")
        self.ipc.pubsub.topics[ShouldCalibrateTopic].publish(ShouldCalibrateMessage())
