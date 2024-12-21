import logging
import multiprocessing
from abc import ABC, abstractmethod
from enum import Enum
from multiprocessing import Process, Queue
from typing import Dict

from pydantic import BaseModel, Field, ConfigDict
from skellycam.core import CameraId
from skellycam.core.camera_group.shmorchestrator.shared_memory.ring_buffer_camera_shared_memory import \
    RingBufferCameraSharedMemory, RingBufferCameraSharedMemoryDTO
from skellycam.core.frames.payloads.frame_payload import FramePayload
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload

logger = logging.getLogger(__name__)


class StageConfigKeys(str, Enum):
    CAMERA_PROCESSES = "camera_processes"
    AGGREGATION_PROCESS = "aggregation_process"


class PipelineStageConfig(BaseModel, ABC):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    pass


class PipelineConfig(BaseModel, ABC):
    stage_configs: Dict[str, PipelineStageConfig] = Field(default_factory=dict)


class CameraGroupPipelineConfig(PipelineConfig):
    stage_configs: Dict[str, PipelineStageConfig] = {
        StageConfigKeys.CAMERA_PROCESSES: Dict[CameraId, PipelineStageConfig],
        StageConfigKeys.AGGREGATION_PROCESS: PipelineStageConfig}


class PipelineData(BaseModel, ABC):
    data: object
    metadata: dict[object, object] = Field(default_factory=dict)


class CameraProcessingNode(BaseModel, ABC):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    config: PipelineStageConfig
    camera_id: CameraId
    process: Process
    output_queue: Queue
    camera_ring_shm: RingBufferCameraSharedMemory
    shutdown_event: multiprocessing.Event

    @classmethod
    def create(cls,
               config: PipelineConfig,
               camera_id: CameraId,
               camera_ring_shm_dto: RingBufferCameraSharedMemoryDTO,
               output_queue: Queue,
               shutdown_event: multiprocessing.Event):
        return cls(camera_id=camera_id,
                   camera_ring_shm=RingBufferCameraSharedMemory.recreate(dto=camera_ring_shm_dto,
                                                                         read_only=False),
                   shutdown_event=shutdown_event,
                   process=Process(target=cls._run, args=(config, camera_ring_shm_dto, output_queue)),
                   config=config)

    def intake_data(self, frame_payload: FramePayload):
        self.camera_ring_shm.put_frame(frame_payload.image, frame_payload.metadata)

    @staticmethod
    def _run(config: PipelineStageConfig,
             camera_ring_shm_dto: RingBufferCameraSharedMemoryDTO,
             output_queue: Queue,
             shutdown_event: multiprocessing.Event):
        pass

    def start(self):
        logger.debug(f"Starting {self.__class__.__name__} for camera {self.camera_id}")
        self.process.start()

    def stop(self):
        logger.debug(f"Stopping {self.__class__.__name__} for camera {self.camera_id}")
        self.shutdown_event.set()
        self.process.join()

    def join(self):
        self.process.join()


class AggregationProcessNode(BaseModel, ABC):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    config: PipelineStageConfig
    process: Process
    input_queues: Dict[CameraId, Queue]
    output_queue: Queue
    shutdown_event: multiprocessing.Event

    @classmethod
    def create(cls,
               config: PipelineConfig,
               input_queues: Dict[CameraId, Queue],
               output_queue: Queue,
               shutdown_event: multiprocessing.Event):
        return cls(config=config,
                   process=Process(target=cls._run, args=(config, input_queues, output_queue, shutdown_event)),
                   input_queues=input_queues,
                   output_queue=output_queue,
                   shutdown_event=shutdown_event)

    @staticmethod
    def _run(config: PipelineConfig,
             input_queues: Dict[CameraId, Queue],
             output_queue: Queue,
             shutdown_event: multiprocessing.Event):
        pass

    def start(self):
        logger.debug(f"Starting {self.__class__.__name__}")
        self.process.start()

    def stop(self):
        logger.debug(f"Stopping {self.__class__.__name__}")
        self.shutdown_event.set()
        self.process.join()

    def join(self):
        self.process.join()


class CameraGroupProcessingPipeline(BaseModel, ABC):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    config: PipelineConfig
    camera_processes: Dict[CameraId, CameraProcessingNode]
    aggregation_process: AggregationProcessNode
    output_queue: Queue
    shutdown_event: multiprocessing.Event

    @classmethod
    def create(cls,
               config: PipelineConfig,
               camera_shm_dtos: Dict[CameraId, RingBufferCameraSharedMemoryDTO],
               shutdown_event: multiprocessing.Event):
        camera_process_configs = config.stage_configs.get("camera_processes", {})
        aggregation_process_config = config.stage_configs.get("aggregation_process", {})
        camera_output_queues = {camera_id: Queue() for camera_id in camera_shm_dtos.keys()}
        aggregation_output_queue = Queue()
        camera_processes = {camera_id: CameraProcessingNode.create(config=camera_process_configs.get(camera_id, {}),
                                                                   camera_id=camera_id,
                                                                   camera_ring_shm_dto=camera_shm_dtos[camera_id],
                                                                   output_queue=camera_output_queues[camera_id],
                                                                   shutdown_event=shutdown_event)
                            for camera_id in camera_process_configs.keys()}
        aggregation_process = AggregationProcessNode.create(config=aggregation_process_config,
                                                            input_queues=camera_output_queues,
                                                            output_queue=aggregation_output_queue,
                                                            shutdown_event=shutdown_event)

        return cls(config=config,
                   camera_processes=camera_processes,
                   aggregation_process=aggregation_process,
                   output_queue=aggregation_process.output_queue,
                   shutdown_event=shutdown_event,
                   )

    def intake_data(self, multiframe_payload: MultiFramePayload):
        if not all(camera_id in self.camera_processes.keys() for camera_id in multiframe_payload.camera_ids):
            raise ValueError("Data provided for camera IDs not in camera processes!")
        for camera_id, frame_payload in multiframe_payload.frames.items():
            self.camera_processes[camera_id].intake_data(frame_payload)

    def start(self):
        logger.debug(f"Starting {self.__class__.__name__} with camera processes {self.camera_processes.keys()}...")
        self.aggregation_process.start()
        for camera_id, camera_process in self.camera_processes.items():
            camera_process.start()

    def shutdown(self):
        logger.debug(f"Shutting down {self.__class__.__name__}...")
        self.shutdown_event.set()
        self.aggregation_process.join()
        for camera_id, camera_process in self.camera_processes.items():
            camera_process.join()


class CameraGroupProcessingServer(BaseModel, ABC):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    processing_pipeline: CameraGroupProcessingPipeline
    pipeline_config: PipelineConfig
    shutdown_event: multiprocessing.Event

    @classmethod
    def create(cls,
               pipeline_config: PipelineConfig,
               camera_shm_dtos: Dict[CameraId, RingBufferCameraSharedMemoryDTO],
               shutdown_event: multiprocessing.Event):
        return cls(processing_pipeline=CameraGroupProcessingPipeline.create(config=pipeline_config,
                                                                            camera_shm_dtos=camera_shm_dtos,
                                                                            shutdown_event=shutdown_event),
                   pipeline_config=pipeline_config,
                   shutdown_event=shutdown_event)

    def intake_data(self, multiframe_payload: MultiFramePayload):
        self.processing_pipeline.intake_data(multiframe_payload)

    def start(self):
        logger.debug(f"Starting {self.__class__.__name__}...")
        self.processing_pipeline.start()

    def shutdown(self):
        logger.debug(f"Shutting down {self.__class__.__name__}...")
        self.shutdown_event.set()
        self.processing_pipeline.shutdown()
