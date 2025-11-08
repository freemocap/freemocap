"""
Updated aggregation node implementation using the new base abstractions.
"""
import logging
import multiprocessing
import threading
from typing import Any, ClassVar

from pydantic import Field
import numpy as np
from skellycam.core.ipc.pubsub.pubsub_topics import SetShmMessage, SetShmTopic
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemory
from skellycam.core.types.type_overloads import CameraIdString, CameraGroupIdString
from skellycam.utilities.wait_functions import wait_1ms

from freemocap.core.pipeline.base_node_abcs import ProcessNodeABC, ProcessNodeParams
from freemocap.core.pipeline.og.pipeline_configs import PipelineConfig, CalibrationTaskConfig, MocapTaskConfig
from freemocap.core.pipeline.og.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.pipeline_launch_configs import AggregationNodeParams
from freemocap.core.tasks.calibration_task.shared_view_accumulator import SharedViewAccumulator
from freemocap.core.tasks.calibration_task.v1_capture_volume_calibration.charuco_stuff.charuco_board_definition import (
    CharucoBoardDefinition,
)
from freemocap.core.tasks.calibration_task.v1_capture_volume_calibration.run_anipose_capture_volume_calibration import (
    run_anipose_capture_volume_calibration,
)
from freemocap.core.types.type_overloads import Point3d, TopicSubscriptionQueue
from freemocap.pubsub.pubsub_abcs import PubSubTopicABC
from freemocap.pubsub.pubsub_manager import PubSubTopicManager
from freemocap.pubsub.pubsub_topics import (
    AggregationNodeOutputMessage,
    AggregationNodeOutputTopic,
    CameraNodeOutputMessage,
    CameraNodeOutputTopic,
    PipelineConfigUpdateMessage,
    PipelineConfigUpdateTopic,
    ProcessFrameNumberMessage,
    ProcessFrameNumberTopic,
    ShouldCalibrateMessage,
    ShouldCalibrateTopic,
)

logger = logging.getLogger(__name__)



class AggregationNodeParams(ProcessNodeParams):
    """Parameters for aggregation node (used by both realtime and posthoc)."""

    # Declare subscription requirements
    subscribed_topics: ClassVar[list[type[PubSubTopicABC]]] = [
        CameraNodeOutputTopic,
        PipelineConfigUpdateTopic,
        ShouldCalibrateTopic,
    ]
    published_topics: ClassVar[list[type[PubSubTopicABC]]] = [
        ProcessFrameNumberTopic,
        AggregationNodeOutputTopic,
    ]

    camera_group_id: CameraGroupIdString
    camera_ids: list[CameraIdString]
    calibration_task_config: CalibrationTaskConfig = Field(default_factory=CalibrationTaskConfig)
    mocap_task_config: MocapTaskConfig = Field(default_factory=MocapTaskConfig)


