import logging
import multiprocessing
import time
from dataclasses import dataclass

import cv2
import numpy as np
from pydantic import BaseModel
from skellycam.core.ipc.pubsub.pubsub_topics import SetShmMessage
from skellycam.core.ipc.shared_memory.camera_shared_memory_ring_buffer import CameraSharedMemoryRingBuffer
from skellycam.core.types.type_overloads import CameraIdString, WorkerType, TopicSubscriptionQueue
from skellycam.utilities.wait_functions import wait_1ms
from skellytracker.trackers.charuco_tracker.charuco_annotator import CharucoImageAnnotator
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation

from freemocap.core.pipeline.pipeline_configs import CameraNodeConfig, PipelineConfig
from freemocap.core.pipeline.pipeline_ipc import PipelineIPC
from freemocap.core.pubsub.pubsub_topics import ProcessFrameNumberTopic, PipelineConfigTopic, CameraNodeOutputTopic, \
    PipelineConfigMessage, ProcessFrameNumberMessage, CameraNodeOutputMessage, ShouldCalibrateTopic, \
    ShouldCalibrateMessage
from freemocap.core.tasks.calibration_task.calibration_helpers.single_camera_calibrator import SingleCameraCalibrator
from freemocap.core.tasks.calibration_task.calibration_pipeline_task import CalibrationCameraNodeTask

logger = logging.getLogger(__name__)


class CameraNodeImageAnnotater(BaseModel):
    calibration_annotator: CharucoImageAnnotator

    # mocap_annotator: MediapipeImageAnnotator

    @classmethod
    def from_pipeline_config(cls, camera_id: CameraIdString, pipeline_config: PipelineConfig):
        return cls(
            calibration_annotator=CharucoImageAnnotator.create(
                config=pipeline_config.camera_node_configs[camera_id].calibration_camera_node_config.annotator_config),
            # mocap_annotator=MediapipeImageAnnotator.create(
            #     config=pipeline_config.camera_node_configs[camera_id].mocap_camera_node_config),
        )

    def annotate_image(self,
                       image: np.ndarray,
                       charuco_observation: CharucoObservation | None = None,
                       # mediapipe_observaton:MediapipeObservation|None=None,
                       ) -> np.ndarray:
        annotated_image = image
        if charuco_observation is not None:
            annotated_image = self.calibration_annotator.annotate_image(image=annotated_image,
                                                                        observation=charuco_observation)
        # if mediapipe_observaton is not None:
        #     annotated_image = self.mocap_annotator.annotate_image(image=annotated_image,
        #                                                          observation=mediapipe_observaton)
        return annotated_image


@dataclass
class CameraNode:
    camera_id: CameraIdString
    shutdown_self_flag: multiprocessing.Value
    worker: WorkerType

    @classmethod
    def create(cls,
               camera_id: CameraIdString,
               config: CameraNodeConfig,
               ipc: PipelineIPC):
        shutdown_self_flag = multiprocessing.Value('b', False)
        return cls(camera_id=camera_id,
                   shutdown_self_flag=shutdown_self_flag,
                   worker=multiprocessing.Process(target=cls._run,
                                                  name=f"CameraProcessingNode-{camera_id}",
                                                  kwargs=dict(camera_id=camera_id,
                                                              ipc=ipc,
                                                              camera_node_config=config,
                                                              shutdown_self_flag=shutdown_self_flag,
                                                              process_frame_number_subscription=ipc.pubsub.get_subscription(
                                                                  ProcessFrameNumberTopic),
                                                              pipeline_config_subscription=ipc.pubsub.get_subscription(
                                                                  PipelineConfigTopic),
                                                              should_calibrate_subscription=ipc.pubsub.get_subscription(
                                                                  ShouldCalibrateTopic),
                                                              shm_subscription=ipc.shm_topic.get_subscription()
                                                              ),
                                                  daemon=True
                                                  ),
                   )

    @staticmethod
    def _run(camera_id: CameraIdString,
             ipc: PipelineIPC,
             camera_node_config: CameraNodeConfig,
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
        try:
            logger.trace(f"Starting camera processing node for camera {camera_id}")
            calibration_task = CalibrationCameraNodeTask.create(
                config=camera_node_config.calibration_camera_node_config)
            # mocap_task: BaseCameraNodeTask|None = None # TODO - this

            frame_rec_array: np.recarray | None = None
            while ipc.should_continue and not shutdown_self_flag.value:
                wait_1ms()
                # Check trackers config updates
                if not pipeline_config_subscription.empty():
                    new_pipeline_config_message: PipelineConfigMessage = pipeline_config_subscription.get()
                    logger.debug(f"Received new skelly trackers for camera {camera_id}: {new_pipeline_config_message}")

                    camera_node_config = new_pipeline_config_message.pipeline_config.camera_node_configs[
                        camera_node_config.camera_id]
                    calibration_task = CalibrationCameraNodeTask.create(
                        config=camera_node_config.calibration_camera_node_config)
                    # mocap_task = None  # TODO - this

                if not should_calibrate_subscription.empty():
                    _ : ShouldCalibrateMessage = should_calibrate_subscription.get() #dummy message triggers calibration
                    if camera_calibrator is None:
                        raise RuntimeError("Received should calibrate message but camera calibrator is None")
                    camera_calibrator.calibrate()

                # Check for new frame to process
                if not process_frame_number_subscription.empty():
                    process_frame_number_message: ProcessFrameNumberMessage = process_frame_number_subscription.get()
                    #
                    # logger.trace(
                    #     f"Camera {camera_id} received request to process frame number {process_frame_number_message.frame_number}")

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
                    charuco_observation = calibration_task.process_image(
                        frame_number=frame_rec_array.frame_metadata.frame_number[0],
                        image=rotated_image, )

                    tok = time.perf_counter_ns()
                    if charuco_observation is not None and charuco_observation.detected_charuco_corners_in_object_coordinates is not None:
                        # Publish the observation to the IPC
                        if camera_calibrator is None:
                            camera_calibrator = SingleCameraCalibrator.from_charuco_observation(
                                camera_id=camera_id,
                                charuco_observation=charuco_observation
                            )
                        else:
                            camera_calibrator.add_observation(observation=charuco_observation)
                            charuco_observation.compute_board_pose_and_camera_coordinates(
                                camera_matrix=camera_calibrator.camera_matrix.matrix,
                                distortion_coefficients=camera_calibrator.distortion_coefficients.coefficients
                            )

                    ipc.pubsub.publish(
                        topic_type=CameraNodeOutputTopic,
                        message=CameraNodeOutputMessage(
                            camera_id=frame_rec_array.frame_metadata.camera_config.camera_id[0],
                            frame_number=frame_rec_array.frame_metadata.frame_number[0],
                            tracker_name=calibration_task.__class__.__name__,
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
