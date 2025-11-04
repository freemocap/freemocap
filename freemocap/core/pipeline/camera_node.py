import logging
import multiprocessing
import time
from dataclasses import dataclass

import cv2
import numpy as np
from pydantic import BaseModel, ConfigDict
from skellycam.core.ipc.pubsub.pubsub_topics import SetShmMessage
from skellycam.core.ipc.shared_memory.camera_shared_memory_ring_buffer import CameraSharedMemoryRingBuffer
from skellycam.core.types.type_overloads import CameraIdString, WorkerType, TopicSubscriptionQueue
from skellycam.utilities.wait_functions import wait_1ms
from skellytracker.trackers.charuco_tracker.charuco_annotator import CharucoImageAnnotator
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation

from freemocap.core.pipeline.pipeline_configs import  PipelineConfig
from freemocap.core.pipeline.pipeline_ipc import PipelineIPC
from freemocap.core.tasks.calibration_task.ooooold.calibration_helpers.single_camera_calibrator import SingleCameraCalibrator
from freemocap.core.types.type_overloads import PipelineIdString
from freemocap.pubsub.pubsub_topics import ProcessFrameNumberTopic, PipelineConfigUpdateTopic, CameraNodeOutputTopic, \
    PipelineConfigUpdateMessage, ProcessFrameNumberMessage, CameraNodeOutputMessage, ShouldCalibrateTopic, \
    ShouldCalibrateMessage
from skellytracker.trackers.charuco_tracker.charuco_detector import CharucoDetector

logger = logging.getLogger(__name__)


class CameraNodeState(BaseModel):
    model_config = ConfigDict(
        validate_assignment=True,
        frozen=True
    )
    pipeline_id: PipelineIdString
    alive: bool
    last_seen_frame_number: int | None = None
    calibration_task_state: object | None = None
    mocap_task_state: object = None  # TODO - this


