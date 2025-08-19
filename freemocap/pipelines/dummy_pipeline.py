import logging
import multiprocessing
import time
from multiprocessing import Queue, Process
from typing import Dict

from skellycam.core.types.type_overloads import CameraIdString
from skellycam.core.camera.config.camera_config import CameraConfig, CameraConfigs
from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import SharedMemoryRingBufferDTO
from skellycam.core.ipc.shared_memory.frame_payload_shared_memory_ring_buffer import FramePayloadSharedMemoryRingBuffer
from freemocap.pipelines.pipeline_abcs import BaseCameraNode, BasePipelineStageConfig, BasePipelineData, \
    BaseAggregationNode, BasePipelineConfig, BaseProcessingPipeline

logger = logging.getLogger(__name__)


class DummyPipelineCameraLayerOutputData(BasePipelineData):
    data: object


class DummyPipelineAggregationLayerOutputData(BasePipelineData):
    pass

class DummyPipelineCameraNodeConfig(BasePipelineStageConfig):
    camera_config: CameraConfig
    param1: int = 1


class DummyPipelineAggregationNodeConfig(BasePipelineStageConfig):
    param2: int = 2


class DummyPipelineConfig(BasePipelineConfig):
    camera_node_configs: dict[CameraIdString, DummyPipelineCameraNodeConfig]
    aggregation_node_config: DummyPipelineAggregationNodeConfig

    @classmethod
    def create(cls, **kwargs):
        return cls(camera_node_configs={camera_id: DummyPipelineCameraNodeConfig(camera_config = camera_config) for camera_id, camera_config in camera_configs.items()},
                   aggregation_node_config=DummyPipelineAggregationNodeConfig())


class DummyCameraProcessingNode(BaseCameraNode):
    @classmethod
    def create(cls,
                pipeline_config: DummyPipelineCameraNodeConfig,
                camera_id: CameraIdString,
                camera_shm_dto: SharedMemoryRingBufferDTO,
                output_queue: Queue,
                shutdown_event: multiprocessing.Event):
        return cls(camera_id=camera_id,
                   config=config,

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
    def _run(camera_id: CameraIdString,
             config: DummyPipelineCameraNodeConfig,
             camera_shm_dto: SharedMemoryRingBufferDTO,
             output_queue: Queue,
             shutdown_event: multiprocessing.Event,
             ):
        logger.trace(f"Starting camera processing node for camera {camera_id}")
        camera_ring_shm = FramePayloadSharedMemoryRingBuffer.recreate(dto=camera_shm_dto,
                                                                         read_only=True),
        try:
            while not shutdown_event.is_set():
                time.sleep(0.001)
                if camera_ring_shm.new_frame_available:
                    frame = camera_ring_shm.retrieve_frame()
                    print(f"\t\tCamera Node for Camera#{camera_id} received frame {frame.metadata[FRAME_METADATA_MODEL.FRAME_NUMBER.value]} with image shape {frame.image.shape}")
                    # TODO - process image
                    output_queue.put(DummyPipelineCameraLayerOutputData(data=frame.metadata))
        except Exception as e:
            logger.exception(f"Error in camera processing node for camera {camera_id}", exc_info=e)
            raise
        finally:
            logger.trace(f"Shutting down camera processing node for camera {camera_id}")
            shutdown_event.set()
            camera_ring_shm.close()


class DummyAggregationProcessNode(BaseAggregationNode):
    @classmethod
    def create(cls,
               config: DummyPipelineAggregationNodeConfig,
               input_queues: dict[CameraIdString, Queue],
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
    def _run(config: DummyPipelineAggregationNodeConfig, input_queues: Dict[CameraId, Queue], output_queue: Queue,
             shutdown_event: multiprocessing.Event):
        try:
            while not shutdown_event.is_set():
                data_by_camera_id:dict[CameraId, DummyCameraProcessingNode|None] = {camera_id: None for camera_id in input_queues.keys()}
                while any([input_queues[camera_id] is None for camera_id in input_queues.keys()]):
                    time.sleep(0.001)
                    for camera_id in input_queues.keys():
                        if data_by_camera_id[camera_id] is None:
                            if not input_queues[camera_id].empty():
                                camera_node_output = input_queues[camera_id].get()
                                if not isinstance(camera_node_output, DummyPipelineCameraLayerOutputData):
                                    raise ValueError(f"Unexpected data type received from camera {camera_id}: {type(camera_node_output)}")
                                if not camera_node_output.camera_id or camera_node_output.camera_id != camera_id:
                                    raise ValueError(f"Unexpected camera ID received from camera {camera_id}: {camera_node_output.camera_id}")
                                data_by_camera_id[camera_id] = camera_node_output

                if len(data_by_camera_id) == len(input_queues):
                    # TODO - process aggregated data
                    output_queue.put(DummyPipelineAggregationLayerOutputData(data=data_by_camera_id))
                else:
                    raise ValueError("Not all camera data received!")
        except Exception as e:
            logger.exception(f"Error in aggregation processing node", exc_info=e)
            raise
        finally:
            logger.trace(f"Shutting down aggregation processing node")
            shutdown_event.set()


class DummyPipeline(BaseProcessingPipeline):
    config: DummyPipelineConfig
    camera_nodes: Dict[CameraId, DummyCameraProcessingNode]
    aggregation_node: DummyAggregationProcessNode

    @classmethod
    def create(cls,
               config: DummyPipelineConfig,
               camera_shm_dtos: CameraGroupSharedMemoryDTO,
               shutdown_event: multiprocessing.Event):
        if not all(camera_id in camera_shm_dtos.keys() for camera_id in config.camera_node_configs.keys()):
            raise ValueError("Camera IDs provided in config not in camera shared memory DTOS!")
        camera_output_queues = {camera_id: Queue() for camera_id in camera_shm_dtos.keys()}
        aggregation_output_queue = Queue()
        camera_nodes = {camera_id: DummyCameraProcessingNode.create(config=config,
                                                                    camera_id=CameraId(camera_id),
                                                                    camera_shm_dto=camera_shm_dtos[camera_id],
                                                                    output_queue=camera_output_queues[camera_id],
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


