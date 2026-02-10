"""
RealtimeAggregationNode: collects per-camera observations for each frame,
optionally triangulates (if calibration is valid), and publishes aggregated output.

Uses CalibrationStateTracker for graceful degradation: if triangulation fails,
the calibration is invalidated and we continue publishing 2D-only data until
a new calibration is loaded (triggered by a config update after posthoc
calibration completes).
"""
import logging
import multiprocessing
from dataclasses import dataclass

from skellycam.core.ipc.shared_memory.camera_group_shared_memory import (
    CameraGroupSharedMemory,
    CameraGroupSharedMemoryDTO,
)
from skellycam.core.types.type_overloads import CameraGroupIdString, CameraIdString, TopicSubscriptionQueue
from skellycam.utilities.wait_functions import wait_1ms

from freemocap.core.pipeline.shared.calibration_state import CalibrationStateTracker
from freemocap.core.pipeline.shared.pipeline_configs import RealtimePipelineConfig
from freemocap.core.pipeline.shared.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.shared.base_node import BaseNode
from freemocap.pubsub.pubsub_topics import (
    CameraNodeOutputMessage,
    CameraNodeOutputTopic,
    PipelineConfigUpdateTopic,
    ProcessFrameNumberTopic,
    ProcessFrameNumberMessage,
    AggregationNodeOutputMessage,
    AggregationNodeOutputTopic,
    PipelineConfigUpdateMessage,
    ShouldCalibrateTopic,
)
from skellycam.core.ipc.process_management.process_registry import ProcessRegistry

logger = logging.getLogger(__name__)


