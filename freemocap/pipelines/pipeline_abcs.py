import logging
from abc import ABC, abstractmethod
from multiprocessing import Process, Queue
from typing import Dict, OrderedDict

from pydantic import BaseModel, Field
from skellycam.core import CameraId
from skellycam.core.camera_group.shmorchestrator.shared_memory.ring_buffer_camera_shared_memory import \
    RingBufferCameraSharedMemory
from skellycam.core.camera_group.shmorchestrator.shared_memory.ring_buffer_shared_memory import SharedMemoryRingBuffer, \
    SharedMemoryRingBufferDTO
from skellycam.skellycam_app.skellycam_app_state import SkellycamAppState

logger = logging.getLogger(__name__)


class PipelineStageConfig(BaseModel, ABC):
    pass


class PipelineConfig(BaseModel, ABC):
    stage_configs: Dict[str, PipelineStageConfig]


class PipelineData(BaseModel, ABC):
    data: object
    metadata: dict[object, object] = Field(default_factory=dict)


class PipelineStage(BaseModel, ABC):
    config: PipelineConfig

    @abstractmethod
    def get_output(self, input_data: PipelineData) -> PipelineData:
        pass


class PipelineModel(BaseModel, ABC):
    config: PipelineConfig
    stages: OrderedDict[str, PipelineStage]

    def process_data(self, data: PipelineData) -> PipelineData:
        logger.loop("Running pipeline")
        latest_data = data
        for stage in self.stages.values():
            logger.info(f"Running stage {stage}")
            latest_data = stage.process_input(latest_data)
        return latest_data


class CameraProcessingNode(BaseModel, ABC):
    camera_id: CameraId
    image_ring_shm: SharedMemoryRingBuffer
    process: Process
    output_queue: Queue
    config: PipelineConfig

    @classmethod
    def create(cls,
               config: PipelineConfig,
               camera_id: CameraId,
               camera_ring_shm_dto: SharedMemoryRingBufferDTO,
               input_queue: Queue,
               output_queue: Queue):
        return cls(camera_id=camera_id,
                   image_ring_shm=SharedMemoryRingBuffer.recreate(camera_ring_shm_dto,
                                                                  read_only=True),
                   input_queue=input_queue,
                   output_queue=output_queue,
                   config=config)

    def start(self):
        self.process.start()

    def stop(self):
        self.process.terminate()

    def join(self):
        self.process.join()


class AggregationProcessNode(BaseModel, ABC):
    config: PipelineConfig
    process: Process
    input_queues: Dict[CameraId, Queue]
    output_queue: Queue

    @classmethod
    def create(cls, config: PipelineConfig, input_queues: Dict[CameraId, Queue], output_queue: Queue):
        return cls(config=config,
                   input_queues=input_queues,
                   output_queue=output_queue)

    def start(self):
        self.process.start()

    def stop(self):
        self.process.terminate()

    def join(self):
        self.process.join()


class CameraGroupProcessingTree(ABC):
    camera_processes: Dict[CameraId, CameraProcessingNode]
    aggregation_process: Process
    queues_by_camera_id: Dict[CameraId, Queue]
    output_queue: Queue

    @classmethod
    def create(cls, *args, **kwargs):
        pass


class CameraGroupProcessingServer(BaseModel, ABC):
    process_tree: CameraGroupProcessingTree

    def process_data(self, data: PipelineData) -> PipelineData:
        return self.pipeline.process_data(data)


class FreeMoCapProcessingTree(CameraGroupProcessingTree):
    camera_ring_buffer_shms: Dict[CameraId, RingBufferCameraSharedMemory]

    @classmethod
    def create(cls,
               skellycam_app_state: SkellycamAppState,
               pipeline_config: PipelineConfig = PipelineConfig()):
        camera_ring_buffer_shms = skellycam_app_state.camera_ring_buffer_shms
        camera_processes = {}
        queues_by_camera_id = {}
        output_queue = Queue()
        for camera_id, camera_shm in camera_ring_buffer_shms.items():
            camera_shm_dto = camera_shm.to_dto()
            input_queue = Queue()
            camera_processes[camera_id] = CameraProcessingNode.create(config=pipeline_config,
                                                                      camera_id=camera_id,
                                                                      camera_ring_shm_dto=camera_shm_dto,
                                                                      input_queue=input_queue,
                                                                      output_queue=output_queue)
            queues_by_camera_id[camera_id] = input_queue

        aggregation_process = AggregationProcessNode.create(config=PipelineConfig(),
                                                            input_queues=queues_by_camera_id,
                                                            output_queue=Queue())

        return cls(camera_processes=camera_processes,
                   camera_ring_buffer_shms=camera_ring_buffer_shms,
                   aggregation_process=aggregation_process,
                   queues_by_camera_id=queues_by_camera_id,
                   output_queue=aggregation_process.output_queue)


class FreemocapProcessingServer(CameraGroupProcessingServer):
    @classmethod
    def create(cls, skellycam_app_state: SkellycamAppState):
        return cls(process_tree=CameraGroupProcessingTree.create(skellycam_app_state))
