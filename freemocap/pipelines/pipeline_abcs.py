import asyncio
import logging
import multiprocessing
from abc import ABC, abstractproperty, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from multiprocessing import Process, Queue

from skellycam.core import CameraId
from skellycam.core.camera_group.shmorchestrator.shared_memory.single_slot_camera_group_shared_memory import \
    SingleSlotCameraSharedMemory
from skellycam.core.camera_group.shmorchestrator.shared_memory.single_slot_camera_shared_memory import \
    CameraSharedMemoryDTO
from skellycam.core.frames.payloads.frame_payload import FramePayload
from skellycam.core.frames.payloads.metadata.frame_metadata import FrameMetadata
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload
from skellytracker.trackers.base_tracker.base_tracker import BaseTrackerConfig, BaseImageAnnotator, \
    BaseImageAnnotatorConfig

logger = logging.getLogger(__name__)


class ReadTypes(str, Enum):
    LATEST = "latest"
    NEXT = "next"

@dataclass
class BasePipelineData( ABC):
    pass

@dataclass
class BaseAggregationLayerOutputData(BasePipelineData):
    multi_frame_number: int
    points3d: dict[str, tuple]

    def to_serializable_dict(self):
        return {"multi_frame_number": self.multi_frame_number, "points3d": self.points3d}

@dataclass
class BaseCameraNodeOutputData(BasePipelineData):
    frame_metadata: FrameMetadata
    time_to_retrieve_frame_ns: int
    time_to_process_frame_ns: int

@dataclass
class BasePipelineOutputData(ABC):
    camera_node_output: dict[CameraId, BaseCameraNodeOutputData]
    aggregation_layer_output: BaseAggregationLayerOutputData

    @property
    def multi_frame_number(self) -> int:
        frame_numbers = [camera_node_output.frame_metadata.frame_number for camera_node_output in self.camera_node_output.values()]
        if len(set(frame_numbers)) > 1:
            raise ValueError(f"Frame numbers from camera nodes do not match - got {frame_numbers}")
        return frame_numbers[0]

    @abstractmethod
    def to_serializable_dict(self):
        pass

@dataclass
class BasePipelineStageConfig( ABC):
    pass

@dataclass
class BasePipelineConfig( ABC):
    camera_node_configs: dict[CameraId, BasePipelineStageConfig] = field(default_factory=dict)
    aggregation_node_config: BasePipelineStageConfig = field(default_factory=BasePipelineStageConfig)

    @classmethod
    def create(cls, camera_ids: list[CameraId], tracker_config: BaseTrackerConfig):
        return cls(camera_node_configs={camera_id: BasePipelineStageConfig() for camera_id in camera_ids},
                   aggregation_node_config=BasePipelineStageConfig())


