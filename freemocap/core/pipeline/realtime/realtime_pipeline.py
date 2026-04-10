"""
RealtimePipeline: a long-lived pipeline attached to a CameraGroup.

Runs indefinitely, processing live camera frames through detection and
(optionally) triangulation. Behavior changes dynamically via config updates
published through the pubsub system.

Calibration or Kinematic reconstructions-specific orchestration (start/stop recording, triggering posthoc
calibration) is NOT here — it belongs in the PipelineManager or route handlers.
"""
import logging
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict
from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.types.type_overloads import CameraIdString, CameraGroupIdString

from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.realtime.camera_node import CameraNode
from freemocap.core.pipeline.realtime.realtime_aggregator_node import RealtimeAggregatorNode
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.types.type_overloads import PipelineIdString, TopicSubscriptionQueue, FrameNumberInt
from freemocap.core.viz.frontend_payload import FrontendPayload, FrontendImagePacket
from freemocap.pubsub.pubsub_manager import PubSubTopicManager
from freemocap.pubsub.pubsub_topics import (
    AggregationNodeOutputTopic,
    AggregationNodeOutputMessage,
    PipelineConfigUpdateMessage,
    PipelineConfigUpdateTopic,
)

logger = logging.getLogger(__name__)


class RealtimePipelineState(BaseModel):
    """Serializable snapshot of pipeline state (for API responses)."""
    model_config = ConfigDict(validate_assignment=True, frozen=True)
    id: PipelineIdString
    camera_group_id: CameraGroupIdString
    alive: bool
    calibration_loaded: bool


@dataclass
class RealtimePipeline:
    id: PipelineIdString
    camera_group: CameraGroup
    config: RealtimePipelineConfig
    camera_nodes: dict[CameraIdString, CameraNode]
    aggregation_node: RealtimeAggregatorNode
    aggregation_output_subscription: TopicSubscriptionQueue
    ipc: PipelineIPC
    pubsub: PubSubTopicManager
    started: bool = False

    @property
    def alive(self) -> bool:
        if not self.started:
            return False
        return (
                all(node.is_alive for node in self.camera_nodes.values())
                and self.aggregation_node.is_alive
        )

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
    def create(
            cls,
            *,
            camera_group: CameraGroup,
            worker_registry: WorkerRegistry,
            pipeline_config: RealtimePipelineConfig,
    ) -> "RealtimePipeline":
        global_kill_flag = camera_group.ipc.global_kill_flag

        ipc = PipelineIPC.create(
            global_kill_flag=global_kill_flag,
            heartbeat_timestamp=worker_registry.heartbeat_timestamp,
        )
        pubsub = PubSubTopicManager.create(
            global_kill_flag=global_kill_flag,
        )

        camera_nodes = {
            camera_id: CameraNode.create(
                camera_id=camera_id,
                worker_registry=worker_registry,
                camera_shm_dto=camera_group.shm.to_dto().camera_shm_dtos[camera_id],
                config=pipeline_config.camera_node_config,
                ipc=ipc,
                pubsub=pubsub,
            )
            for camera_id in camera_group.configs.keys()
        }

        aggregation_node = RealtimeAggregatorNode.create(
            camera_group_id=camera_group.id,
            worker_registry=worker_registry,
            camera_group_shm_dto=camera_group.shm.to_dto(),
            config=pipeline_config,
            ipc=ipc,
            pubsub=pubsub,
        )

        aggregation_output_subscription = pubsub.get_subscription(
            AggregationNodeOutputTopic,
        )

        return cls(
            id=str(uuid.uuid4())[:6],
            camera_group=camera_group,
            config=pipeline_config,
            camera_nodes=camera_nodes,
            aggregation_node=aggregation_node,
            aggregation_output_subscription=aggregation_output_subscription,
            ipc=ipc,
            pubsub=pubsub,
        )

    def start(self) -> None:
        if self.started:
            raise RuntimeError(f"RealtimePipeline {self.id} already started")
        self.started = True

        logger.info(
            f"Starting RealtimePipeline [{self.id}] for camera group "
            f"[{self.camera_group_id}] with cameras {self.camera_ids}"
        )

        if not self.camera_group.started:
            logger.debug("Starting camera group...")
            self.camera_group.start()

        self.aggregation_node.start()

        for camera_id, node in self.camera_nodes.items():
            node.start()

        logger.info(f"RealtimePipeline [{self.id}] — all workers started")

    def shutdown(self) -> None:
        logger.debug(f"Shutting down RealtimePipeline [{self.id}]")
        self.ipc.shutdown_pipeline()

        # Mark all workers as intentionally terminated BEFORE they die
        # so the WorkerRegistry child monitor doesn't trigger a cascade kill
        for node in self.camera_nodes.values():
            node.worker._intentionally_terminated = True
        self.aggregation_node.worker._intentionally_terminated = True

        self.pubsub.close()
        for node in self.camera_nodes.values():
            if node.is_alive:
                node.shutdown()
        if self.aggregation_node.is_alive:
            self.aggregation_node.shutdown()
        logger.debug(f"RealtimePipeline [{self.id}] shut down")

    def update_config(self, new_config: RealtimePipelineConfig) -> None:
        """Push a config update to all pipeline workers via pubsub."""
        self.config = new_config
        logger.trace(f"Pushing new config to realtime pipeline: {self.id} \n {new_config.model_dump_json(indent=4)}")
        self.pubsub.publish(
            topic_type=PipelineConfigUpdateTopic,
            message=PipelineConfigUpdateMessage(pipeline_config=new_config),
        )

    async def update_camera_configs(self, camera_configs: CameraConfigs) -> CameraConfigs:
        return await self.camera_group.update_camera_settings(
            requested_configs=camera_configs,
        )

    def get_latest_frontend_payload(self, if_newer_than: FrameNumberInt, ) -> FrontendImagePacket | None:
        if not self.alive:
            if self.camera_group.alive:
                result = self.camera_group.get_latest_frontend_payload(if_newer_than=if_newer_than)
                if result is not None:
                    frame_number, _ts, frames_bytes = result
                    return FrontendImagePacket(
                        image_bytes=frames_bytes,
                        frame_number=frame_number,
                        frontend_payload=None,
                    )
            return None

        aggregation_output: AggregationNodeOutputMessage | None = None
        while not self.aggregation_output_subscription.empty():
            aggregation_output = self.aggregation_output_subscription.get()

        if aggregation_output is None:
            return None

        frames_bytes = self.camera_group.get_frontend_payload_by_frame_number(
            frame_number=aggregation_output.frame_number,
        )
        return FrontendImagePacket(
            image_bytes=frames_bytes,
            frame_number=aggregation_output.frame_number,
            frontend_payload=FrontendPayload.from_aggregation_output(aggregation_output),
        )
        aggregation_output: AggregationNodeOutputMessage | None = None
        while not self.aggregation_output_subscription.empty():
            aggregation_output = self.aggregation_output_subscription.get()

        if aggregation_output is None:
            return None, None

        frames_bytes = self.camera_group.get_frontend_payload_by_frame_number(
            frame_number=aggregation_output.frame_number,
        )

        return (
            frames_bytes,
            FrontendPayload.from_aggregation_output(aggregation_output=aggregation_output),
        )
