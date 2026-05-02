"""
RealtimePipeline: a long-lived pipeline attached to a CameraGroup.

Runs indefinitely, processing live camera frames through detection and
(optionally) triangulation. Behavior changes dynamically via config updates
published through the pubsub system.

Calibration or Kinematic reconstructions-specific orchestration (start/stop recording, triggering posthoc
calibration) is NOT here — it belongs in the PipelineManager or route handlers.
"""
import asyncio
import logging
import multiprocessing
import multiprocessing.synchronize
import os
import uuid
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict
from skellytracker.trackers.rtmpose_tracker.names_and_connections import RTMPOSE_WHOLEBODY_DEFINITION
from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.types.type_overloads import CameraIdString, CameraGroupIdString

from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.realtime.camera_node import CameraNode
from freemocap.core.pipeline.realtime.realtime_aggregator_node import RealtimeAggregatorNode
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.pipeline.realtime.realtime_skeleton_inference_node import (
    RealtimeSkeletonInferenceNode,
)
from freemocap.core.types.type_overloads import PipelineIdString, TopicSubscriptionQueue, FrameNumberInt
from freemocap.core.viz.frontend_keypoints_serializer import build_keypoints_payload
from freemocap.core.viz.frontend_payload import FrontendPayload, FrontendImagePacket
from freemocap.pubsub.pubsub_manager import PubSubTopicManager
from freemocap.pubsub.pubsub_topics import (
    AggregationNodeOutputTopic,
    AggregationNodeOutputMessage,
    PipelineConfigUpdateMessage,
    PipelineConfigUpdateTopic,
)

logger = logging.getLogger(__name__)