@dataclass
class RealtimeAggregationNode(BaseNode):

    @classmethod
    def create(
        cls,
        *,
        config: RealtimePipelineConfig,
        camera_group_id: CameraGroupIdString,
        process_registry: ProcessRegistry,
        camera_group_shm_dto: CameraGroupSharedMemoryDTO,
        ipc: PipelineIPC,
    ) -> "RealtimeAggregationNode":
        shutdown_self_flag, worker = cls._create_worker(
            target=cls._run,
            name=f"CameraGroup-{camera_group_id}-AggregationNode",
            process_registry=process_registry,
            log_queue=ipc.ws_queue,
            kwargs=dict(
                config=config,
                camera_group_id=camera_group_id,
                ipc=ipc,
                camera_group_shm_dto=camera_group_shm_dto,
                camera_node_subscription=ipc.pubsub.topics[
                    CameraNodeOutputTopic
                ].get_subscription(),
                pipeline_config_subscription=ipc.pubsub.topics[
                    PipelineConfigUpdateTopic
                ].get_subscription(),
                should_calibrate_subscription=ipc.pubsub.topics[
                    ShouldCalibrateTopic
                ].get_subscription(),
            ),
        )
        return cls(
            shutdown_self_flag=shutdown_self_flag,
            worker=worker,
        )

    @staticmethod
    def _run(
        *,
        config: RealtimePipelineConfig,
        camera_group_id: CameraGroupIdString,
        ipc: PipelineIPC,
        shutdown_self_flag: multiprocessing.Value,
        camera_group_shm_dto: CameraGroupSharedMemoryDTO,
        camera_node_subscription: TopicSubscriptionQueue,
        pipeline_config_subscription: TopicSubscriptionQueue,
        should_calibrate_subscription: TopicSubscriptionQueue,
    ) -> None:
        logger.debug(f"RealtimeAggregationNode [{camera_group_id}] initializing")

        camera_group_shm = CameraGroupSharedMemory.recreate(
            shm_dto=camera_group_shm_dto,
            read_only=True,
        )
        calibration = CalibrationStateTracker.create_and_try_load()
        if calibration.is_valid:
            logger.info(
                f"RealtimeAggregationNode [{camera_group_id}] loaded calibration "
                f"from {calibration.calibration_path}"
            )
        else:
            logger.info(
                f"RealtimeAggregationNode [{camera_group_id}] starting without "
                f"calibration — triangulation disabled"
            )

        camera_node_outputs: dict[CameraIdString, CameraNodeOutputMessage | None] = {
            cam_id: None for cam_id in config.camera_configs.keys()
        }
        latest_requested_frame: int = -1
        last_received_frame: int = -1

        try:
            logger.debug(f"RealtimeAggregationNode [{camera_group_id}] entering main loop")
            while ipc.should_continue and not shutdown_self_flag.value:
                wait_1ms()

                # ---- Handle config updates (also triggers calibration reload) ----
                while not pipeline_config_subscription.empty():
                    msg: PipelineConfigUpdateMessage = pipeline_config_subscription.get()
                    config = msg.pipeline_config
                    logger.info(
                        f"RealtimeAggregationNode [{camera_group_id}] received config update"
                    )
                    # On config update, try reloading calibration
                    # (a posthoc calibration may have written a new toml)
                    if calibration.reload():
                        logger.info(
                            f"RealtimeAggregationNode [{camera_group_id}] "
                            f"reloaded calibration from {calibration.calibration_path}"
                        )

                # ---- Handle explicit calibration signals ----
                while not should_calibrate_subscription.empty():
                    should_calibrate_subscription.get()  # consume
                    if calibration.reload():
                        logger.info(
                            f"RealtimeAggregationNode [{camera_group_id}] "
                            f"reloaded calibration after ShouldCalibrate signal"
                        )

                # ---- Request new frames if ready ----
                if (camera_group_shm.latest_multiframe_number > latest_requested_frame
                        and last_received_frame >= latest_requested_frame):
                    ipc.pubsub.topics[ProcessFrameNumberTopic].publish(
                        ProcessFrameNumberMessage(
                            frame_number=camera_group_shm.latest_multiframe_number,
                        ),
                    )
                    latest_requested_frame = camera_group_shm.latest_multiframe_number

                # ---- Collect camera node outputs ----
                if camera_node_subscription.empty():
                    continue

                cam_output: CameraNodeOutputMessage = camera_node_subscription.get()
                if cam_output.camera_id not in config.camera_configs:
                    raise ValueError(
                        f"Camera ID {cam_output.camera_id} not in "
                        f"camera IDs {list(config.camera_configs.keys())}"
                    )
                camera_node_outputs[cam_output.camera_id] = cam_output

                # ---- Check if all cameras reported for this frame ----
                if not all(
                    isinstance(v, CameraNodeOutputMessage)
                    for v in camera_node_outputs.values()
                ):
                    continue

                # Warn on frame number mismatches (don't hard-fail for realtime)
                frame_numbers = [
                    msg.frame_number
                    for msg in camera_node_outputs.values()
                    if isinstance(msg, CameraNodeOutputMessage)
                ]
                if len(set(frame_numbers)) > 1:
                    logger.warning(
                        f"Frame number mismatch across cameras: {frame_numbers} "
                        f"(expected {latest_requested_frame})"
                    )

                last_received_frame = latest_requested_frame

                # ---- Triangulate if calibration is valid ----
                tracked_points3d: dict = {}
                if calibration.is_valid:
                    triangulated = calibration.try_triangulate(
                        frame_number=latest_requested_frame,
                        frame_observations_by_camera={
                            cam_id: output.observation
                            for cam_id, output in camera_node_outputs.items()
                            if isinstance(output, CameraNodeOutputMessage)
                        },
                    )
                    if triangulated is not None:
                        tracked_points3d = triangulated
                    # If triangulated is None, calibration was invalidated.
                    # We continue publishing 2D-only data.

                # ---- Publish aggregated output ----
                ipc.pubsub.topics[AggregationNodeOutputTopic].publish(
                    AggregationNodeOutputMessage(
                        frame_number=latest_requested_frame,
                        pipeline_id=ipc.pipeline_id,
                        camera_group_id=camera_group_id,
                        pipeline_config=config,
                        camera_node_outputs=camera_node_outputs,
                        tracked_points3d=tracked_points3d,
                    ),
                )

                # Reset for next frame
                camera_node_outputs = {cam_id: None for cam_id in config.camera_configs.keys()}

        except Exception as e:
            logger.error(
                f"Exception in RealtimeAggregationNode [{camera_group_id}]: {e}",
                exc_info=True,
            )
            ipc.kill_everything()
            raise
        finally:
            logger.debug(f"RealtimeAggregationNode [{camera_group_id}] exiting")