import multiprocessing
import time
from multiprocessing import Queue
from typing import Dict

from skellycam import CameraId
from skellycam.core.camera_group.shmorchestrator.shared_memory.ring_buffer_camera_shared_memory import \
    RingBufferCameraSharedMemory

from freemocap.pipelines.pipeline_abcs import CameraProcessingNode, PipelineStageConfig, logger, PipelineData, \
    AggregationProcessNode, PipelineConfig, CameraGroupProcessingPipeline, CameraGroupProcessingServer


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

    @staticmethod
    def _run(config: DummyPipelineConfig,
             camera_ring_shm_dto: RingBufferCameraSharedMemory,
             output_queue: Queue,
             shutdown_event: multiprocessing.Event):
        camera_ring_shm = RingBufferCameraSharedMemory.recreate(dto=camera_ring_shm_dto,
                                                                read_only=True)
        while not shutdown_event.is_set():
            time.sleep(0.001)
            if camera_ring_shm.ready_to_read:
                image = camera_ring_shm.read()
                logger.loop(f"Processing image from camera {camera_ring_shm.camera_id}")
                # TODO - process image
                output_queue.put(PipelineData(data=image))

class DummyAggregationProcessNode(AggregationProcessNode):

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
                logger.loop(f"Processing aggregated data from cameras {data_by_camera_id.keys()}")
                # TODO - process aggregated data
                output_queue.put(PipelineData(data=data_by_camera_id))

class DummyProcessingPipeline(CameraGroupProcessingPipeline):
    config: DummyPipelineConfig
    camera_processes: Dict[CameraId, DummyCameraProcessingNode]
    aggregation_process: DummyAggregationProcessNode

class DummyProcessingServer(CameraGroupProcessingServer):
    processing_pipeline: DummyProcessingPipeline
    pipeline_config: DummyPipelineConfig
