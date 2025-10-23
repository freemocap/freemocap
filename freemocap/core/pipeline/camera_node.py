import multiprocessing
from copy import deepcopy
from dataclasses import dataclass

import numpy as np
from skellycam.core.ipc.shared_memory.camera_shared_memory_ring_buffer import CameraSharedMemoryRingBuffer
from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import SharedMemoryRingBufferDTO
from skellycam.core.types.type_overloads import CameraIdString, WorkerType, WorkerStrategy, TopicSubscriptionQueue
from skellycam.utilities.wait_functions import wait_1ms
from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseTracker

from freemocap.core.pipeline.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.processing_pipeline import logger
from freemocap.core.pubsub.pubsub_topics import ProcessFrameNumberTopic, PipelineConfigTopic, CameraNodeOutputTopic, \
    PipelineConfigMessage, LogsTopic, ProcessFrameNumberMessage, CameraNodeOutputMessage


@dataclass
class CameraNode:
    camera_id: CameraIdString
    shutdown_self_flag: multiprocessing.Value
    worker: WorkerType

    @classmethod
    def create(cls,
               camera_id: CameraIdString,
               camera_shm_dto: SharedMemoryRingBufferDTO,
               worker_strategy: WorkerStrategy,
               ipc: PipelineIPC):
        shutdown_self_flag = multiprocessing.Value('b', False)
        return cls(camera_id=camera_id,
                   shutdown_self_flag=shutdown_self_flag,
                   worker=worker_strategy.value(target=cls._run,
                                                name=f"CameraProcessingNode-{camera_id}",
                                                kwargs=dict(camera_id=camera_id,
                                                            camera_shm_dto=camera_shm_dto,
                                                            ipc=ipc,
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
             process_frame_number_subscription: TopicSubscriptionQueue,
             pipeline_config_subscription: TopicSubscriptionQueue,
             shutdown_self_flag: multiprocessing.Value,
             ):
        if multiprocessing.parent_process():
            # Configure logging if multiprocessing (i.e. if there is a parent process)
            from freemocap.system.logging_configuration.configure_logging import configure_logging
            from freemocap import LOG_LEVEL
            configure_logging(LOG_LEVEL, ws_queue=ipc.pubsub.topics[LogsTopic].publication)
        logger.trace(f"Starting camera processing node for camera {camera_id}")
        camera_shm = CameraSharedMemoryRingBuffer.recreate(dto=camera_shm_dto,
                                                           read_only=False)
        trackers: list[BaseTracker] = []
        frame_rec_array: np.recarray | None = None
        while ipc.should_continue and not shutdown_self_flag.value:
            wait_1ms()

            # Check trackers config updates
            if not pipeline_config_subscription.empty():
                new_pipeline_config_message:PipelineConfigMessage = pipeline_config_subscription.get()
                logger.debug(f"Received new skelly tracker s for camera {camera_id}: {new_pipeline_config_message}")

                # TODO - This method of updating trackers is sloppy and won't scale as we add more trackers, should make more sophisticated
                tracker_configs = deepcopy(new_pipeline_config_message.pipeline_config)
                # Create or update the tracker for this camera
                delete_these = []
                for existing_tracker in trackers:
                    for tracker_index, tracker_config in enumerate(tracker_configs):
                        if isinstance(existing_tracker.config, tracker_config):
                            existing_tracker.update_config(tracker_config)
                            delete_these.append(tracker_index)
                # Remove trackers that were updated
                for index in delete_these:
                    del tracker_configs[index]

                for tracker_config in tracker_configs:
                    from skellytracker.trackers.charuco_tracker import CharucoTracker, CharucoTrackerConfig
                    from skellytracker.trackers.mediapipe_tracker import MediapipeTracker, MediapipeTrackerConfig

                    if isinstance(tracker_config, CharucoTrackerConfig):
                        trackers.append(CharucoTracker.create(config=tracker_config))
                    elif isinstance(tracker_config, MediapipeTrackerConfig):
                        trackers.append(MediapipeTracker.create(config=tracker_config))
                    else:
                        raise ValueError(f"Unknown tracker config type: {type(tracker_config)}")

                logger.debug(
                    f"Camera {camera_id}, created/updates trackers: {', '.join([tracker.__class__.__name__ for tracker in trackers])}")

            # Check for new frame to process
            if not process_frame_number_subscription.empty():
                process_frame_number_message:ProcessFrameNumberMessage = process_frame_number_subscription.get()

                logger.debug(
                    f"Camera {camera_id} received request to process frame number {process_frame_number_message.frame_number}")

                # Process the frame
                frame_rec_array = camera_shm.get_data_by_index(index=process_frame_number_message.frame_number,
                                                               frame_rec_array=frame_rec_array)
                for tracker in trackers:
                    observation = tracker.process_image(frame_number=frame_rec_array.frame_metadata.frame_number,
                                                        image=frame_rec_array.image, )
                    if observation is not None:
                        # Publish the observation to the IPC
                        ipc.pubsub.publish(
                            topic_type=CameraNodeOutputTopic,
                            message=CameraNodeOutputMessage(
                                frame_metadata=frame_rec_array.metadata,
                                tracker_name=tracker.__class__.__name__,
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
