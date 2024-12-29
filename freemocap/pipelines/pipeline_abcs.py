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
from skellycam.core.camera_group.shmorchestrator.shared_memory.single_slot_camera_shared_memory import \
    CameraSharedMemoryDTO
from skellycam.core.frames.payloads.frame_payload import FramePayload
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload

logger = logging.getLogger(__name__)


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
    camera_node_configs: dict[CameraId, PipelineStageConfig]
    aggregation_node_configs: PipelineStageConfig


class PipelineData(BaseModel, ABC):
    data: object
    metadata: dict[object, object] = Field(default_factory=dict)


@dataclass
class CameraProcessingNode(ABC):
    config: PipelineStageConfig
    camera_id: CameraId
    camera_ring_shm: RingBufferCameraSharedMemory

    process: Process
    shutdown_event: multiprocessing.Event

    @classmethod
    def create(cls,
               config: PipelineConfig,
               camera_id: CameraId,
               camera_ring_shm_dto: RingBufferCameraSharedMemoryDTO,
               output_queue: Queue,
               shutdown_event: multiprocessing.Event):
        raise NotImplementedError("You need to re-implement this method with your pipeline's version of the CameraProcessingNode "
                                  "abstract base class! See example in the `freemocap/.../dummy_pipeline.py` file.")
        # return cls(config=config,
        #            camera_id=camera_id,
        #            camera_ring_shm=RingBufferCameraSharedMemory.recreate(dto=camera_ring_shm_dto,
        #                                                                  read_only=False),
        #            process=Process(target=cls._run,
        #                            kwargs=dict(config=config,
        #                                        camera_ring_shm_dto=camera_ring_shm_dto,
        #                                        output_queue=output_queue,
        #                                        read_type=read_type,
        #                                        shutdown_event=shutdown_event
        #                                        )
        #                            ),
        #            read_type=read_type,
        #            shutdown_event=shutdown_event
        #          )

    def intake_data(self, frame_payload: FramePayload):
        self.camera_ring_shm.put_frame(frame_payload.image, frame_payload.metadata)



    @staticmethod
    def _run(camera_id:CameraId,
             config: PipelineStageConfig,
             camera_shm_dto: CameraSharedMemoryDTO,
             output_queue: Queue,
             shutdown_event: multiprocessing.Event):
        raise NotImplementedError("Add your camera process logic here! See example in the `freemocap/.../dummy_pipeline.py` file.")
        # logger.trace(f"Starting camera processing node for camera {camera_ring_shm_dto.camera_id}")
        # camera_ring_shm = RingBufferCameraSharedMemory.recreate(dto=camera_ring_shm_dto,
        #                                                         read_only=False)
        # while not shutdown_event.is_set():
        #     time.sleep(0.001)
        #     if camera_ring_shm.ready_to_read:
        #
        #         if read_type == ReadTypes.LATEST_AND_INCREMENT:
        #             image = camera_ring_shm.retrieve_latest_frame(increment=True)
        #         elif read_type == ReadTypes.LATEST_READ_ONLY:
        #             image = camera_ring_shm.retrieve_latest_frame(increment=False)
        #         elif read_type == ReadTypes.NEXT:
        #             image = camera_ring_shm.retrieve_next_frame()
        #         else:
        #             raise ValueError(f"Invalid read_type: {read_type}")
        #
        #         logger.trace(f"Processing image from camera {camera_ring_shm.camera_id}")
        #         # TODO - process image
        #         output_queue.put(PipelineData(data=image))

    def start(self):
        logger.debug(f"Starting {self.__class__.__name__} for camera {self.camera_id}")
        self.process.start()

    def stop(self):
        logger.debug(f"Stopping {self.__class__.__name__} for camera {self.camera_id}")
        self.shutdown_event.set()
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
        raise NotImplementedError("You need to re-implement this method with your pipeline's version of the AggregationProcessNode "
                                    "abstract base class! See example in the `freemocap/.../dummy_pipeline.py` file.")
        # return cls(config=config,
        #            process=Process(target=cls._run,
        #                            kwargs=dict(config=config,
        #                                        input_queues=input_queues,
        #                                        output_queue=output_queue,
        #                                        shutdown_event=shutdown_event)
        #                            ),
        #            input_queues=input_queues,
        #            output_queue=output_queue,
        #            shutdown_event=shutdown_event)

    @staticmethod
    def _run(config: PipelineConfig,
             input_queues: dict[CameraId, Queue],
             output_queue: Queue,
             shutdown_event: multiprocessing.Event):
        raise NotImplementedError("Add your aggregation process logic here! See example in the `freemocap/.../dummy_pipeline.py` file.")
        # while not shutdown_event.is_set():
        #     data_by_camera_id = {camera_id: None for camera_id in input_queues.keys()}
        #     while any([input_queues[camera_id].empty() for camera_id in input_queues.keys()]):
        #         time.sleep(0.001)
        #         for camera_id in input_queues.keys():
        #             if not input_queues[camera_id] is None:
        #                 if not input_queues[camera_id].empty():
        #                     data_by_camera_id[camera_id] = input_queues[camera_id].get()
        #     if len(data_by_camera_id) == len(input_queues):
        #         logger.trace(f"Processing aggregated data from cameras {data_by_camera_id.keys()}")
        #         # TODO - process aggregated data
        #         output_queue.put(PipelineData(data=data_by_camera_id))

    def start(self):
        logger.debug(f"Starting {self.__class__.__name__}")
        self.process.start()

    def stop(self):
        logger.debug(f"Stopping {self.__class__.__name__}")
        self.shutdown_event.set()
        self.process.join()



