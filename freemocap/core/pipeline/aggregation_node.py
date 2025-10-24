import logging
import multiprocessing
from dataclasses import dataclass

import numpy as np
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryDTO, \
    CameraGroupSharedMemory
from skellycam.core.types.type_overloads import CameraGroupIdString, CameraIdString, TopicSubscriptionQueue
from skellycam.utilities.wait_functions import wait_1ms

from freemocap.core.pipeline.pipeline_configs import AggregationNodeConfig
from freemocap.core.pipeline.pipeline_ipc import PipelineIPC
from freemocap.core.pubsub.pubsub_topics import CameraNodeOutputMessage, PipelineConfigTopic, ProcessFrameNumberTopic, \
    ProcessFrameNumberMessage, AggregationNodeOutputMessage, AggregationNodeOutputTopic, CameraNodeOutputTopic
from freemocap.core.types.type_overloads import Point3d

logger = logging.getLogger(__name__)


@dataclass
class AggregationNode:
    shutdown_self_flag: multiprocessing.Value
    worker: multiprocessing.Process

    @classmethod
    def create(cls,
               config: AggregationNodeConfig,
               camera_group_id: CameraGroupIdString,
               camera_group_shm_dto: CameraGroupSharedMemoryDTO,
               ipc: PipelineIPC):
        shutdown_self_flag = multiprocessing.Value('b', False)
        return cls(shutdown_self_flag=shutdown_self_flag,
                   worker=multiprocessing.Process(target=cls._run,
                                                  name=f"CameraGroup-{camera_group_id}-AggregationNode",
                                                  kwargs=dict(config=config,
                                                              camera_group_id=camera_group_id,
                                                              ipc=ipc,
                                                              shutdown_self_flag=shutdown_self_flag,
                                                              camera_node_subscription=ipc.pubsub.topics[
                                                                  CameraNodeOutputTopic].get_subscription(),
                                                              pipeline_config_subscription=ipc.pubsub.topics[
                                                                  PipelineConfigTopic].get_subscription(),
                                                              camera_group_shm_dto=camera_group_shm_dto,
                                                              ),
                                                  daemon=True
                                                  ),
                   )

    @staticmethod
    def _run(config: AggregationNodeConfig,
             camera_group_id: CameraGroupIdString,
             ipc: PipelineIPC,
             shutdown_self_flag: multiprocessing.Value,
             camera_node_subscription: TopicSubscriptionQueue,
             pipeline_config_subscription: TopicSubscriptionQueue,
             camera_group_shm_dto: CameraGroupSharedMemoryDTO
             ):
        if multiprocessing.parent_process():
            # Configure logging if multiprocessing (i.e. if there is a parent process)
            from freemocap.system.logging_configuration.configure_logging import configure_logging
            from freemocap import LOG_LEVEL
            configure_logging(LOG_LEVEL, ws_queue=ipc.ws_queue)
        logger.debug(f"Starting aggregation process for camera group {camera_group_id}")
        camera_node_outputs: dict[CameraIdString, CameraNodeOutputMessage | None] = {camera_id: None for camera_id in
                                                                                     config.camera_configs.keys()}
        camera_group_shm = CameraGroupSharedMemory.recreate(shm_dto=camera_group_shm_dto,
                                                                   read_only=True)
        latest_requested_frame: int = -1
        last_received_frame: int = -1
        while ipc.should_continue and not shutdown_self_flag.value:
            wait_1ms()
            if camera_group_shm.latest_multiframe_number > latest_requested_frame and last_received_frame >= latest_requested_frame:
                logger.info(f'Requesting frame {camera_group_shm.latest_multiframe_number} for aggregation')
                ipc.pubsub.topics[ProcessFrameNumberTopic].publish(
                    ProcessFrameNumberMessage(frame_number=camera_group_shm.latest_multiframe_number))
                latest_requested_frame = camera_group_shm.latest_multiframe_number
            # Check for Camera Node Output
            if not camera_node_subscription.empty():
                camera_node_output_message: CameraNodeOutputMessage = camera_node_subscription.get()
                logger.info(
                    f"AggregationNode received CameraNodeOutputMessage for frame {camera_node_output_message.frame_number} from camera {camera_node_output_message.camera_id}")
                # Process the camera node output and aggregate it
                camera_id = camera_node_output_message.camera_id
                if not camera_id in config.camera_configs.keys():
                    raise ValueError(
                        f"Camera ID {camera_id} not in camera IDs {list(config.camera_configs.keys())}")
                camera_node_outputs[camera_id] = camera_node_output_message

            # Check if ready to process a frame output
            if not any([camera_node_output_message is None for camera_node_output_message in
                        camera_node_outputs.values()]):
                # All cameras have observations for this tracker and the frame number is greater than or equal to the latest requested frame
                if not all([camera_node_output_message.frame_number == latest_requested_frame for
                            camera_node_output_message in camera_node_outputs.values()]):
                    raise ValueError(
                        f"Frame numbers from tracker results do not match expected ({latest_requested_frame}) - got {[camera_node_output_message.frame_number for camera_node_output_message in camera_node_outputs.values()]}")
                last_received_frame = latest_requested_frame
                aggregation_output: AggregationNodeOutputMessage = AggregationNodeOutputMessage(
                    frame_number=latest_requested_frame,
                    camera_group_id=camera_group_id,
                    tracked_points3d={'fake_point': Point3d(x=np.sin(last_received_frame),
                                                            y=np.cos(last_received_frame),
                                                            z=np.cos(last_received_frame)
                                                            )}  # Placeholder for actual aggregation logic
                )
                ipc.pubsub.topics[AggregationNodeOutputTopic].publish(aggregation_output)
                camera_node_outputs = {camera_id: None for camera_id in camera_node_outputs.keys()}
                logger.debug(
                    f"Published aggregation output for frame {latest_requested_frame} with points3d: {aggregation_output.tracked_points3d.keys()}")

    def start(self):
        logger.debug(f"Starting AggregationNode worker")
        self.worker.start()

    def shutdown(self):
        logger.debug(f"Stopping AggregationNode worker")
        self.shutdown_self_flag.value = True
        self.worker.join()