# Step 1 of the JSON→binary keypoints refactor is gated behind this env var so
# the JSON path stays the default until both ends are validated end-to-end.
# Set FREEMOCAP_BINARY_KEYPOINTS=1 to enable.
_BINARY_KEYPOINTS_ENABLED: bool = os.environ.get("FREEMOCAP_BINARY_KEYPOINTS", "0") == "1"


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
    skeleton_inference_node: RealtimeSkeletonInferenceNode | None
    aggregation_output_subscription: TopicSubscriptionQueue
    result_ready_event: multiprocessing.synchronize.Event
    result_consumed_event: multiprocessing.synchronize.Event
    ipc: PipelineIPC
    pubsub: PubSubTopicManager
    worker_registry: WorkerRegistry
    started: bool = False

    @property
    def alive(self) -> bool:
        if not self.started:
            return False
        nodes_alive = (
                all(node.is_alive for node in self.camera_nodes.values())
                and self.aggregation_node.is_alive
        )
        if self.skeleton_inference_node is not None:
            nodes_alive = nodes_alive and self.skeleton_inference_node.is_alive
        return nodes_alive

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

        camera_registry = worker_registry
        if pipeline_config.camera_node_config.worker_mode == WorkerMode.THREAD:
            camera_registry = WorkerRegistry(
                global_kill_flag=global_kill_flag,
                worker_mode=WorkerMode.THREAD,
            )

        camera_nodes = {
            camera_id: CameraNode.create(
                camera_id=camera_id,
                worker_registry=camera_registry,
                camera_shm_dto=camera_group.shm.to_dto().camera_shm_dtos[camera_id],
                config=pipeline_config.camera_node_config,
                ipc=ipc,
                pubsub=pubsub,
                skeleton_inference_centralized=pipeline_config.use_centralized_gpu_inference,
                log_pipeline_times=pipeline_config.log_pipeline_times,
            )
            for camera_id in camera_group.configs.keys()
        }

        skeleton_inference_node: RealtimeSkeletonInferenceNode | None = None
        if (pipeline_config.use_centralized_gpu_inference
                and pipeline_config.camera_node_config.skeleton_tracking_enabled):
            skeleton_inference_node = RealtimeSkeletonInferenceNode.create(
                camera_group_id=camera_group.id,
                camera_ids=camera_group.camera_ids,
                worker_registry=worker_registry,
                camera_group_shm_dto=camera_group.shm.to_dto(),
                config=pipeline_config,
                ipc=ipc,
                pubsub=pubsub,
            )

        # Backpressure events between the aggregator and the websocket consumer.
        # The aggregator processes one frame, publishes the result, clears
        # `result_consumed_event`, and sets `result_ready_event`. The consumer
        # waits on `result_ready_event`, grabs the result, then flips the events
        # in the opposite order — releasing the aggregator to start the next
        # frame. Initial state: nothing is ready, but the slot is "consumed"
        # (free), so the aggregator can produce its first frame immediately.
        result_ready_event = multiprocessing.Event()
        result_consumed_event = multiprocessing.Event()
        result_consumed_event.set()

        aggregation_node = RealtimeAggregatorNode.create(
            camera_group_id=camera_group.id,
            camera_ids=camera_group.camera_ids,
            worker_registry=worker_registry,
            camera_group_shm_dto=camera_group.shm.to_dto(),
            config=pipeline_config,
            ipc=ipc,
            pubsub=pubsub,
            result_ready_event=result_ready_event,
            result_consumed_event=result_consumed_event,
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
            skeleton_inference_node=skeleton_inference_node,
            aggregation_output_subscription=aggregation_output_subscription,
            result_ready_event=result_ready_event,
            result_consumed_event=result_consumed_event,
            ipc=ipc,
            pubsub=pubsub,
            worker_registry=worker_registry,
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

        # Start the centralized GPU inference node before camera nodes so its
        # session (including any TRT engine compilation) is ready by the time
        # the first frame request lands. First-run TRT compile can take 1–3
        # minutes; subsequent runs are cache-hits.
        if self.skeleton_inference_node is not None:
            logger.info(
                f"Starting centralized SkeletonInferenceNode for pipeline [{self.id}] — "
                f"first run may pause for ~1-3 minutes while TensorRT compiles engines."
            )
            self.skeleton_inference_node.start()

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
        if self.skeleton_inference_node is not None:
            self.skeleton_inference_node.worker._intentionally_terminated = True

        self.pubsub.close()
        for node in self.camera_nodes.values():
            if node.is_alive:
                node.shutdown()
        if self.skeleton_inference_node is not None and self.skeleton_inference_node.is_alive:
            self.skeleton_inference_node.shutdown()
        if self.aggregation_node.is_alive:
            self.aggregation_node.shutdown()
        logger.debug(f"RealtimePipeline [{self.id}] shut down")

    def update_config(self, new_config: RealtimePipelineConfig) -> None:
        """Push a config update to all pipeline workers via pubsub.

        Also manages SkeletonInferenceNode lifecycle when skeleton_tracking_enabled
        transitions between True and False.
        """
        old_skeleton = self.config.camera_node_config.skeleton_tracking_enabled
        new_skeleton = new_config.camera_node_config.skeleton_tracking_enabled

        self.config = new_config
        logger.trace(f"Pushing new config to realtime pipeline: {self.id} \n {new_config.model_dump_json(indent=4)}")
        self.pubsub.publish(
            topic_type=PipelineConfigUpdateTopic,
            message=PipelineConfigUpdateMessage(pipeline_config=new_config),
        )

        if old_skeleton and not new_skeleton:
            # Skeleton tracking disabled: shut down the centralized inference node.
            if self.skeleton_inference_node is not None and self.skeleton_inference_node.is_alive:
                logger.info(f"RealtimePipeline [{self.id}]: skeleton tracking disabled — shutting down SkeletonInferenceNode")
                self.skeleton_inference_node.shutdown()
            self.skeleton_inference_node = None

        elif not old_skeleton and new_skeleton and new_config.use_centralized_gpu_inference:
            # Skeleton tracking re-enabled: create and start a fresh inference node.
            logger.info(
                f"Starting centralized SkeletonInferenceNode for pipeline [{self.id}] — "
                f"first run may pause for ~1-3 minutes while TensorRT compiles engines."
            )
            self.skeleton_inference_node = RealtimeSkeletonInferenceNode.create(
                camera_group_id=self.camera_group.id,
                camera_ids=self.camera_group.camera_ids,
                worker_registry=self.worker_registry,
                camera_group_shm_dto=self.camera_group.shm.to_dto(),
                config=new_config,
                ipc=self.ipc,
                pubsub=self.pubsub,
            )
            self.skeleton_inference_node.start()

    async def update_camera_configs(self, camera_configs: CameraConfigs) -> CameraConfigs:
        return await self.camera_group.update_camera_settings(
            requested_configs=camera_configs,
        )

    async def wait_for_result_ready(self, timeout: float) -> bool:
        """Block (off the event loop) until the aggregator has a result ready.

        Returns True if a result became available within `timeout`, False on
        timeout. Used by the websocket relay to avoid spinning on a polling
        loop while the aggregator is processing the next frame.
        """
        return await asyncio.to_thread(self.result_ready_event.wait, timeout)

    def get_latest_frontend_payload(self, if_newer_than: FrameNumberInt, ) -> FrontendImagePacket | None:
        if not self.alive:
            if self.camera_group.alive:
                result = self.camera_group.get_latest_frontend_payload(if_newer_than=if_newer_than)
                if result is not None:
                    frame_number, mf_timestamp, frames_bytearray = result
                    return FrontendImagePacket(
                        images_bytearray=frames_bytearray,
                        multiframe_timestamp=mf_timestamp,

                        frontend_payload=FrontendPayload(
                            frame_number=frame_number,
                            camera_group_id=self.camera_group.id,
                        ),
                    )
            return None

        aggregation_output: AggregationNodeOutputMessage | None = None
        while not self.aggregation_output_subscription.empty():
            aggregation_output = self.aggregation_output_subscription.get()

        if aggregation_output is None:
            return None

        # Flip the backpressure events: clear "ready" (we just took it) and
        # set "consumed" (the aggregator can now process the next frame).
        # The aggregator should already be idling on the consumed-gate, so
        # this signal is what kicks off the next pass — in parallel with
        # the websocket sending this packet to the frontend.
        self.result_ready_event.clear()
        self.result_consumed_event.set()

        payload = self.camera_group.get_frontend_payload_by_frame_number(
            frame_number=aggregation_output.frame_number,
        )
        if payload is not None:
            frames_bytearray, mf_timestamp = payload
            keypoints_bytearray: bytearray | None = None
            if _BINARY_KEYPOINTS_ENABLED:
                keypoints_bytearray = build_keypoints_payload(
                    frame_number=aggregation_output.frame_number,
                    tracker_id=RTMPOSE_WHOLEBODY_DEFINITION.name,
                    point_names=RTMPOSE_WHOLEBODY_DEFINITION.tracked_points,
                    keypoints_raw_arrays=aggregation_output.keypoints_raw_arrays,
                    keypoints_filtered_arrays=aggregation_output.keypoints_filtered_arrays,
                )
            return FrontendImagePacket(
                images_bytearray=frames_bytearray,
                multiframe_timestamp=mf_timestamp,
                frontend_payload=FrontendPayload.from_aggregation_output(aggregation_output),
                keypoints_bytearray=keypoints_bytearray,
            )
        return None
