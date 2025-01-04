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
    def to_serializable_dict(self):
        return {"data": self.data}

@dataclass
class CalibrationAggregationNodeConfig(BasePipelineStageConfig):
    param2: int = 2


@dataclass
class CalibrationPipelineOutputData(BasePipelineOutputData):
    camera_node_output: dict[CameraId, CalibrationCameraNodeOutputData]
    aggregation_layer_output: CalibrationAggregationLayerOutputData

    def to_serializable_dict(self):
        return {
            "camera_node_output": {camera_id: camera_node_output.to_serializable_dict() for camera_id, camera_node_output in
                                   self.camera_node_output.items()},
            "aggregation_layer_output": self.aggregation_layer_output.to_serializable_dict()
        }


@dataclass
class CalibrationAggregationProcessNode(BaseAggregationNode):
    @classmethod
    def create(cls,
               config: CalibrationAggregationNodeConfig,
               input_queues: dict[CameraId, Queue],
               output_queue: Queue,
               all_ready_events: dict[CameraId | str, multiprocessing.Event],
               shutdown_event: multiprocessing.Event):
        return cls(config=config,
                   process=Process(target=cls._run,
                                   kwargs=dict(config=config,
                                               input_queues=input_queues,
                                               output_queue=output_queue,
                                               all_ready_events=all_ready_events,
                                               shutdown_event=shutdown_event)
                                   ),
                   input_queues=input_queues,
                   output_queue=output_queue,
                   shutdown_event=shutdown_event)

    @staticmethod
    def _run(config: CalibrationAggregationNodeConfig,
             input_queues: Dict[CameraId, Queue],
             output_queue: Queue,
             all_ready_events: dict[CameraId | str, multiprocessing.Event],
             shutdown_event: multiprocessing.Event):
        all_ready_events[-1].set()
        logger.trace(f"Aggregation processing node ready!")
        try:
            camera_node_incoming_data: dict[CameraId, CalibrationCameraNodeOutputData | None] = {camera_id: None for
                                                                                                 camera_id in
                                                                                                 input_queues.keys()}

            while not all([value.is_set() for value in all_ready_events.values()]):
                time.sleep(0.001)

            while not shutdown_event.is_set():

                while any([queue.empty() for queue in input_queues.values()]):
                    time.sleep(0.001)
                    continue

                for camera_id in input_queues.keys():
                    camera_node_output = input_queues[camera_id].get()
                    if not isinstance(camera_node_output, CalibrationCameraNodeOutputData):
                        raise ValueError(
                            f"Unexpected data type received from camera {camera_id}: {type(camera_node_output)}")
                    camera_node_incoming_data[camera_id] = camera_node_output

                print(f"Aggregation node received data from camera nodes: {[(camera_id, value.frame_metadata.frame_number) for camera_id, value in camera_node_incoming_data.items()]}")
                frame_numbers = set(
                    [camera_node_output.frame_metadata.frame_number for camera_node_output in
                     camera_node_incoming_data.values()])
                if len(frame_numbers) > 1:
                    logger.exception(f"Frame numbers from camera nodes do not match! got {frame_numbers}")
                    raise ValueError(f"Frame numbers from camera nodes do not match! got {frame_numbers}")
                latest_frame_number = frame_numbers.pop()
                # TODO - add aggregation logic here
                output= CalibrationPipelineOutputData(camera_node_output=camera_node_incoming_data,  # type: ignore
                                              aggregation_layer_output=CalibrationAggregationLayerOutputData(
                                                  data={"multi_frame_number": latest_frame_number}
                                              )
                                                )

                print(f"Aggregation node output for frame {latest_frame_number}: mf_number: {output.multi_frame_number}")
                output_queue.put(output)
        except Exception as e:
            logger.exception(f"Error in aggregation processing node", exc_info=e)
            raise
        finally:
            logger.trace(f"Shutting down aggregation processing node")
            shutdown_event.set()
