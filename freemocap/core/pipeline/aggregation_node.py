import logging
import multiprocessing
import threading
from dataclasses import dataclass

import numpy as np
from pydantic import BaseModel, ConfigDict
from skellycam.core.ipc.pubsub.pubsub_topics import SetShmMessage
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemory
from skellycam.core.types.type_overloads import CameraGroupIdString, CameraIdString, TopicSubscriptionQueue
from skellycam.utilities.wait_functions import wait_1ms

from freemocap.core.pipeline.pipeline_configs import PipelineConfig
from freemocap.core.pipeline.pipeline_ipc import PipelineIPC
from freemocap.core.tasks.calibration_task.shared_view_accumulator import SharedViewAccumulator
from freemocap.core.tasks.calibration_task.v1_capture_volume_calibration.charuco_stuff.charuco_board_definition import \
    CharucoBoardDefinition
from freemocap.core.tasks.calibration_task.v1_capture_volume_calibration.run_anipose_capture_volume_calibration import \
    run_anipose_capture_volume_calibration
from freemocap.core.types.type_overloads import Point3d, PipelineIdString
from freemocap.pubsub.pubsub_topics import CameraNodeOutputMessage, PipelineConfigUpdateTopic, ProcessFrameNumberTopic, \
    ProcessFrameNumberMessage, AggregationNodeOutputMessage, AggregationNodeOutputTopic, CameraNodeOutputTopic, \
    PipelineConfigUpdateMessage, ShouldCalibrateTopic, ShouldCalibrateMessage

logger = logging.getLogger(__name__)


class AggregationNodeState(BaseModel):
    model_config = ConfigDict(
        validate_assignment=True,
        frozen=True
    )
    pipeline_id: PipelineIdString
    config: PipelineConfig
    alive: bool
    last_seen_frame_number: int | None = None
    calibration_task_state: object | None = None
    mocap_task_state: object = None  # TODO - this


