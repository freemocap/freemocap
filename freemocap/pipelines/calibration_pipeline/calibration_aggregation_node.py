import json
import logging
import multiprocessing
import time
from dataclasses import dataclass
from multiprocessing import Queue, Process
from typing import Dict

import numpy as np
from pydantic import BaseModel
from skellycam import CameraId
from tabulate import tabulate

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
class CalibrationPipelineOutputData(BasePipelineOutputData):
    camera_node_output: dict[CameraId, CalibrationCameraNodeOutputData]
    aggregation_layer_output: CalibrationAggregationLayerOutputData

    def to_serializable_dict(self):
        return {
            "camera_node_output": {camera_id: camera_node_output.to_serializable_dict() for
                                   camera_id, camera_node_output in
                                   self.camera_node_output.items()},
            "aggregation_layer_output": self.aggregation_layer_output.to_serializable_dict()
        }


@dataclass
class CalibrationAggregationNodeConfig(BasePipelineStageConfig):
    param2: int = 2


class CameraViewRecord(BaseModel):
    camera_id: CameraId
    can_see_target: bool


class SharedViewAccumulator(BaseModel):
    """
    Keeps track of the data feeds from each camera, and keeps track of the frames where each can see the calibration target,
    and counts the number of shared views each camera has with each other camera (i.e. frames where both cameras can see the target)
    """
    camera_ids: list[CameraId]
    camera_view_records_by_frame: dict[int, Dict[CameraId, CameraViewRecord]]

    @classmethod
    def create(cls, camera_ids: list[CameraId]):
        return cls(camera_ids=camera_ids, camera_view_records_by_frame={})

    @property
    def shared_views_per_camera_by_camera(self) -> dict[CameraId, dict[CameraId, int]]:
        shared_views_by_camera = {
            camera_id: {other_camera_id: 0 for other_camera_id in self.camera_ids if other_camera_id != camera_id}
            for camera_id in self.camera_ids}
        for frame_number, camera_view_records in self.camera_view_records_by_frame.items():
            for camera_id, camera_view_record in camera_view_records.items():
                for other_camera_view_record in camera_view_records.values():
                    if other_camera_view_record.camera_id == camera_id:
                        continue
                        # shared_views_by_camera[camera_id][other_camera_view_record.camera_id] += 1

                    if camera_view_records[camera_id].can_see_target and other_camera_view_record.can_see_target:
                        shared_views_by_camera[camera_id][other_camera_view_record.camera_id] += 1
        return shared_views_by_camera

    @property
    def shared_views_total_per_camera(self) -> dict[CameraId, int]:
        return {camera_id: sum(shared_views.values()) for camera_id, shared_views in
                self.shared_views_per_camera_by_camera.items()}

    def receive_camera_node_output(self, multi_frame_number: int,
                                   camera_node_output: dict[CameraId, CalibrationCameraNodeOutputData]):
        self.camera_view_records_by_frame[multi_frame_number] = {camera_id: CameraViewRecord(camera_id=camera_id,
                                                                                             can_see_target=camera_node_output.can_see_target)
                                                                 for camera_id, camera_node_output in
                                                                 camera_node_output.items()}



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
        while not all([value.is_set() for value in all_ready_events.values()]):
            time.sleep(0.001)
        logger.trace(f"All processing nodes ready!")
        camera_node_incoming_data: dict[CameraId, CalibrationCameraNodeOutputData | None] = {camera_id: None for
                                                                                             camera_id in
                                                                                             input_queues.keys()}

        shared_view_accumulator: SharedViewAccumulator = SharedViewAccumulator.create(
            camera_ids=list(input_queues.keys()))
        incoming_data: list[dict[CameraId, CalibrationCameraNodeOutputData | None]] = []
        try:

            while not shutdown_event.is_set():

                while any([queue.empty() for queue in input_queues.values()]):
                    time.sleep(0.001)
                    continue

                for camera_id in input_queues.keys():
                    camera_node_output = input_queues[camera_id].get()
                    if not isinstance(camera_node_output, CalibrationCameraNodeOutputData):
                        raise ValueError(
                            f"Unexpected data type received from camera {camera_id}: {type(camera_node_output)}")
                    camera_node_incoming_data[
                        camera_id] = camera_node_output  # type: ignore # noqa //Not sure why this is throwing a linter error, might be too many nested types are confusing the poor machine

                if any([camera_node_output is None for camera_node_output in camera_node_incoming_data.values()]):
                    logger.exception(f"Received None from camera nodes! got {camera_node_incoming_data}")
                    raise ValueError(f"Received None from camera nodes! got {camera_node_incoming_data}")

                frame_numbers = set(
                    [camera_node_output.frame_metadata.frame_number for camera_node_output in
                     camera_node_incoming_data.values()])
                if len(frame_numbers) > 1:
                    logger.exception(f"Frame numbers from camera nodes do not match! got {frame_numbers}")
                    raise ValueError(f"Frame numbers from camera nodes do not match! got {frame_numbers}")
                multi_frame_number = frame_numbers.pop()
                # Accumulate shared views
                incoming_data.append(camera_node_incoming_data)
                shared_view_accumulator.receive_camera_node_output(multi_frame_number=multi_frame_number,
                                                                   camera_node_output=camera_node_incoming_data)
                logger.trace(f"Shared view accumulator:\n {json.dumps(shared_view_accumulator.shared_views_per_camera_by_camera, indent=2)}")
                output = CalibrationPipelineOutputData(camera_node_output=camera_node_incoming_data,  # type: ignore
                                                       aggregation_layer_output=CalibrationAggregationLayerOutputData(
                                                           multi_frame_number=multi_frame_number,
                                                           points3d={f"camera_{camera_id}": (camera_id, np.sin(camera_id)*10, np.cos(camera_id)*10) for
                                                                     camera_id in input_queues.keys()},
                                                           data=shared_view_accumulator.model_dump()
                                                       )
                                                       )

                output_queue.put(output)
        except Exception as e:
            logger.exception(f"Error in aggregation processing node", exc_info=e)
            raise
        finally:
            logger.trace(f"Shutting down aggregation processing node")
            shutdown_event.set()
