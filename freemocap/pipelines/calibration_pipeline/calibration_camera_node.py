import logging
import multiprocessing
import time
from dataclasses import dataclass
from multiprocessing import Queue
from threading import Thread

from skellycam import CameraId
from skellycam.core.camera_group.camera.config.camera_config import CameraConfig
from skellycam.core.camera_group.shmorchestrator.shared_memory.single_slot_camera_shared_memory import \
    CameraSharedMemoryDTO, SingleSlotCameraSharedMemory
from skellycam.core.frames.payloads.metadata.frame_metadata import FrameMetadata
from skellytracker.trackers.charuco_tracker import CharucoTrackerConfig, CharucoTracker

from freemocap.pipelines.calibration_pipeline.calibration_camera_node_output_data import CalibrationCameraNodeOutputData
from freemocap.pipelines.calibration_pipeline.single_camera_calibrator import SingleCameraCalibrator
from freemocap.pipelines.processing_pipeline import BaseCameraNode, BasePipelineStageConfig

logger = logging.getLogger(__name__)


class CalibrationPipelineCameraNodeConfig(BasePipelineStageConfig):
    camera_config: CameraConfig
    tracker_config: CharucoTrackerConfig
    param1: int = 1


@dataclass
class CalibrationCameraNode(BaseCameraNode):
    @classmethod
    def create(cls,
               camera_id: CameraId,
               config: CalibrationPipelineCameraNodeConfig,
               camera_shm_dto: CameraSharedMemoryDTO,
               output_queue: Queue,
               all_ready_events: dict[CameraId, multiprocessing.Event],
               shutdown_event: multiprocessing.Event,
               use_thread: bool=False
               ):
        if use_thread:
            worker = Thread(target=cls._run,
                   kwargs=dict(camera_id=camera_id,
                               config=config,
                               camera_shm_dto=camera_shm_dto,
                               output_queue=output_queue,
                               all_ready_events=all_ready_events,
                               shutdown_event=shutdown_event
                               )
                   )
        else:
            worker = multiprocessing.Process(target=cls._run,
                                             kwargs=dict(camera_id=camera_id,
                                                         config=config,
                                                         camera_shm_dto=camera_shm_dto,
                                                         output_queue=output_queue,
                                                         all_ready_events=all_ready_events,
                                                         shutdown_event=shutdown_event
                                                         )
                                             )
        return cls(camera_id=camera_id,
                   config=config,
                   incoming_frame_shm=SingleSlotCameraSharedMemory.recreate(camera_config=config.camera_config,
                                                                            camera_shm_dto=camera_shm_dto,
                                                                            read_only=False),
                   process=worker,
                   all_ready_events=all_ready_events,
                   shutdown_event=shutdown_event
                   )

    @staticmethod
    def _run(camera_id: CameraId,
             config: CalibrationPipelineCameraNodeConfig,
             camera_shm_dto: CameraSharedMemoryDTO,
             output_queue: Queue,
             all_ready_events: dict[CameraId, multiprocessing.Event],
             shutdown_event: multiprocessing.Event,
             ):
        frame_intake_shm = SingleSlotCameraSharedMemory.recreate(
            camera_config=config.camera_config,
            camera_shm_dto=camera_shm_dto,
            read_only=False)

        charuco_tracker = CharucoTracker.create(config=config.tracker_config)
        camera_calibration_estimator: SingleCameraCalibrator | None = None
        try:
            logger.trace(f"Camera#{camera_id} processing node ready!")
            all_ready_events[camera_id].set()
            while not shutdown_event.is_set():
                time.sleep(0.001)
                if not all([event.is_set() for event in all_ready_events.values()]):
                    continue
                if frame_intake_shm.new_frame_available:
                    tik = time.perf_counter_ns()
                    frame = frame_intake_shm.retrieve_frame()
                    time_to_retrieve = time.perf_counter_ns() - tik
                    tik = time.perf_counter_ns()
                    observation, raw_results = charuco_tracker.process_image(frame_number=frame.frame_number,
                                                                             image=frame.image,
                                                                             annotate_image=False)

                    time_to_process = time.perf_counter_ns() - tik
                    output_queue.put(CalibrationCameraNodeOutputData(
                        frame_metadata=FrameMetadata.from_frame_metadata_array(frame.metadata),
                        charuco_observation=observation,
                        time_to_retrieve_frame_ns=time_to_retrieve,
                        time_to_process_frame_ns=time_to_process
                    ),
                    )
        except Exception as e:
            logger.exception(f"Error in camera processing node for camera {camera_id}", exc_info=e)
            raise
        finally:
            logger.trace(f"Shutting down camera processing node for camera {camera_id}")
            shutdown_event.set()
            frame_intake_shm.close()