@dataclass
class AggregationNode:
    shutdown_self_flag: multiprocessing.Value
    worker: multiprocessing.Process

    @classmethod
    def create(cls,
               config: PipelineConfig,
               camera_group_id: CameraGroupIdString,
               subprocess_registry: list[multiprocessing.Process],
               ipc: PipelineIPC):
        shutdown_self_flag = multiprocessing.Value('b', False)
        worker = multiprocessing.Process(target=cls._run,
                                         name=f"CameraGroup-{camera_group_id}-AggregationNode",
                                         kwargs=dict(config=config,
                                                     camera_group_id=camera_group_id,
                                                     ipc=ipc,
                                                     shutdown_self_flag=shutdown_self_flag,
                                                     camera_node_subscription=ipc.pubsub.topics[
                                                         CameraNodeOutputTopic].get_subscription(),
                                                     pipeline_config_subscription=ipc.pubsub.topics[
                                                         PipelineConfigUpdateTopic].get_subscription(),
                                                     shm_subscription=ipc.shm_topic.get_subscription(),
                                                     should_calibrate_subscription=ipc.pubsub.topics[
                                                         ShouldCalibrateTopic].get_subscription(),
                                                     ),

                                         daemon=True
                                         )
        subprocess_registry.append(worker)
        return cls(shutdown_self_flag=shutdown_self_flag,
                   worker=worker
                   )

    @staticmethod
    def _run(config: PipelineConfig,
             camera_group_id: CameraGroupIdString,
             ipc: PipelineIPC,
             shutdown_self_flag: multiprocessing.Value,
             camera_node_subscription: TopicSubscriptionQueue,
             pipeline_config_subscription: TopicSubscriptionQueue,
             shm_subscription: TopicSubscriptionQueue,
             should_calibrate_subscription: TopicSubscriptionQueue
             ):
        if multiprocessing.parent_process():
            # Configure logging if multiprocessing (i.e. if there is a parent process)
            from freemocap.system.logging_configuration.configure_logging import configure_logging
            from freemocap import LOG_LEVEL
            configure_logging(LOG_LEVEL, ws_queue=ipc.ws_queue)

        logger.debug("AggregationNode process started - waiting for SHM message")
        shm_message: SetShmMessage = shm_subscription.get(block=True)
        logger.debug("AggregationNode - received SHM message - starting main loop")
        try:
            logger.debug(f"Starting aggregation process for camera group {camera_group_id}")
            camera_node_outputs: dict[CameraIdString, CameraNodeOutputMessage | None] = {camera_id: None for camera_id
                                                                                         in
                                                                                         config.camera_configs.keys()}
            camera_group_shm = CameraGroupSharedMemory.recreate(shm_dto=shm_message.camera_group_shm_dto,
                                                                read_only=True)
            shared_view_accumulator = SharedViewAccumulator.create(camera_ids=config.camera_ids)
            calibrate_recording_thread: threading.Thread | None = None
            calibration_thread_kill_event = threading.Event()
            latest_requested_frame: int = -1
            last_received_frame: int = -1
            while ipc.should_continue and not shutdown_self_flag.value:
                wait_1ms()

                # Check for updated Pipeline Config
                while not pipeline_config_subscription.empty():
                    pipeline_config_message: PipelineConfigUpdateMessage = pipeline_config_subscription.get()
                    config = pipeline_config_message.pipeline_config
                    logger.info(f"AggregationNode for camera group {camera_group_id} received updated config")

                # Check if we should request a new frame to process
                if camera_group_shm.latest_multiframe_number > latest_requested_frame and last_received_frame >= latest_requested_frame:
                    ipc.pubsub.topics[ProcessFrameNumberTopic].publish(
                        ProcessFrameNumberMessage(frame_number=camera_group_shm.latest_multiframe_number))
                    latest_requested_frame = camera_group_shm.latest_multiframe_number

                # Check for Camera Node Output
                if not camera_node_subscription.empty():
                    camera_node_output_message: CameraNodeOutputMessage = camera_node_subscription.get()
                    camera_id = camera_node_output_message.camera_id
                    if not camera_id in config.camera_configs.keys():
                        raise ValueError(
                            f"Camera ID {camera_id} not in camera IDs {list(config.camera_configs.keys())}")
                    camera_node_outputs[camera_id] = camera_node_output_message

                # Check if ready to process a frame output
                if all([isinstance(camera_node_output_message, CameraNodeOutputMessage) for camera_node_output_message
                        in
                        camera_node_outputs.values()]):
                    if not all([camera_node_output_message.frame_number == latest_requested_frame for
                                camera_node_output_message in camera_node_outputs.values()]):
                        logger.warning(
                            f"Frame numbers from tracker results do not match expected ({latest_requested_frame}) - got {[camera_node_output_message.frame_number for camera_node_output_message in camera_node_outputs.values()]}")
                    last_received_frame = latest_requested_frame
                    if any([node.charuco_observation and node.charuco_observation.charuco_board_visible for node in
                            camera_node_outputs.values()]):
                        shared_view_accumulator.receive_camera_node_output(
                            camera_node_output_by_camera=camera_node_outputs,
                            multi_frame_number=latest_requested_frame)
                    aggregation_output: AggregationNodeOutputMessage = AggregationNodeOutputMessage(
                        frame_number=latest_requested_frame,
                        pipeline_id=ipc.pipeline_id,
                        camera_group_id=camera_group_id,
                        pipeline_config=config,
                        camera_node_outputs=camera_node_outputs,
                        tracked_points3d={'fake_point': Point3d(x=np.sin(last_received_frame),
                                                                y=np.cos(last_received_frame),
                                                                z=np.cos(last_received_frame)
                                                                )}  # Placeholder for actual aggregation logic
                    )
                    logger.info(f'Publishing aggregation output for frame {latest_requested_frame} in camera group {camera_group_id}')
                    ipc.pubsub.topics[AggregationNodeOutputTopic].publish(aggregation_output)
                    camera_node_outputs = {camera_id: None for camera_id in camera_node_outputs.keys()}

                if not should_calibrate_subscription.empty():
                    should_calibrate_message = should_calibrate_subscription.get()
                    if isinstance(should_calibrate_message, ShouldCalibrateMessage) and calibrate_recording_thread is None:
                        logger.info(
                            f"Starting calibration recording thread for camera group {camera_group_id} in pipeline {ipc.pipeline_id}")
                        # TODO - Shoehorning v2 models into v1 calibration function - v excited to put v1 in the ground sooooooon
                        if calibrate_recording_thread is not None and calibrate_recording_thread.is_alive():
                            calibration_thread_kill_event.set()
                            calibrate_recording_thread.join(timeout=5)
                            if calibrate_recording_thread.is_alive():
                                raise RuntimeError('Failed to stop existing calibration recording thread....')
                        calibration_thread_kill_event.clear()
                        calibrate_recording_thread = threading.Thread(
                            target=run_anipose_capture_volume_calibration,
                            name=f"CameraGroup-{camera_group_id}-CalibrationRecordingThread",
                            kwargs=dict(
                                charuco_board_definition=CharucoBoardDefinition(
                                    name=f"charuco_{camera_group_id}",
                                    number_of_squares_width=config.calibration_task_config.charuco_board_x_squares,
                                    number_of_squares_height=config.calibration_task_config.charuco_board_y_squares),
                                charuco_square_size=config.calibration_task_config.charuco_square_length,
                                kill_event=calibration_thread_kill_event,
                                calibration_recording_folder=config.calibration_task_config.calibration_recording_folder,
                                use_charuco_as_groundplane=True)
                        )
                        calibrate_recording_thread.start()
        except Exception as e:
            logger.error(f"Exception in AggregationNode for camera group {camera_group_id}: {e}", exc_info=True)
            ipc.kill_everything()
            raise
        finally:
            logger.debug(f"Shutting down aggregation process for camera group {camera_group_id}")

    def start(self):
        logger.debug(f"Starting AggregationNode worker")
        self.worker.start()

    def shutdown(self):
        logger.debug(f"Stopping AggregationNode worker")
        self.shutdown_self_flag.value = True
        self.worker.join()
