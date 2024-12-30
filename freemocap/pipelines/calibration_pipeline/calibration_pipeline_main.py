import logging
import multiprocessing
import time
from dataclasses import dataclass
from multiprocessing import Queue, Process
from typing import Dict

from skellycam import CameraId
from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.shmorchestrator.shared_memory.single_slot_camera_group_shared_memory import \
    CameraSharedMemoryDTOs
from skellytracker import SkellyTrackerTypes
from skellytracker.trackers.charuco_tracker.charuco_annotator import CharucoImageAnnotator

from freemocap.pipelines.calibration_pipeline.calibration_camera_node import CalibrationPipelineCameraNodeConfig, \
    CalibrationCameraNodeOutputData, CalibrationCameraNode
from freemocap.pipelines.pipeline_abcs import BasePipelineStageConfig, BasePipelineData, \
    BaseAggregationNode, BasePipelineConfig, BaseProcessingPipeline, BaseProcessingServer

logger = logging.getLogger(__name__)


class CalibrationPipelineOutputData(BasePipelineData):
    pass


class CalibrationAggregationNodeConfig(BasePipelineStageConfig):
    param2: int = 2


class CalibrationPipelineConfig(BasePipelineConfig):
    camera_node_configs: dict[CameraId, CalibrationPipelineCameraNodeConfig]
    aggregation_node_config: CalibrationAggregationNodeConfig

    @classmethod
    def create(cls, camera_configs: CameraConfigs):
        return cls(camera_node_configs={camera_id: CalibrationPipelineCameraNodeConfig(camera_config=camera_config) for
                                        camera_id, camera_config in camera_configs.items()},
                   aggregation_node_config=CalibrationAggregationNodeConfig())


class CalibrationAggregationProcessNode(BaseAggregationNode):
    @classmethod
    def create(cls,
               config: CalibrationAggregationNodeConfig,
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
    def _run(config: CalibrationAggregationNodeConfig,
             input_queues: Dict[CameraId, Queue],
             output_queue: Queue,
             shutdown_event: multiprocessing.Event):
        try:
            while not shutdown_event.is_set():
                data_by_camera_id: dict[CameraId, CalibrationCameraNode | None] = {camera_id: None for
                                                                                   camera_id in
                                                                                   input_queues.keys()}
                while any([input_queues[camera_id] is None for camera_id in input_queues.keys()]):
                    time.sleep(0.001)
                    for camera_id in input_queues.keys():
                        if data_by_camera_id[camera_id] is None:
                            if not input_queues[camera_id].empty():
                                camera_node_output = input_queues[camera_id].get()
                                if not isinstance(camera_node_output, CalibrationCameraNodeOutputData):
                                    raise ValueError(
                                        f"Unexpected data type received from camera {camera_id}: {type(camera_node_output)}")
                                if not camera_node_output.camera_id or camera_node_output.camera_id != camera_id:
                                    raise ValueError(
                                        f"Unexpected camera ID received from camera {camera_id}: {camera_node_output.camera_id}")
                                data_by_camera_id[camera_id] = camera_node_output

                if len(data_by_camera_id) == len(input_queues):
                    # TODO - process aggregated data
                    output_queue.put(CalibrationPipelineOutputData(data=data_by_camera_id))
                else:
                    raise ValueError("Not all camera data received!")
        except Exception as e:
            logger.exception(f"Error in aggregation processing node", exc_info=e)
            raise
        finally:
            logger.trace(f"Shutting down aggregation processing node")
            shutdown_event.set()


@dataclass
class CalibrationPipeline(BaseProcessingPipeline):
    config: CalibrationPipelineConfig
    camera_nodes: Dict[CameraId, CalibrationCameraNode]
    aggregation_node: CalibrationAggregationProcessNode
    annotator: CharucoImageAnnotator

    @classmethod
    def create(cls,
               config: CalibrationPipelineConfig,
               camera_shm_dtos: CameraSharedMemoryDTOs,
               shutdown_event: multiprocessing.Event):
        if not all(camera_id in camera_shm_dtos.keys() for camera_id in config.camera_node_configs.keys()):
            raise ValueError("Camera IDs provided in config not in camera shared memory DTOS!")
        camera_output_queues = {camera_id: Queue() for camera_id in camera_shm_dtos.keys()}
        aggregation_output_queue = Queue()

        return cls(config=config,
                   camera_nodes={camera_id: CalibrationCameraNode.create(config=config,
                                                                         camera_id=CameraId(camera_id),
                                                                         camera_shm_dto=camera_shm_dtos[
                                                                                       camera_id],
                                                                         output_queue=camera_output_queues[
                                                                                       camera_id],
                                                                         shutdown_event=shutdown_event)
                                 for camera_id, config in config.camera_node_configs.items()},
                   aggregation_node=CalibrationAggregationProcessNode.create(config=config.aggregation_node_config,
                                                                             input_queues=camera_output_queues,
                                                                             output_queue=aggregation_output_queue,
                                                                             shutdown_event=shutdown_event),
                   # NOTE - this `annotator` is not the same annotator as the one that will be created in the tracker, but will be able to process its outputs
                   annotator=SkellyTrackerTypes.CHARUCO.value.create().annotator,
                   shutdown_event=shutdown_event,
                   )


class CalibrationProcessingServer(BaseProcessingServer):
    processing_pipeline: CalibrationPipeline
    pipeline_config: CalibrationPipelineConfig

    @classmethod
    def create(cls,
               pipeline_config: CalibrationPipelineConfig,
               camera_shm_dtos: CameraSharedMemoryDTOs,
               shutdown_event: multiprocessing.Event):
        processing_pipeline = CalibrationPipeline.create(
            config=pipeline_config,
            camera_shm_dtos=camera_shm_dtos,
            shutdown_event=shutdown_event,
        )

        return cls(processing_pipeline=processing_pipeline,
                   shutdown_event=shutdown_event)
