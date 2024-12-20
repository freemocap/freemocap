import logging
import multiprocessing
from abc import ABC, abstractmethod
from multiprocessing import Process, Queue
from typing import Dict, OrderedDict

from pydantic import BaseModel, Field, ConfigDict
from skellycam.core import CameraId
from skellycam.core.camera_group.shmorchestrator.shared_memory.ring_buffer_camera_shared_memory import \
    RingBufferCameraSharedMemory
from skellycam.core.camera_group.shmorchestrator.shared_memory.ring_buffer_shared_memory import \
    SharedMemoryRingBufferDTO
from skellycam.skellycam_app.skellycam_app_state import SkellycamAppState

logger = logging.getLogger(__name__)


class PipelineStageConfig(BaseModel, ABC):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    pass


class PipelineConfig(BaseModel, ABC):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    stage_configs: Dict[str, PipelineStageConfig] = Field(default_factory=dict)


class PipelineData(BaseModel, ABC):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    data: object
    metadata: dict[object, object] = Field(default_factory=dict)


class PipelineStage(BaseModel, ABC):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    config: PipelineConfig

    @abstractmethod
    def get_output(self, input_data: PipelineData) -> PipelineData:
        pass


class PipelineModel(BaseModel, ABC):
    model_config = ConfigDict(arbitrary_types_allowed=True)
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
    model_config = ConfigDict(arbitrary_types_allowed=True)
    camera_id: CameraId
    process: Process
    output_queue: Queue
    config: PipelineConfig

    @classmethod
    def create(cls,
               config: PipelineConfig,
               camera_id: CameraId,
               camera_ring_shm_dto: SharedMemoryRingBufferDTO,
               output_queue: Queue,
               shutdown_event: multiprocessing.Event):
        return cls(camera_id=camera_id,
                   process=Process(target=cls._run, args=(config, camera_ring_shm_dto, output_queue)),
                   config=config)

    def start(self):
        self.process.start()

    def stop(self):
        self.process.terminate()

    def join(self):
        self.process.join()

    @staticmethod
    def _run(config: PipelineConfig, camera_ring_shm_dto: SharedMemoryRingBufferDTO, output_queue: Queue):
        pass


class AggregationProcessNode(BaseModel, ABC):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    config: PipelineConfig
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

    def start(self):
        self.process.start()

    def stop(self):
        self.process.terminate()

    def join(self):
        self.process.join()

    @staticmethod
    def _run(config: PipelineConfig, input_queues: Dict[CameraId, Queue], output_queue: Queue,
             shutdown_event: multiprocessing.Event):
        pass


class CameraGroupProcessingPipeline(BaseModel, ABC):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    camera_processes: Dict[CameraId, CameraProcessingNode]
    aggregation_process: Process
    queues_by_camera_id: Dict[CameraId, Queue]
    output_queue: Queue
    shutdown_event: multiprocessing.Event

    @classmethod
    def create(cls, *args, **kwargs):
        pass

    def start(self):
        self.aggregation_process.start()
        for camera_id, camera_process in self.camera_processes.items():
            camera_process.start()

    def shutdown(self):
        self.shutdown_event.set()
        self.aggregation_process.join()
        for camera_id, camera_process in self.camera_processes.items():
            camera_process.join()

    def intake_data(self, data: PipelineData):
        for camera_id, camera_process in self.camera_processes.items():
            camera_process.intake_data(data)


class CameraGroupProcessingServer(BaseModel, ABC):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    processing_pipeline: CameraGroupProcessingPipeline
    shutdown_event: multiprocessing.Event

    def intake_data(self, data: PipelineData):
        self.processing_pipeline.intake_data(data)

    def start(self):
        self.processing_pipeline.start()

    def shutdown(self):
        self.shutdown_event.set()
        self.processing_pipeline.shutdown()

class FreemocapCameraProcessingNode(CameraProcessingNode):
    @staticmethod
    def _run(config: PipelineConfig, camera_ring_shm_dto: SharedMemoryRingBufferDTO, output_queue: Queue):
        pass

class FreemocapAggregationProcessNode(AggregationProcessNode):
    @staticmethod
    def _run(config: PipelineConfig, input_queues: Dict[CameraId, Queue], output_queue: Queue,
             shutdown_event: multiprocessing.Event):
        pass

class FreemocapPipelineConfig(PipelineConfig):
    pass

class FreemocapProcessingPipeline(CameraGroupProcessingPipeline):
    camera_ring_buffer_shms: Dict[CameraId, RingBufferCameraSharedMemory]
    shutdown_event: multiprocessing.Event

    @classmethod
    def create(cls,
               skellycam_app_state: SkellycamAppState,
               shutdown_event: multiprocessing.Event,
               pipeline_config: FreemocapPipelineConfig = FreemocapPipelineConfig()):
        if skellycam_app_state.camera_ring_buffer_shms is None:
            raise ValueError("Cannot create FreeMoCapProcessingTree without camera ring buffer SHMs!")
        camera_ring_buffer_shms = skellycam_app_state.camera_ring_buffer_shms
        camera_processes = {}
        queues_by_camera_id = {}
        output_queue = Queue()
        for camera_id, camera_shm in camera_ring_buffer_shms.items():
            camera_shm_dto = camera_shm.to_dto()
            camera_output_queue = Queue()
            camera_processes[camera_id] = CameraProcessingNode.create(config=pipeline_config,
                                                                      camera_id=camera_id,
                                                                      camera_ring_shm_dto=camera_shm_dto,
                                                                      output_queue=camera_output_queue,
                                                                      shutdown_event=shutdown_event,
                                                                      )
            queues_by_camera_id[camera_id] = camera_output_queue

        aggregation_process = AggregationProcessNode.create(config=PipelineConfig(),
                                                            input_queues=queues_by_camera_id,
                                                            output_queue=output_queue,
                                                            shutdown_event=shutdown_event,
                                                            )

        return cls(camera_processes=camera_processes,
                   camera_ring_buffer_shms=camera_ring_buffer_shms,
                   aggregation_process=aggregation_process,
                   queues_by_camera_id=queues_by_camera_id,
                   output_queue=aggregation_process.output_queue,
                   shutdown_event=shutdown_event,
                   )


class FreemocapProcessingServer(CameraGroupProcessingServer):
    @classmethod
    def create(cls,
               skellycam_app_state: SkellycamAppState):
        shutdown_event = multiprocessing.Event()
        return cls(processing_pipeline=FreemocapProcessingPipeline.create(skellycam_app_state=skellycam_app_state,
                                                                          shutdown_event=shutdown_event),
                   shutdown_event=shutdown_event,
                   )
