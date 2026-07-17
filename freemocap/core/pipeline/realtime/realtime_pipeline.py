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
import uuid
from dataclasses import dataclass
from queue import Empty

from pydantic import BaseModel, ConfigDict
from freemocap.core.tracking.tracker_definitions import RTMPOSE_WHOLEBODY_DEFINITION
from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.types.type_overloads import CameraIdString, CameraGroupIdString

from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.realtime.camera_node import CameraNode
from freemocap.core.pipeline.realtime.realtime_aggregator_node import RealtimeAggregatorNode
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.pipeline.realtime.charuco_recorder_node import CharucoRecorderNode
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
    SkeletonFitterResetTopic,
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
    skeleton_inference_node: RealtimeSkeletonInferenceNode | None
    charuco_recorder_node: CharucoRecorderNode | None
    aggregation_output_subscription: TopicSubscriptionQueue
    result_ready_event: multiprocessing.synchronize.Event
    result_consumed_event: multiprocessing.synchronize.Event
    ipc: PipelineIPC
    pubsub: PubSubTopicManager
    worker_registry: WorkerRegistry
    started: bool = False
    # Config stashed while a calibration recording temporarily forces Charuco-only
    # mode (skeleton inference paused). None whenever not in that mode.
    _pre_calibration_config: RealtimePipelineConfig | None = None

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
        if self.charuco_recorder_node is not None:
            nodes_alive = nodes_alive and self.charuco_recorder_node.is_alive
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
            realtime_camera_ids: list[CameraIdString] | None = None,
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

        # Use the realtime subset if provided, otherwise all cameras in the group.
        # The camera group is always started with all selected cameras so their
        # shared memory exists; we just choose which ones feed the pipeline nodes.
        pipeline_camera_ids: list[CameraIdString] = (
            [cid for cid in camera_group.configs.keys() if cid in realtime_camera_ids]
            if realtime_camera_ids is not None
            else list(camera_group.configs.keys())
        )

        camera_nodes = {
            camera_id: CameraNode.create(
                camera_id=camera_id,
                worker_registry=camera_registry,
                camera_shm_dto=camera_group.shm.to_dto().camera_shm_dtos[camera_id],
                config=pipeline_config.camera_node_config,
                ipc=ipc,
                pubsub=pubsub,
                skeleton_inference_centralized=(
                    pipeline_config.use_centralized_gpu_inference
                    and pipeline_config.camera_node_config.detector_type != "mediapipe"
                ),
                log_pipeline_times=pipeline_config.log_pipeline_times,
            )
            for camera_id in pipeline_camera_ids
        }

        skeleton_inference_node: RealtimeSkeletonInferenceNode | None = None
        if (pipeline_config.use_centralized_gpu_inference
                and pipeline_config.camera_node_config.skeleton_tracking_enabled
                and pipeline_config.camera_node_config.detector_type != "mediapipe"):
            skeleton_inference_node = RealtimeSkeletonInferenceNode.create(
                camera_group_id=camera_group.id,
                camera_ids=pipeline_camera_ids,
                worker_registry=worker_registry,
                camera_group_shm_dto=camera_group.shm.to_dto(),
                config=pipeline_config,
                ipc=ipc,
                pubsub=pubsub,
            )

        # Create CharucoRecorderNode if charuco tracking is enabled.
        # This node buffers observations during calibration recording windows
        # so posthoc calibration can skip redundant detection.
        charuco_recorder_node: CharucoRecorderNode | None = None
        if pipeline_config.camera_node_config.charuco_tracking_enabled:
            charuco_recorder_node = CharucoRecorderNode.create(
                camera_ids=pipeline_camera_ids,
                ipc=ipc,
                pubsub=pubsub,
                board_config=pipeline_config.camera_node_config.charuco_tracker_config.stages[0].keypoint_detectors[0].board,
                worker_registry=worker_registry,
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

        skeleton_fitter_reset_sub = pubsub.get_subscription(
            SkeletonFitterResetTopic,
        )

        aggregation_node = RealtimeAggregatorNode.create(
            camera_group_id=camera_group.id,
            camera_ids=pipeline_camera_ids,
            worker_registry=worker_registry,
            camera_group_shm_dto=camera_group.shm.to_dto(),
            config=pipeline_config,
            ipc=ipc,
            pubsub=pubsub,
            result_ready_event=result_ready_event,
            result_consumed_event=result_consumed_event,
            skeleton_fitter_reset_sub=skeleton_fitter_reset_sub,
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
            charuco_recorder_node=charuco_recorder_node,
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

        if self.charuco_recorder_node is not None:
            self.charuco_recorder_node.start()
            logger.info(f"CharucoRecorderNode started for pipeline [{self.id}]")

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
        if self.charuco_recorder_node is not None:
            self.charuco_recorder_node.worker._intentionally_terminated = True

        # Shut down worker threads BEFORE closing pubsub queues.
        # On Windows, closing a multiprocessing.Queue while a thread is
        # reading from it (even get_nowait) can hang on the underlying
        # pipe handle. Shutting nodes down first gives them a chance to
        # exit their loops (ipc.should_continue is already False).
        for node in self.camera_nodes.values():
            if node.is_alive:
                node.shutdown()
        if self.skeleton_inference_node is not None and self.skeleton_inference_node.is_alive:
            self.skeleton_inference_node.shutdown()
        if self.charuco_recorder_node is not None and self.charuco_recorder_node.is_alive:
            self.charuco_recorder_node.shutdown()
        if self.aggregation_node.is_alive:
            self.aggregation_node.shutdown()

        self.pubsub.close()
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

    def enter_calibration_charuco_only_mode(self) -> None:
        """Pause skeleton inference for the duration of a calibration recording.

        Skeleton inference is the realtime throughput bottleneck; with it off the
        pipeline keeps up with (ideally) every recorded frame, so the
        CharucoRecorderNode can cache far more observations for posthoc calibration
        to reuse. Restored by ``exit_calibration_charuco_only_mode``. No-op if
        skeleton tracking is already off. Best-effort: posthoc re-detects any frame
        the cache lacks, so coverage only affects speed, never correctness.
        """
        if self._pre_calibration_config is not None:
            return  # already in Charuco-only mode
        if not self.config.camera_node_config.skeleton_tracking_enabled:
            return  # nothing to pause

        self._pre_calibration_config = self.config
        # model_copy(update=...) builds new instances rather than mutating, so this
        # is safe regardless of whether the config models are frozen, and leaves the
        # stashed pre-calibration config untouched for restore.
        charuco_only_camera_config = self.config.camera_node_config.model_copy(
            update={"skeleton_tracking_enabled": False},
        )
        charuco_only_config = self.config.model_copy(
            update={"camera_node_config": charuco_only_camera_config},
        )
        logger.info(
            f"RealtimePipeline [{self.id}]: entering Charuco-only mode for "
            f"calibration recording (skeleton inference paused)"
        )
        self.update_config(charuco_only_config)

    def exit_calibration_charuco_only_mode(self) -> None:
        """Restore the config saved by ``enter_calibration_charuco_only_mode``,
        re-enabling skeleton inference. No-op if not currently in Charuco-only mode.
        """
        if self._pre_calibration_config is None:
            return
        logger.info(
            f"RealtimePipeline [{self.id}]: exiting Charuco-only mode — "
            f"restoring skeleton inference"
        )
        restored_config = self._pre_calibration_config
        self._pre_calibration_config = None
        self.update_config(restored_config)

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

    def get_latest_frontend_payload(
        self,
        if_newer_than: FrameNumberInt,
        display_image_sizes: dict[str, dict[str, float]] | None = None,
    ) -> FrontendImagePacket | None:
        if not self.alive:
            if self.camera_group.alive:
                result = self.camera_group.get_latest_frontend_payload(
                    if_newer_than=if_newer_than,
                    display_image_sizes=display_image_sizes,
                )
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
        while True:
            try:
                aggregation_output = self.aggregation_output_subscription.get_nowait()
            except Empty:
                break

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
            display_image_sizes=display_image_sizes,
        )
        if payload is not None:
            frames_bytearray, mf_timestamp = payload
            detector_type = aggregation_output.pipeline_config.camera_node_config.detector_type
            if detector_type == "mediapipe":
                # Mediapipe keypoint names differ from RTMPose; embed them directly in the
                # block so the frontend can render whatever was triangulated without needing
                # the RTMPose schema. The SKELETON_3D rigidifier block is omitted since the
                # rigidifier expects RTMPose wholebody point names.
                keypoints_binary_payload = build_keypoints_payload(
                    frame_number=aggregation_output.frame_number,
                    tracker_id="mediapipe",
                    point_names=list(aggregation_output.keypoints_arrays.keys()),
                    keypoints_arrays=aggregation_output.keypoints_arrays,
                    skeleton_arrays=None,
                    embed_keypoint_names=True,
                )
            else:
                keypoints_binary_payload = build_keypoints_payload(
                    frame_number=aggregation_output.frame_number,
                    tracker_id=RTMPOSE_WHOLEBODY_DEFINITION.name,
                    point_names=RTMPOSE_WHOLEBODY_DEFINITION.tracked_points,
                    keypoints_arrays=aggregation_output.keypoints_arrays,
                    skeleton_arrays=aggregation_output.skeleton,
                )
            return FrontendImagePacket(
                images_bytearray=frames_bytearray,
                multiframe_timestamp=mf_timestamp,
                frontend_payload=FrontendPayload.from_aggregation_output(aggregation_output),
                keypoints_binary_payload=keypoints_binary_payload,
            )
        return None
