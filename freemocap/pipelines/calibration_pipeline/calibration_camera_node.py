import logging
import multiprocessing
import time
from multiprocessing import Queue, Process

from skellycam import CameraId
from skellycam.core.camera_group.camera.config.camera_config import CameraConfig
from skellycam.core.camera_group.shmorchestrator.shared_memory.single_slot_camera_shared_memory import \
    CameraSharedMemoryDTO, SingleSlotCameraSharedMemory
from skellycam.core.frames.payloads.metadata.frame_metadata_enum import FRAME_METADATA_MODEL
from skellytracker import SkellyTrackerTypes

from freemocap.pipelines.pipeline_abcs import BaseCameraNode, BasePipelineStageConfig, BasePipelineData

logger = logging.getLogger(__name__)


class CalibrationPipelineAggregationLayerOutputData(BasePipelineData):
    pass


class CalibrationPipelineAggregationNodeConfig(BasePipelineStageConfig):
    param2: int = 2

class CalibrationPipelineCameraNodeConfig(BasePipelineStageConfig):
    camera_config: CameraConfig
    param1: int = 1




class CalibrationCameraNodeOutputData(BasePipelineData):
    data: object




class CalibrationCameraNode(BaseCameraNode):
    @classmethod
    def create(cls,
               camera_id: CameraId,
               config: CalibrationPipelineCameraNodeConfig,
               camera_shm_dto: CameraSharedMemoryDTO,
               output_queue: Queue,
               shutdown_event: multiprocessing.Event,
               ):
        return cls(camera_id=camera_id,
                   config=config,
                   camera_ring_shm=SingleSlotCameraSharedMemory.recreate(camera_config=config.camera_config,
                                                                         camera_shm_dto=camera_shm_dto,
                                                                         read_only=False),
                   process=Process(target=cls._run,
                                   kwargs=dict(camera_id=camera_id,
                                               config=config,
                                               camera_shm_dto=camera_shm_dto,
                                               output_queue=output_queue,
                                               shutdown_event=shutdown_event
                                               )
                                   ),
                   shutdown_event=shutdown_event
                   )

    @staticmethod
    def _run(camera_id: CameraId,
             config: CalibrationPipelineCameraNodeConfig,
             camera_shm_dto: CameraSharedMemoryDTO,
             output_queue: Queue,
             shutdown_event: multiprocessing.Event,
             tracker: SkellyTrackerTypes = SkellyTrackerTypes.CHARUCO,
             ):
        logger.trace(f"Starting camera processing node for camera {camera_id}")
        camera_ring_shm = SingleSlotCameraSharedMemory.recreate(
            camera_config=config.camera_config,
            camera_shm_dto=camera_shm_dto,
            read_only=False)

        charuco_tracker = tracker.value.create()

        try:
            while not shutdown_event.is_set():
                time.sleep(0.001)
                if camera_ring_shm.new_frame_available:
                    frame = camera_ring_shm.retrieve_frame()
                    print(f"\t\tCamera Node for Camera#{camera_id} received frame {frame.metadata[FRAME_METADATA_MODEL.FRAME_NUMBER.value]} with image shape {frame.image.shape}")
                    tracker_results = charuco_tracker.process_image(frame.image, annotate_image=False)
                    output_queue.put(CalibrationCameraNodeOutputData(data=tracker_results))
        except Exception as e:
            logger.exception(f"Error in camera processing node for camera {camera_id}", exc_info=e)
            raise
        finally:
            logger.trace(f"Shutting down camera processing node for camera {camera_id}")
            shutdown_event.set()
            camera_ring_shm.close()






