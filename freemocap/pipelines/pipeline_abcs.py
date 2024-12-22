import logging
import multiprocessing
from abc import ABC
from dataclasses import dataclass
from enum import Enum
from multiprocessing import Process, Queue

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


class ReadTypes(str, Enum):
    LATEST = "latest"
    NEXT = "next"


class PipelineStageConfig(BaseModel, ABC):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    pass


class PipelineConfig(BaseModel, ABC):
    camera_node_configs: dict[CameraId, PipelineStageConfig] = Field(default_factory=dict)
    aggregation_node_config: PipelineStageConfig = Field(default_factory=PipelineStageConfig)

    @classmethod
    def create(cls, camera_ids: list[CameraId]):
        return cls(camera_node_configs={camera_id: PipelineStageConfig() for camera_id in camera_ids},
                   aggregation_node_config=PipelineStageConfig())


class CameraGroupPipelineConfig(PipelineConfig):
    stage_configs: dict[str, PipelineStageConfig] = {
        StageConfigKeys.CAMERA_PROCESSES.value: dict[CameraId, PipelineStageConfig],
        StageConfigKeys.AGGREGATION_PROCESS.value: PipelineStageConfig}


class PipelineData(BaseModel, ABC):
    data: object
    metadata: dict[object, object] = Field(default_factory=dict)


@dataclass
class CameraProcessingNode(ABC):
    config: PipelineStageConfig
    camera_id: CameraId
    camera_ring_shm: RingBufferCameraSharedMemory
    read_type: ReadTypes

    process: Process
    shutdown_event: multiprocessing.Event

    @classmethod
    def create(cls,
               config: PipelineConfig,
               camera_id: CameraId,
               camera_ring_shm_dto: RingBufferCameraSharedMemoryDTO,
               output_queue: Queue,
               read_type: ReadTypes,
               shutdown_event: multiprocessing.Event):
        return cls(config=config,
                   camera_id=camera_id,
                   camera_ring_shm=RingBufferCameraSharedMemory.recreate(dto=camera_ring_shm_dto,
                                                                         read_only=False),
                   process=Process(target=cls._run,
                                   kwargs=dict(config=config,
                                               camera_ring_shm_dto=camera_ring_shm_dto,
                                               output_queue=output_queue,
                                               read_type=read_type,
                                               shutdown_event=shutdown_event
                                               )
                                   ),
                   read_type=read_type,
                   shutdown_event=shutdown_event
                   )

    def intake_data(self, frame_payload: FramePayload):
        self.camera_ring_shm.put_frame(frame_payload.image, frame_payload.metadata)

    @staticmethod
    def _run(config: PipelineStageConfig,
             camera_ring_shm_dto: RingBufferCameraSharedMemoryDTO,
             output_queue: Queue,
             read_type: ReadTypes,
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


@dataclass
class AggregationProcessNode(ABC):
    config: PipelineStageConfig
    process: Process
    input_queues: dict[CameraId, Queue]
    output_queue: Queue
    shutdown_event: multiprocessing.Event

    @classmethod
    def create(cls,
               config: PipelineConfig,
               input_queues: dict[CameraId, Queue],
               output_queue: Queue,
               shutdown_event: multiprocessing.Event):
        return cls(config=config,
                   process=Process(target=cls._run,
                                   kwargs=dict(config=config,
                                               input_queues=input_queues,
                                               output_queue=output_queue,
                                               shutdown_event=shutdown_event)
                                   ),
                   input_queues=input_queues,
                   output_queue=output_queue,
                   shutdown_event=shutdown_event)

    @staticmethod
    def _run(config: PipelineConfig,
             input_queues: dict[CameraId, Queue],
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


@dataclass
class CameraGroupProcessingPipeline(ABC):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    config: PipelineConfig
    camera_node: dict[CameraId, CameraProcessingNode]
    aggregation_node: AggregationProcessNode
    shutdown_event: multiprocessing.Event

    @classmethod
    def create(cls,
               config: PipelineConfig,
               camera_shm_dtos: dict[CameraId, RingBufferCameraSharedMemoryDTO],
               read_type: ReadTypes,
               shutdown_event: multiprocessing.Event):
        if not all(camera_id in camera_shm_dtos.keys() for camera_id in config.camera_node_configs.keys()):
            raise ValueError("Camera IDs provided in config not in camera shared memory DTOS!")
        camera_output_queues = {camera_id: Queue() for camera_id in camera_shm_dtos.keys()}
        aggregation_output_queue = Queue()
        camera_processes = {camera_id: CameraProcessingNode.create(config=config,
                                                                   camera_id=CameraId(camera_id),
                                                                   camera_ring_shm_dto=camera_shm_dtos[camera_id],
                                                                   output_queue=camera_output_queues[camera_id],
                                                                   read_type=read_type,
                                                                   shutdown_event=shutdown_event)
                            for camera_id, config in config.camera_node_configs.items()}
        aggregation_process = AggregationProcessNode.create(config=config.aggregation_node_config,
                                                            input_queues=camera_output_queues,
                                                            output_queue=aggregation_output_queue,
                                                            shutdown_event=shutdown_event)

        return cls(config=config,
                   camera_node=camera_processes,
                   aggregation_node=aggregation_process,
                   shutdown_event=shutdown_event,
                   )

    def intake_data(self, multiframe_payload: MultiFramePayload):
        if not all(camera_id in self.camera_node.keys() for camera_id in multiframe_payload.camera_ids):
            raise ValueError("Data provided for camera IDs not in camera processes!")
        for camera_id, frame_payload in multiframe_payload.frames.items():
            self.camera_node[camera_id].intake_data(frame_payload)

    def start(self):
        logger.debug(f"Starting {self.__class__.__name__} with camera processes {self.camera_node.keys()}...")
        self.aggregation_node.start()
        for camera_id, camera_node in self.camera_node.items():
            camera_node.start()

    def shutdown(self):
        logger.debug(f"Shutting down {self.__class__.__name__}...")
        self.shutdown_event.set()
        self.aggregation_node.join()
        for camera_id, camera_process in self.camera_node.items():
            camera_process.join()


@dataclass
class CameraGroupProcessingServer(ABC):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    pipeline_config: PipelineConfig
    processing_pipeline: CameraGroupProcessingPipeline
    read_type: ReadTypes
    shutdown_event: multiprocessing.Event

    def intake_data(self, multiframe_payload: MultiFramePayload):
        self.processing_pipeline.intake_data(multiframe_payload)

    @classmethod
    def create(cls,
               pipeline_config: PipelineConfig,
               camera_shm_dtos: dict[CameraId, RingBufferCameraSharedMemoryDTO],
               read_type: ReadTypes,
               shutdown_event: multiprocessing.Event):
        return cls(processing_pipeline=CameraGroupProcessingPipeline.create(config=pipeline_config,
                                                                            camera_shm_dtos=camera_shm_dtos,
                                                                            read_type=read_type,
                                                                            shutdown_event=shutdown_event),
                   pipeline_config=pipeline_config,
                   read_type=read_type,
                   shutdown_event=shutdown_event)

    def start(self):
        logger.debug(f"Starting {self.__class__.__name__}...")
        self.processing_pipeline.start()

    def shutdown(self):
        logger.debug(f"Shutting down {self.__class__.__name__}...")
        self.shutdown_event.set()
        self.processing_pipeline.shutdown()
