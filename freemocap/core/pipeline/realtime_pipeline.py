import logging
import multiprocessing
import time
import uuid
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict
from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraIdString, CameraGroupIdString

from freemocap.core.pipeline.nodes.aggregation_node import AggregationNode, AggregationNodeState
from freemocap.core.pipeline.nodes.camera_node import CameraNode, CameraNodeState
from freemocap.core.pipeline.frontend_payload import FrontendPayload
from freemocap.core.pipeline.pipeline_configs import PipelineConfig, CalibrationTaskConfig
from freemocap.core.pipeline.pipeline_ipc import PipelineIPC
from freemocap.core.types.type_overloads import PipelineIdString, TopicSubscriptionQueue, FrameNumberInt
from freemocap.pubsub.pubsub_topics import AggregationNodeOutputTopic, AggregationNodeOutputMessage, \
    PipelineConfigUpdateMessage, \
    PipelineConfigUpdateTopic, ShouldCalibrateMessage, ShouldCalibrateTopic

logger = logging.getLogger(__name__)


class RealtimePipelineState(BaseModel):
    """Serializable representation of a processing pipeline state."""
    model_config = ConfigDict(
        validate_assignment=True,
        frozen=True
    )
    id: PipelineIdString
    camera_group_id: CameraGroupIdString
    camera_node_states: dict[CameraIdString, CameraNodeState]
    aggregation_node_state: AggregationNodeState
    alive: bool




@dataclass
class RealtimeProcessingPipeline:
    id: PipelineIdString
    camera_group: CameraGroup
    config: PipelineConfig
    camera_nodes: dict[CameraIdString, CameraNode]
    aggregation_node: AggregationNode
    aggregation_node_subscription: TopicSubscriptionQueue
    ipc: PipelineIPC
    started: bool = False

    @property
    def alive(self) -> bool:
        return all([camera_node.worker.is_alive() for camera_node in
                    self.camera_nodes.values()]) and self.aggregation_node.worker.is_alive()

    @property
    def camera_group_id(self) -> CameraGroupIdString:
        return self.camera_group.id

    @property
    def camera_ids(self) -> list[CameraIdString]:
        return list(self.camera_nodes.keys())

    @property
    def camera_configs(self) -> CameraConfigs:
        return self.camera_group.configs

    @classmethod
    def from_config(cls,
                    camera_group: CameraGroup,
                    heartbeat_timestamp: multiprocessing.Value,
                    subprocess_registry: list[multiprocessing.Process],
                    pipeline_config: PipelineConfig,
                    ):

        ipc = PipelineIPC.create(global_kill_flag=camera_group.ipc.global_kill_flag,
                                 shm_topic=camera_group.ipc.pubsub.topics[TopicTypes.SHM_UPDATES],
                                 heartbeat_timestamp=heartbeat_timestamp
        )
        camera_nodes = {camera_id: CameraNode.create(camera_id=camera_id,
                                                     subprocess_registry=subprocess_registry,
                                                     camera_shm_dto=camera_group.shm.to_dto().camera_shm_dtos[camera_id],
                                                     config=pipeline_config,
                                                     ipc=ipc)
                        for camera_id, config in camera_group.configs.items()}
        aggregation_node = AggregationNode.create(camera_group_id=camera_group.id,
                                                  subprocess_registry=subprocess_registry,
                                                  config=pipeline_config,
                                                  ipc=ipc,
                                                  )

        return cls(camera_nodes=camera_nodes,
                   aggregation_node=aggregation_node,
                   ipc=ipc,
                   config=pipeline_config,
                   aggregation_node_subscription=ipc.pubsub.topics[
                       AggregationNodeOutputTopic].get_subscription(),
                   camera_group=camera_group,
                   id=str(uuid.uuid4())[:6],
                   )

    def start(self) -> None:
        self.started = True
        logger.debug(
            f"Starting Pipeline (id:{self.id} with camera group (id:{self.camera_group_id} for camera ids: {list(self.camera_nodes.keys())}...")
        if not self.camera_group.started:
            try:
                logger.debug("Starting camera group...")
                self.camera_group.start()
            except Exception as e:
                logger.error(f"Failed to start camera group: {type(e).__name__} - {e}")
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

        for camera_id, camera_node in self.camera_nodes.items():
            try:
                logger.debug(f"Starting camera node {camera_id}...")
                camera_node.start()
                logger.debug(f"Camera node {camera_id} worker started: alive={camera_node.worker.is_alive()}")
            except Exception as e:
                logger.error(f"Failed to start camera node {camera_id}: {type(e).__name__} - {e}")
                logger.exception(e)
                raise

        logger.info(f"All pipeline workers started successfully")

    def shutdown(self):
        logger.debug(f"Shutting down {self.__class__.__name__}...")

        self.ipc.shutdown_pipeline()
        for camera_id, camera_node in self.camera_nodes.items():
            camera_node.shutdown()
        self.aggregation_node.shutdown()
        self.camera_group.close()

    async def update_camera_configs(self, camera_configs: CameraConfigs) -> CameraConfigs:
        return await self.camera_group.update_camera_settings(requested_configs=camera_configs)

    def get_latest_frontend_payload(self, if_newer_than: FrameNumberInt) -> tuple[bytes, FrontendPayload | None] | None:
        if not self.alive:
            if self.camera_group.alive:
                _, _, frames_bytearray = self.camera_group.get_latest_frontend_payload(if_newer_than=if_newer_than)
                if frames_bytearray is not None:
                    return (frames_bytearray,
                            None)
            return None
        aggregation_output: AggregationNodeOutputMessage | None = None
        while not self.aggregation_node_subscription.empty():
            aggregation_output = self.aggregation_node_subscription.get()
        if aggregation_output is None:
            return None
        frames_bytearray = self.camera_group.get_frontend_payload_by_frame_number(
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
        logger.info(f"Starting calibration recording: {recording_info.full_recording_path} with config: {config.model_dump_json(indent=2)}")
        self.config.calibration_task_config = config
        self.ipc.pubsub.topics[PipelineConfigUpdateTopic].publish(
            PipelineConfigUpdateMessage(pipeline_config=self.config))
        self.camera_group.start_recording(recording_info=recording_info)
        logger.info("Calibration recording started.")

    def stop_calibration_recording(self):
        logger.info("Stopping calibration recording...")
        # TODO - I don't love this method of getting the config and path here, wanna fix it later
        self.camera_group.stop_recording()
        time.sleep(1)  # give it a sec to wrap up
        logger.info(f"Calibration recording stopped - sending calibration start message - config: {self.config.calibration_task_config.model_dump_json(indent=2)}")
        self.ipc.pubsub.topics[ShouldCalibrateTopic].publish(ShouldCalibrateMessage())