@dataclass
class BaseCameraNode(ABC):
    config: BasePipelineStageConfig
    camera_id: CameraId
    incoming_frame_shm: SingleSlotCameraSharedMemory

    process: Process
    all_ready_events: dict[CameraId, multiprocessing.Event]
    shutdown_event: multiprocessing.Event

    @classmethod
    def create(cls,
               config: BasePipelineStageConfig,
               camera_id: CameraId,
               incoming_frame_shm_dto: CameraSharedMemoryDTO,
               output_queue: Queue,
               all_ready_events: dict[CameraId, multiprocessing.Event],
               shutdown_event: multiprocessing.Event):
        raise NotImplementedError(
            "You need to re-implement this method with your pipeline's version of the CameraProcessingNode "
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
        self.incoming_frame_shm.put_frame(frame_payload.image, frame_payload.metadata)

    @staticmethod
    def _run(camera_id: CameraId,
             config: BasePipelineStageConfig,
             incoming_frame_shm_dto: CameraSharedMemoryDTO,
             output_queue: Queue,
             all_ready_events: dict[CameraId, multiprocessing.Event],
             shutdown_event: multiprocessing.Event):
        raise NotImplementedError(
            "Add your camera process logic here! See example in the `freemocap/.../dummy_pipeline.py` file.")
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
class BaseAggregationNode(ABC):
    config: BasePipelineStageConfig
    process: Process
    input_queues: dict[CameraId, Queue]
    output_queue: Queue
    shutdown_event: multiprocessing.Event

    @classmethod
    def create(cls,
               config: BasePipelineStageConfig,
               input_queues: dict[CameraId, Queue],
               output_queue: Queue,
               all_ready_events: dict[CameraId|str, multiprocessing.Event],
               shutdown_event: multiprocessing.Event):
        raise NotImplementedError(
            "You need to re-implement this method with your pipeline's version of the AggregationProcessNode "
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
    def _run(config: BasePipelineStageConfig,
             input_queues: dict[CameraId, Queue],
             output_queue: Queue,
             all_ready_events: dict[CameraId | str, multiprocessing.Event],
        shutdown_event: multiprocessing.Event):
        raise NotImplementedError(
            "Add your aggregation process logic here! See example in the `freemocap/.../dummy_pipeline.py` file.")
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
class PipelineImageAnnotator(ABC):
    camera_node_annotators: dict[CameraId, BaseImageAnnotator]

    @classmethod
    def create(cls, configs: dict[CameraId, BaseImageAnnotatorConfig]):
        raise NotImplementedError(
            "You need to re-implement this method with your pipeline's version of the PipelineImageAnnotator ")

    def annotate_images(self, multiframe_payload: MultiFramePayload, pipeline_output: BasePipelineOutputData) -> MultiFramePayload:
        raise NotImplementedError(
            "You need to re-implement this method with your pipeline's version of the PipelineImageAnnotator ")

@dataclass
class BaseProcessingPipeline(ABC):
    config: BasePipelineStageConfig
    camera_nodes: dict[CameraId, BaseCameraNode]
    aggregation_node: BaseAggregationNode
    annotator: PipelineImageAnnotator
    shutdown_event: multiprocessing.Event
    all_ready_events: dict[CameraId|str, multiprocessing.Event]

    latest_pipeline_data: BasePipelineData | None = None

    @property
    def alive(self  ):
        return all([camera_node.process.is_alive() for camera_node in self.camera_nodes.values()]) and self.aggregation_node.process.is_alive()

    @property
    def nodes_ready(self):
        return all(value.is_set() for value in self.all_ready_events.values())

    @property
    def ready_to_intake(self):
        return self.alive and self.nodes_ready

    @classmethod
    def create(cls,
               config: BasePipelineStageConfig,
               camera_shm_dtos: dict[CameraId, CameraSharedMemoryDTO],
               shutdown_event: multiprocessing.Event,
               ):
        raise NotImplementedError(
            "You need to re-implement this method with your pipeline's version of the CameraGroupProcessingPipeline "
            "and CameraProcessingNode abstract base classes! See example in the `freemocap/.../dummy_pipeline.py` file.")
        # if not all(camera_id in camera_shm_dtos.keys() for camera_id in config.camera_node_configs.keys()):
        #     raise ValueError("Camera IDs provided in config not in camera shared memory DTOS!")
        # camera_output_queues = {camera_id: Queue() for camera_id in camera_shm_dtos.keys()}
        # aggregation_output_queue = Queue()
        # self._annotator = SkellyTrackerTypes.DUMMY.create().annotator # Returns annotator for dummy tracker, NOT the same one that will be created in the camera/nodes, but will be able to process their output
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

    async def process_multiframe_payload(self, multiframe_payload: MultiFramePayload, annotate_images: bool = True) -> tuple[MultiFramePayload, BasePipelineOutputData]:
        self.intake_data(multiframe_payload)
        pipeline_output = await self.get_next_data_async()
        if not multiframe_payload.multi_frame_number == pipeline_output.multi_frame_number:
            raise ValueError(f"Frame number mismatch: {multiframe_payload.multi_frame_number} != {pipeline_output.multi_frame_number}")
        annotated_payload = self.annotate_images(multiframe_payload, pipeline_output)
        return annotated_payload, pipeline_output


    def intake_data(self, multiframe_payload: MultiFramePayload):
        if not self.ready_to_intake:
            raise ValueError("Pipeline not ready to intake data!")
        if not all(camera_id in self.camera_nodes.keys() for camera_id in multiframe_payload.camera_ids):
            raise ValueError("Data provided for camera IDs not in camera processes!")
        for camera_id, frame_payload in multiframe_payload.frames.items():
            if not frame_payload.frame_number == multiframe_payload.multi_frame_number:
                raise ValueError(f"Frame number mismatch: {frame_payload.frame_number} != {multiframe_payload.multi_frame_number}")
            self.camera_nodes[camera_id].intake_data(frame_payload)

    def get_next_data(self) -> BasePipelineOutputData | None:
        if self.aggregation_node.output_queue.empty():
            return None
        data = self.aggregation_node.output_queue.get()
        return data

    async def get_next_data_async(self) -> BasePipelineOutputData:
        while self.aggregation_node.output_queue.empty():
            await asyncio.sleep(0.001)
        data = self.aggregation_node.output_queue.get()
        return data

    def get_latest_data(self) -> BasePipelineOutputData | None:
        while not self.aggregation_node.output_queue.empty():
            self.latest_pipeline_data = self.aggregation_node.output_queue.get()

        return self.latest_pipeline_data

    def get_output_for_frame(self, target_frame_number:int) -> BasePipelineOutputData | None:
        while not self.aggregation_node.output_queue.empty():
            self.latest_pipeline_data:BasePipelineOutputData = self.aggregation_node.output_queue.get()
            print(f"Frame Annotator got data for frame {self.latest_pipeline_data.multi_frame_number}")
            if self.latest_pipeline_data.multi_frame_number > target_frame_number:
                raise ValueError(f"We missed the target frame number {target_frame_number} - current output is for frame {self.latest_pipeline_data.multi_frame_number}")

            if self.latest_pipeline_data.multi_frame_number == target_frame_number:
                return self.latest_pipeline_data


    def annotate_images(self, multiframe_payload: MultiFramePayload,
                        pipeline_output:BasePipelineOutputData|None) -> MultiFramePayload:
        if pipeline_output is None:
            return multiframe_payload
        return self.annotator.annotate_images(multiframe_payload, pipeline_output)



    def start(self):
        logger.debug(f"Starting {self.__class__.__name__} with camera processes {list(self.camera_nodes.keys())}...")
        self.aggregation_node.start()
        for camera_id, camera_node in self.camera_nodes.items():
            camera_node.start()

    def shutdown(self):
        logger.debug(f"Shutting down {self.__class__.__name__}...")
        self.shutdown_event.set()
        self.aggregation_node.stop()
        for camera_id, camera_process in self.camera_nodes.items():
            camera_process.stop()



