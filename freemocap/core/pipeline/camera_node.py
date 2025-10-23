import multiprocessing
from dataclasses import dataclass

import numpy as np
from skellycam.core.ipc.shared_memory.camera_shared_memory_ring_buffer import CameraSharedMemoryRingBuffer
from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import SharedMemoryRingBufferDTO
from skellycam.core.types.type_overloads import CameraIdString, WorkerType, TopicSubscriptionQueue
from skellycam.utilities.wait_functions import wait_1ms

from freemocap.core.pipeline.pipeline_configs import CameraNodeConfig
from freemocap.core.pipeline.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.tasks.calibration_task.calibration_pipeline_task import CalibrationCameraNodeTask
from freemocap.core.pubsub.pubsub_topics import ProcessFrameNumberTopic, PipelineConfigTopic, CameraNodeOutputTopic, \
    PipelineConfigMessage, ProcessFrameNumberMessage, CameraNodeOutputMessage

logger = multiprocessing.get_logger()


@dataclass
class CameraNode:
    camera_id: CameraIdString
    shutdown_self_flag: multiprocessing.Value
    worker: WorkerType

    @classmethod
    def create(cls,
               camera_id: CameraIdString,
               config:CameraNodeConfig,
               camera_shm_dto: SharedMemoryRingBufferDTO,
               ipc: PipelineIPC):
        shutdown_self_flag = multiprocessing.Value('b', False)
        return cls(camera_id=camera_id,
                   shutdown_self_flag=shutdown_self_flag,
                   worker=multiprocessing.Process(target=cls._run,
                                                name=f"CameraProcessingNode-{camera_id}",
                                                kwargs=dict(camera_id=camera_id,
                                                            camera_shm_dto=camera_shm_dto,
                                                            ipc=ipc,
                                                            camera_node_config=config,
                                                            shutdown_self_flag=shutdown_self_flag,
                                                            process_frame_number_subscription=ipc.pubsub.get_subscription(
                                                                ProcessFrameNumberTopic),
                                                            pipeline_config_subscription=ipc.pubsub.get_subscription(
                                                                PipelineConfigTopic),
                                                            ),
                                                daemon=True
                                                ),
                   )

    @staticmethod
    def _run(camera_id: CameraIdString,
             camera_shm_dto: SharedMemoryRingBufferDTO,
             ipc: PipelineIPC,
             camera_node_config: CameraNodeConfig,
             process_frame_number_subscription: TopicSubscriptionQueue,
             pipeline_config_subscription: TopicSubscriptionQueue,
             shutdown_self_flag: multiprocessing.Value,
             ):
        if multiprocessing.parent_process():
            # Configure logging if multiprocessing (i.e. if there is a parent process)
            from freemocap.system.logging_configuration.configure_logging import configure_logging
            from freemocap import LOG_LEVEL
            configure_logging(LOG_LEVEL, ws_queue=ipc.ws_queue)
        logger.trace(f"Starting camera processing node for camera {camera_id}")
        camera_shm = CameraSharedMemoryRingBuffer.recreate(dto=camera_shm_dto,
                                                           read_only=False)

        calibration_task= CalibrationCameraNodeTask.create(config=camera_node_config.calibration_camera_node_config)
        # mocap_task: BaseCameraNodeTask|None = None # TODO - this

        frame_rec_array: np.recarray | None = None
        while ipc.should_continue and not shutdown_self_flag.value:
            wait_1ms()
            # Check trackers config updates
            if not pipeline_config_subscription.empty():
                new_pipeline_config_message: PipelineConfigMessage = pipeline_config_subscription.get()
                logger.debug(f"Received new skelly tracker s for camera {camera_id}: {new_pipeline_config_message}")

                # TODO - this
                camera_node_config = new_pipeline_config_message.pipeline_config.camera_node_configs[camera_node_config.camera_id]
                calibration_task= CalibrationCameraNodeTask.create(config=camera_node_config.calibration_camera_node_config)
                # mocap_task = None  # TODO - this

            # Check for new frame to process
            if not process_frame_number_subscription.empty():
                process_frame_number_message: ProcessFrameNumberMessage = process_frame_number_subscription.get()

                logger.debug(
                    f"Camera {camera_id} received request to process frame number {process_frame_number_message.frame_number}")

                # Process the frame
                frame_rec_array = camera_shm.get_data_by_index(index=process_frame_number_message.frame_number,
                                                               rec_array=frame_rec_array)
                observation = calibration_task.process_image(frame_number=frame_rec_array.frame_metadata.frame_number[0],
                                                    image=frame_rec_array.image[0], )
                if observation is not None:
                    # Publish the observation to the IPC
                    ipc.pubsub.publish(
                        topic_type=CameraNodeOutputTopic,
                        message=CameraNodeOutputMessage(
                            camera_id = frame_rec_array.frame_metadata.camera_config.camera_id[0],
                            frame_number=frame_rec_array.frame_metadata.frame_number[0],
                            tracker_name=calibration_task.__class__.__name__,
                            observation=observation,
                        ),
                    )

    def start(self):
        logger.debug(f"Starting {self.__class__.__name__} for camera {self.camera_id}")
        self.worker.start()

    def stop(self):
        logger.debug(f"Stopping {self.__class__.__name__} for camera {self.camera_id}")
        self.shutdown_self_flag.value = True
        self.worker.join()