@dataclass
class CameraGroupProcessingPipeline(ABC):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    config: PipelineConfig
    camera_nodes: dict[CameraId, CameraProcessingNode]
    aggregation_node: AggregationProcessNode
    shutdown_event: multiprocessing.Event

    @classmethod
    def create(cls,
               config: PipelineConfig,
               camera_shm_dtos: dict[CameraId, RingBufferCameraSharedMemoryDTO],
               shutdown_event: multiprocessing.Event):
        raise NotImplementedError("You need to re-implement this method with your pipeline's version of the CameraGroupProcessingPipeline "
                                  "and CameraProcessingNode abstract base classes! See example in the `freemocap/.../dummy_pipeline.py` file.")
        # if not all(camera_id in camera_shm_dtos.keys() for camera_id in config.camera_node_configs.keys()):
        #     raise ValueError("Camera IDs provided in config not in camera shared memory DTOS!")
        # camera_output_queues = {camera_id: Queue() for camera_id in camera_shm_dtos.keys()}
        # aggregation_output_queue = Queue()
        # camera_nodes = {camera_id: CameraProcessingNode.create(config=config,
        #                                                        camera_id=CameraId(camera_id),
        #                                                        camera_ring_shm_dto=camera_shm_dtos[camera_id],
        #                                                        output_queue=camera_output_queues[camera_id],
        #                                                        read_type=read_type,
        #                                                        shutdown_event=shutdown_event)
        #                 for camera_id, config in config.camera_node_configs.items()}
        # aggregation_process = AggregationProcessNode.create(config=config.aggregation_node_config,
        #                                                     input_queues=camera_output_queues,
        #                                                     output_queue=aggregation_output_queue,
        #                                                     shutdown_event=shutdown_event)
        #
        # return cls(config=config,
        #            camera_nodes=camera_nodes,
        #            aggregation_node=aggregation_process,
        #            shutdown_event=shutdown_event,
        #            )

    def intake_data(self, multiframe_payload: MultiFramePayload):
        if not all(camera_id in self.camera_nodes.keys() for camera_id in multiframe_payload.camera_ids):
            raise ValueError("Data provided for camera IDs not in camera processes!")
        for camera_id, frame_payload in multiframe_payload.frames.items():
            self.camera_nodes[camera_id].intake_data(frame_payload)

    def start(self):
        logger.debug(f"Starting {self.__class__.__name__} with camera processes {self.camera_nodes.keys()}...")
        self.aggregation_node.start()
        for camera_id, camera_node in self.camera_nodes.items():
            camera_node.start()

    def shutdown(self):
        logger.debug(f"Shutting down {self.__class__.__name__}...")
        self.shutdown_event.set()
        self.aggregation_node.stop()
        for camera_id, camera_process in self.camera_nodes.items():
            camera_process.stop()


@dataclass
class CameraGroupProcessingServer(ABC):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    processing_pipeline: CameraGroupProcessingPipeline
    shutdown_event: multiprocessing.Event

    def intake_data(self, multiframe_payload: MultiFramePayload):
        self.processing_pipeline.intake_data(multiframe_payload)

    @classmethod
    def create(cls,
               processing_pipeline: CameraGroupProcessingPipeline,
               camera_shm_dtos: dict[CameraId, RingBufferCameraSharedMemoryDTO],
               shutdown_event: multiprocessing.Event):
        raise NotImplementedError("You need to re-implement this method with your pipeline's version of the CameraGroupProcessingServer "
                                  "and CameraGroupProcessingPipeline abstract base classes! See example in the `freemocap/.../dummy_pipeline.py` file.")
        # processing_pipeline = CameraGroupProcessingPipeline.create(
        #     camera_shm_dtos=camera_shm_dtos,
        #     read_type=read_type,
        #     shutdown_event=shutdown_event,
        # )
        # return cls(processing_pipeline=processing_pipeline,
        #            shutdown_event=shutdown_event)


    def start(self):
        logger.debug(f"Starting {self.__class__.__name__}...")
        self.processing_pipeline.start()

    def shutdown_pipeline(self):
        logger.debug(f"Shutting down {self.__class__.__name__}...")
        self.shutdown_event.set()
        self.processing_pipeline.shutdown()