class AggregationNode(ProcessNodeABC):
    """
    Aggregation node using new base abstractions.
    Collects outputs from camera nodes and produces aggregated results.
    """

    @classmethod
    def create(
            cls,
            *,
            node_id: str,
            params: AggregationNodeParams,
            subscriptions: dict[type[PubSubTopicABC], TopicSubscriptionQueue],
            pubsub: PubSubTopicManager,
            subprocess_registry: list[multiprocessing.Process],
            pipeline_config: PipelineConfig,
            ipc: PipelineIPC,
            **kwargs: Any
    ) -> "AggregationNode":
        """
        Create aggregation node with pre-allocated subscriptions.

        CRITICAL: Called from parent process with pre-created subscriptions!
        """
        shutdown_flag = multiprocessing.Value('b', False)

        # Verify we have the required subscriptions
        required_topics = params.get_subscription_requirements()
        for topic in required_topics:
            if topic not in subscriptions:
                raise ValueError(f"Missing required subscription for {topic.__name__}")

        # Also need SHM subscription (special case)
        if SetShmTopic not in subscriptions:
            subscriptions[SetShmTopic] = ipc.shm_topic.get_subscription()

        # Create worker process with all pre-allocated resources
        worker = multiprocessing.Process(
            target=cls._run,
            name=f"AggregationNode-{params.camera_group_id}",
            kwargs=dict(
                node_id=node_id,
                params=params,
                subscriptions=subscriptions,
                pubsub=pubsub,
                shutdown_flag=shutdown_flag,
                pipeline_config=pipeline_config,
                ipc=ipc,
            ),
            daemon=True,
        )

        subprocess_registry.append(worker)

        return cls(
            node_id=node_id,
            params=params,
            subscriptions=subscriptions,
            pubsub=pubsub,
            shutdown_flag=shutdown_flag,
            worker=worker,
        )

    @staticmethod
    def _run(
            *,
            node_id: str,
            params: AggregationNodeParams,
            subscriptions: dict[type[PubSubTopicABC], TopicSubscriptionQueue],
            pubsub: PubSubTopicManager,
            shutdown_flag: multiprocessing.Value,
            pipeline_config: PipelineConfig,
            ipc: PipelineIPC,
            **kwargs: Any
    ) -> None:
        """
        Main process loop for aggregation node.
        Runs in child process with pre-allocated subscriptions.
        """
        # Configure logging for child process
        if multiprocessing.parent_process():
            from freemocap.system.logging_configuration.configure_logging import configure_logging
            from freemocap import LOG_LEVEL
            configure_logging(LOG_LEVEL, ws_queue=ipc.ws_queue)

        logger.debug(f"Starting aggregation node {node_id} for camera group {params.camera_group_id}")

        # Get pre-allocated subscriptions
        camera_output_sub = subscriptions[CameraNodeOutputTopic]
        config_update_sub = subscriptions[PipelineConfigUpdateTopic]
        should_calibrate_sub = subscriptions[ShouldCalibrateTopic]
        shm_sub = subscriptions.get(SetShmTopic)

        # Wait for shared memory setup
        logger.debug("Waiting for SHM message...")
        shm_message: SetShmMessage = shm_sub.get(block=True)
        logger.debug("Received SHM message")

        # Initialize shared memory
        camera_group_shm = CameraGroupSharedMemory.recreate(
            shm_dto=shm_message.camera_group_shm_dto,
            read_only=True
        )

        # Initialize state
        current_config = pipeline_config
        camera_outputs: dict[CameraIdString, CameraNodeOutputMessage | None] = {
            camera_id: None for camera_id in params.camera_ids
        }
        shared_view_accumulator = SharedViewAccumulator.create(camera_ids=params.camera_ids)
        calibrate_thread: threading.Thread | None = None
        calibrate_kill_event = threading.Event()

        latest_requested_frame = -1
        last_received_frame = -1

        try:
            while ipc.should_continue and not shutdown_flag.value:
                wait_1ms()

                # Check for config updates
                while not config_update_sub.empty():
                    msg: PipelineConfigUpdateMessage = config_update_sub.get()
                    current_config = msg.pipeline_config
                    logger.info(f"Aggregation node received config update")

                # Request new frame if available
                if (camera_group_shm.latest_multiframe_number > latest_requested_frame
                        and last_received_frame >= latest_requested_frame):
                    latest_requested_frame = camera_group_shm.latest_multiframe_number
                    pubsub.publish(
                        topic_type=ProcessFrameNumberTopic,
                        message=ProcessFrameNumberMessage(frame_number=latest_requested_frame)
                    )

                # Collect camera outputs
                while not camera_output_sub.empty():
                    camera_msg: CameraNodeOutputMessage = camera_output_sub.get()

                    if camera_msg.camera_id not in params.camera_ids:
                        logger.warning(f"Unexpected camera ID: {camera_msg.camera_id}")
                        continue

                    camera_outputs[camera_msg.camera_id] = camera_msg

                # Check if we have all camera outputs for this frame
                if all(output is not None for output in camera_outputs.values()):
                    # Verify frame numbers match
                    frame_numbers = [output.frame_number for output in camera_outputs.values()]
                    if not all(fn == latest_requested_frame for fn in frame_numbers):
                        logger.warning(
                            f"Frame number mismatch: expected {latest_requested_frame}, "
                            f"got {frame_numbers}"
                        )

                    last_received_frame = latest_requested_frame

                    # Update shared view accumulator
                    if any(node.charuco_observation and node.charuco_observation.charuco_board_visible
                           for node in camera_outputs.values()):
                        shared_view_accumulator.receive_camera_node_output(
                            camera_node_output_by_camera=camera_outputs,
                            multi_frame_number=latest_requested_frame
                        )

                    # Create aggregated output
                    aggregation_output = AggregationNodeOutputMessage(
                        frame_number=latest_requested_frame,
                        pipeline_id=ipc.pipeline_id,
                        camera_group_id=params.camera_group_id,
                        pipeline_config=current_config,
                        camera_node_outputs=camera_outputs,
                        tracked_points3d={
                            'fake_point': Point3d(
                                x=np.sin(last_received_frame),
                                y=np.cos(last_received_frame),
                                z=np.cos(last_received_frame)
                            )
                        }  # Placeholder for actual aggregation
                    )

                    # Publish aggregated output
                    pubsub.publish(
                        topic_type=AggregationNodeOutputTopic,
                        message=aggregation_output
                    )

                    logger.trace(f"Published aggregation for frame {latest_requested_frame}")

                    # Reset for next frame
                    camera_outputs = {camera_id: None for camera_id in params.camera_ids}

                # Check for calibration request
                if not should_calibrate_sub.empty():
                    calibrate_msg = should_calibrate_sub.get()
                    if isinstance(calibrate_msg, ShouldCalibrateMessage) and calibrate_thread is None:
                        logger.info(f"Starting calibration for camera group {params.camera_group_id}")

                        # Stop existing thread if running
                        if calibrate_thread is not None and calibrate_thread.is_alive():
                            calibrate_kill_event.set()
                            calibrate_thread.join(timeout=5)
                            if calibrate_thread.is_alive():
                                raise RuntimeError("Failed to stop calibration thread")

                        calibrate_kill_event.clear()

                        # Start new calibration thread
                        calibrate_thread = threading.Thread(
                            target=run_anipose_capture_volume_calibration,
                            name=f"Calibration-{params.camera_group_id}",
                            kwargs=dict(
                                charuco_board_definition=CharucoBoardDefinition(
                                    name=f"charuco_{params.camera_group_id}",
                                    number_of_squares_width=current_config.calibration_task_config.charuco_board_x_squares,
                                    number_of_squares_height=current_config.calibration_task_config.charuco_board_y_squares,
                                ),
                                charuco_square_size=current_config.calibration_task_config.charuco_square_length,
                                kill_event=calibrate_kill_event,
                                calibration_recording_folder=current_config.calibration_task_config.calibration_recording_folder,
                                use_charuco_as_groundplane=True,
                            )
                        )
                        calibrate_thread.start()

        except Exception as e:
            logger.error(f"Error in aggregation node {node_id}: {e}", exc_info=True)
            ipc.kill_everything()
            raise

        finally:
            # Clean up calibration thread if running
            if calibrate_thread is not None and calibrate_thread.is_alive():
                calibrate_kill_event.set()
                calibrate_thread.join(timeout=2.0)

            logger.debug(f"Shutting down aggregation node {node_id}")