@dataclass
class CameraNode:
    camera_id: CameraIdString
    shutdown_self_flag: multiprocessing.Value
    worker: WorkerType

    @classmethod
    def create(cls,
               camera_id: CameraIdString,
               subprocess_registry: list[multiprocessing.Process],
               config: PipelineConfig,
               ipc: PipelineIPC):
        shutdown_self_flag = multiprocessing.Value('b', False)
        worker = multiprocessing.Process(target=cls._run,
                                         name=f"CameraProcessingNode-{camera_id}",
                                         kwargs=dict(camera_id=camera_id,
                                                     ipc=ipc,
                                                     config=config,
                                                     shutdown_self_flag=shutdown_self_flag,
                                                     process_frame_number_subscription=ipc.pubsub.get_subscription(
                                                         ProcessFrameNumberTopic),
                                                     pipeline_config_subscription=ipc.pubsub.get_subscription(
                                                         PipelineConfigUpdateTopic),
                                                     should_calibrate_subscription=ipc.pubsub.get_subscription(
                                                         ShouldCalibrateTopic),
                                                     shm_subscription=ipc.shm_topic.get_subscription()
                                                     ),
                                         daemon=True
                                         )
        subprocess_registry.append(worker)
        return cls(camera_id=camera_id,
                   shutdown_self_flag=shutdown_self_flag,
                   worker=worker
                   )

    @staticmethod
    def _run(camera_id: CameraIdString,
             ipc: PipelineIPC,
             config: PipelineConfig,
             process_frame_number_subscription: TopicSubscriptionQueue,
             pipeline_config_subscription: TopicSubscriptionQueue,
             should_calibrate_subscription: TopicSubscriptionQueue,
             shutdown_self_flag: multiprocessing.Value,
             shm_subscription: TopicSubscriptionQueue,
             ):
        if multiprocessing.parent_process():
            # Configure logging if multiprocessing (i.e. if there is a parent process)
            from freemocap.system.logging_configuration.configure_logging import configure_logging
            from freemocap import LOG_LEVEL
            configure_logging(LOG_LEVEL, ws_queue=ipc.ws_queue)

        logger.debug(f"Initializing camera processing node for camera {camera_id} - awaiting SHM setup...")
        shm_update_message: SetShmMessage = shm_subscription.get(block=True)
        logger.debug(f"Received SHM setup message - recreating shared memory rig buffer for camera {camera_id}")
        camera_shm = CameraSharedMemoryRingBuffer.recreate(dto=shm_update_message.get_shm_dto_by_camera_id(camera_id),
                                                           read_only=False)
        camera_calibrator: SingleCameraCalibrator | None = None
        charuco_detector = CharucoDetector.create(config=config.calibration_task_config.detector_config)
        try:
            logger.trace(f"Starting camera processing node for camera {camera_id}")
            frame_rec_array: np.recarray | None = None
            while ipc.should_continue and not shutdown_self_flag.value:
                wait_1ms()
                # Check trackers config updates
                if not pipeline_config_subscription.empty():
                    new_pipeline_config_message: PipelineConfigUpdateMessage = pipeline_config_subscription.get()
                    logger.debug(f"Received new skelly trackers for camera {camera_id}: {new_pipeline_config_message}")

                # Check for new frame to process
                if not process_frame_number_subscription.empty():
                    process_frame_number_message: ProcessFrameNumberMessage = process_frame_number_subscription.get()

                    charuco_observation: CharucoObservation | None = None
                    if config.calibration_task_config.live_track_charuco:
                        # Process the frame
                        tik = time.perf_counter_ns()
                        frame_rec_array = camera_shm.get_data_by_index(index=process_frame_number_message.frame_number,
                                                                       rec_array=frame_rec_array)
                        if frame_rec_array.frame_metadata.camera_config.rotation != -1:
                            rotated_image = cv2.rotate(
                                src=frame_rec_array.image[0],
                                rotateCode=frame_rec_array.frame_metadata.camera_config.rotation[0]
                            )
                        else:
                            rotated_image = frame_rec_array.image[0]
                        charuco_observation = charuco_detector.detect(
                            frame_number=frame_rec_array.frame_metadata.frame_number[0],
                            image=rotated_image, )

                        # tok = time.perf_counter_ns()
                        # if charuco_observation is not None and charuco_observation.detected_charuco_corners_in_object_coordinates is not None:
                        #     # Publish the observation to the IPC
                        #     if camera_calibrator is None:
                        #         camera_calibrator = SingleCameraCalibrator.from_charuco_observation(
                        #             camera_id=camera_id,
                        #             charuco_observation=charuco_observation
                        #         )
                        #     else:
                        #         camera_calibrator.add_observation(observation=charuco_observation)
                        #         charuco_observation.compute_board_pose_and_camera_coordinates(
                        #             camera_matrix=camera_calibrator.camera_matrix.matrix,
                        #             distortion_coefficients=camera_calibrator.distortion_coefficients.coefficients
                        #         )

                    ipc.pubsub.publish(
                        topic_type=CameraNodeOutputTopic,
                        message=CameraNodeOutputMessage(
                            camera_id=frame_rec_array.frame_metadata.camera_config.camera_id[0],
                            frame_number=frame_rec_array.frame_metadata.frame_number[0],
                            charuco_observation=charuco_observation,
                        ),
                    )
                    tok2 = time.perf_counter_ns()
                    # logger.debug(
                    #     f"Camera {camera_id} processed frame {frame_rec_array.frame_metadata.frame_number[0]} in "
                    #     f"{(tok - tik) / 1e6:.2f} ms, published observation in {(tok2 - tok) / 1e6:.2f} ms")
        except Exception as e:
            logger.exception(f"Exception in camera node for camera {camera_id}: {e}")
            ipc.kill_everything()
            raise e
        finally:
            logger.debug(f"Shutting down camera processing node for camera {camera_id}")

    def start(self):
        logger.debug(f"Starting {self.__class__.__name__} for camera {self.camera_id}")
        self.worker.start()

    def shutdown(self):
        logger.debug(f"Stopping {self.__class__.__name__} for camera {self.camera_id}")
        self.shutdown_self_flag.value = True
        self.worker.join()
