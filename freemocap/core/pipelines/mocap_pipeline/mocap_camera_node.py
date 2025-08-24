import logging
import multiprocessing
import time
from dataclasses import dataclass
from multiprocessing import Queue, Process

from skellycam import CameraId
from skellycam.core.camera_group.camera.config.camera_config import CameraConfig
from skellycam.core.camera_group.shmorchestrator.shared_memory.single_slot_camera_shared_memory import \
    CameraSharedMemoryDTO, SingleSlotCameraSharedMemory
from skellycam.core.frames.payloads.metadata.frame_metadata import FrameMetadata
from skellytracker.trackers.mediapipe_tracker import MediapipeTrackerConfig, MediapipeTracker
from skellytracker.trackers.mediapipe_tracker.mediapipe_observation import MediapipeObservation

from freemocap.pipelines.processing_pipeline import BaseCameraNode, BasePipelineStageConfig, BaseCameraNodeOutputData

logger = logging.getLogger(__name__)


@dataclass
class MocapPipelineCameraNodeConfig(BasePipelineStageConfig):
    camera_config: CameraConfig
    tracker_config: MediapipeTrackerConfig
    param1: int = 1




@dataclass
class MocapCameraNodeOutputData(BaseCameraNodeOutputData):
    frame_metadata: FrameMetadata
    mediapipe_observation: MediapipeObservation

    def to_serializable_dict(self) -> dict:
        return dict(
            frame_metadata=self.frame_metadata.model_dump(),
            mediapipe_observation=self.mediapipe_observation.to_serializable_dict(),
        )

@dataclass
class MocapCameraNode(BaseCameraNode):
    @classmethod
    def create(cls,
               camera_id: CameraId,
               config: MocapPipelineCameraNodeConfig,
               camera_shm_dto: CameraSharedMemoryDTO,
               output_queue: Queue,
               all_ready_events: dict[CameraId, multiprocessing.Event],
               shutdown_event: multiprocessing.Event,
               ):
        return cls(camera_id=camera_id,
                   config=config,
                   incoming_frame_shm=SingleSlotCameraSharedMemory.recreate(camera_config=config.camera_config,
                                                                            camera_shm_dto=camera_shm_dto,
                                                                            read_only=False),
                   process=Process(target=cls._run,
                                   kwargs=dict(camera_id=camera_id,
                                               config=config,
                                               camera_shm_dto=camera_shm_dto,
                                               output_queue=output_queue,
                                               all_ready_events=all_ready_events,
                                               shutdown_event=shutdown_event
                                               )
                                   ),
                   all_ready_events=all_ready_events,
                   shutdown_event=shutdown_event
                   )

    @staticmethod
    def _run(camera_id: CameraId,
             config: MocapPipelineCameraNodeConfig,
             camera_shm_dto: CameraSharedMemoryDTO,
             output_queue: Queue,
             all_ready_events: dict[CameraId, multiprocessing.Event],
             shutdown_event: multiprocessing.Event,
             ):
        frame_intake_shm = SingleSlotCameraSharedMemory.recreate(
            camera_config=config.camera_config,
            camera_shm_dto=camera_shm_dto,
            read_only=False)

        mediapipe_tracker = MediapipeTracker.create(config=config.tracker_config)
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
                    observation, raw_results = mediapipe_tracker.process_image(frame.image, annotate_image=False)

                    time_to_process = time.perf_counter_ns() - tik
                    output_queue.put(MocapCameraNodeOutputData(
                        frame_metadata=FrameMetadata.from_frame_metadata_array(frame.metadata),
                        mediapipe_observation=observation,
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
