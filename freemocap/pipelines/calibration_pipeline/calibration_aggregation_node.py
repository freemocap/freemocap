import logging
import multiprocessing
import time
from dataclasses import dataclass
from multiprocessing import Queue, Process
from typing import Dict

from skellycam import CameraId

from freemocap.pipelines.calibration_pipeline.calibration_camera_node import CalibrationCameraNodeOutputData
from freemocap.pipelines.pipeline_abcs import BaseAggregationLayerOutputData, BasePipelineStageConfig, \
    BaseAggregationNode, BasePipelineOutputData

logger = logging.getLogger(__name__)


@dataclass
class CalibrationAggregationLayerOutputData(BaseAggregationLayerOutputData):
    data: object = None


@dataclass
class CalibrationAggregationNodeConfig(BasePipelineStageConfig):
    param2: int = 2


@dataclass
class CalibrationPipelineOutputData(BasePipelineOutputData):
    camera_node_output: dict[CameraId, CalibrationCameraNodeOutputData]
    aggregation_layer_output: CalibrationAggregationLayerOutputData


@dataclass
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
        logger.trace(f"Aggregation processing node started!")
        try:
            while not shutdown_event.is_set():
                data_by_camera_id: dict[CameraId, CalibrationCameraNodeOutputData | None] = {camera_id: None for
                                                                                             camera_id in
                                                                                             input_queues.keys()}
                while any([value is None for value in data_by_camera_id.values()]):
                    time.sleep(0.001)
                    for camera_id in input_queues.keys():
                        if data_by_camera_id[camera_id] is None:
                            if not input_queues[camera_id].empty():
                                camera_node_output: CalibrationCameraNodeOutputData = input_queues[camera_id].get()
                                if not isinstance(camera_node_output, CalibrationCameraNodeOutputData):
                                    raise ValueError(
                                        f"Unexpected data type received from camera {camera_id}: {type(camera_node_output)}")

                                data_by_camera_id[camera_id] = camera_node_output

                if len(data_by_camera_id) == len(input_queues):
                    # TODO - process aggregated data
                    output_queue.put(CalibrationPipelineOutputData(camera_node_output=data_by_camera_id,  # type: ignore
                                                                   aggregation_layer_output=CalibrationAggregationLayerOutputData(
                                                                       data=None)
                                                                   )
                                     )
                else:
                    raise ValueError("Not all camera data received!")
        except Exception as e:
            logger.exception(f"Error in aggregation processing node", exc_info=e)
            raise
        finally:
            logger.trace(f"Shutting down aggregation processing node")
            shutdown_event.set()
