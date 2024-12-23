import multiprocessing
import time
from enum import Enum
from multiprocessing import Queue, Process
from typing import Dict

from skellycam import CameraId
from skellycam.core.camera_group.shmorchestrator.shared_memory.ring_buffer_camera_shared_memory import \
    RingBufferCameraSharedMemory, RingBufferCameraSharedMemoryDTO

from freemocap.pipelines.pipeline_abcs import CameraProcessingNode, PipelineStageConfig, logger, PipelineData, \
    AggregationProcessNode, PipelineConfig, CameraGroupProcessingPipeline, CameraGroupProcessingServer, ReadTypes


class DummyCameraPipelineConfig(PipelineStageConfig):
    param1: int = 1


class DummyAggregationProcessConfig(PipelineStageConfig):
    param2: int = 2


class DummyPipelineConfig(PipelineConfig):
    camera_node_configs: dict[CameraId, DummyCameraPipelineConfig]
    aggregation_node_config: DummyAggregationProcessConfig

    @classmethod
    def create(cls, camera_ids: list[CameraId]):
        return cls(camera_node_configs={camera_id: DummyCameraPipelineConfig() for camera_id in camera_ids},
                   aggregation_node_config=DummyAggregationProcessConfig())





class DummyCameraProcessingNode(CameraProcessingNode):
    @classmethod
    def create(cls,
               config: DummyCameraPipelineConfig,
               camera_id: CameraId,
               camera_ring_shm_dto: RingBufferCameraSharedMemoryDTO,
                output_queue: Queue,
                shutdown_event: multiprocessing.Event,
                read_type: ReadTypes = ReadTypes.LATEST_AND_INCREMENT
                ):
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

    @staticmethod
    def _run(config: DummyPipelineConfig,
             camera_ring_shm_dto: RingBufferCameraSharedMemory,
             output_queue: Queue,
             shutdown_event: multiprocessing.Event,
             read_type: ReadTypes = ReadTypes.LATEST_AND_INCREMENT
             ):
        logger.trace(f"Starting camera processing node for camera {camera_ring_shm_dto.camera_id}")
        camera_ring_shm = RingBufferCameraSharedMemory.recreate(dto=camera_ring_shm_dto,
                                                                read_only=False)
        while not shutdown_event.is_set():
            time.sleep(0.001)
            if camera_ring_shm.ready_to_read:

                if read_type == ReadTypes.LATEST_AND_INCREMENT:
                    image = camera_ring_shm.retrieve_latest_frame(increment=True)
                elif read_type == ReadTypes.LATEST_READ_ONLY:
                    image = camera_ring_shm.retrieve_latest_frame(increment=False)
                elif read_type == ReadTypes.NEXT:
                    image = camera_ring_shm.retrieve_next_frame()
                else:
                    raise ValueError(f"Invalid read_type: {read_type}")

                logger.trace(f"Processing image from camera {camera_ring_shm.camera_id}")
                # TODO - process image
                output_queue.put(PipelineData(data=image))


class DummyAggregationProcessNode(AggregationProcessNode):
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
    def _run(config: PipelineConfig, input_queues: Dict[CameraId, Queue], output_queue: Queue,
             shutdown_event: multiprocessing.Event):
        while not shutdown_event.is_set():
            data_by_camera_id = {camera_id: None for camera_id in input_queues.keys()}
            while any([input_queues[camera_id].empty() for camera_id in input_queues.keys()]):
                time.sleep(0.001)
                for camera_id in input_queues.keys():
                    if not input_queues[camera_id] is None:
                        if not input_queues[camera_id].empty():
                            data_by_camera_id[camera_id] = input_queues[camera_id].get()
            if len(data_by_camera_id) == len(input_queues):
                logger.trace(f"Processing aggregated data from cameras {data_by_camera_id.keys()}")
                # TODO - process aggregated data
                output_queue.put(PipelineData(data=data_by_camera_id))


class DummyProcessingPipeline(CameraGroupProcessingPipeline):
    config: DummyPipelineConfig
    camera_nodes: Dict[CameraId, DummyCameraProcessingNode]
    aggregation_node: DummyAggregationProcessNode

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
        camera_nodes = {camera_id: DummyCameraProcessingNode.create(config=config,
                                                                   camera_id=CameraId(camera_id),
                                                                   camera_ring_shm_dto=camera_shm_dtos[camera_id],
                                                                   output_queue=camera_output_queues[camera_id],
                                                                   read_type=read_type,
                                                                   shutdown_event=shutdown_event)
                            for camera_id, config in config.camera_node_configs.items()}
        aggregation_process = DummyAggregationProcessNode.create(config=config.aggregation_node_config,
                                                            input_queues=camera_output_queues,
                                                            output_queue=aggregation_output_queue,
                                                            shutdown_event=shutdown_event)

        return cls(config=config,
                   camera_nodes=camera_nodes,
                   aggregation_node=aggregation_process,
                   shutdown_event=shutdown_event,
                   )

class DummyProcessingServer(CameraGroupProcessingServer):
    processing_pipeline: DummyProcessingPipeline
    pipeline_config: DummyPipelineConfig

    @classmethod
    def create(cls,
               config:DummyPipelineConfig,
                camera_shm_dtos: dict[CameraId, RingBufferCameraSharedMemoryDTO],
                read_type: ReadTypes,
               shutdown_event: multiprocessing.Event):
        processing_pipeline = DummyProcessingPipeline.create(
            camera_shm_dtos=camera_shm_dtos,
            read_type=read_type,
            shutdown_event=shutdown_event,

        )

        return cls(processing_pipeline=processing_pipeline,
                   shutdown_event=shutdown_event)
