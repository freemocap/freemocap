import logging
import multiprocessing
import time
from dataclasses import dataclass
from multiprocessing import Queue, Process
from typing import Dict

import numpy as np
from skellycam import CameraId

from freemocap.pipelines.calibration_pipeline.calibration_camera_node_output_data import CalibrationCameraNodeOutputData
from freemocap.pipelines.calibration_pipeline.multi_camera_calibrator import MultiCameraCalibrator
from freemocap.pipelines.calibration_pipeline.shared_view_accumulator import SharedViewAccumulator
from freemocap.pipelines.pipeline_abcs import BaseAggregationLayerOutputData, BasePipelineStageConfig, \
    BaseAggregationNode, BasePipelineOutputData

logger = logging.getLogger(__name__)


class CalibrationAggregationLayerOutputData(BaseAggregationLayerOutputData):
    data: object = None


class CalibrationPipelineOutputData(BasePipelineOutputData):
    camera_node_output: dict[CameraId, CalibrationCameraNodeOutputData]
    aggregation_layer_output: CalibrationAggregationLayerOutputData


class CalibrationAggregationNodeConfig(BasePipelineStageConfig):
    pass


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
        calibrated = False
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
                    camera_node_incoming_data[camera_id] = camera_node_output

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
                if multi_frame_number % 10 == 0:
                    # Accumulate shared views
                    shared_view_accumulator.receive_camera_node_output(multi_frame_number=multi_frame_number,
                                                                       camera_node_output=camera_node_incoming_data)
                    logger.trace(f"Shared view accumulator: {shared_view_accumulator.shared_view_count_by_camera}")
                    if shared_view_accumulator.all_cameras_have_min_shared_views(10) and not calibrated:
                        calibrated = True
                        multi_camera_calibrator = MultiCameraCalibrator.initialize(
                            shared_charuco_views=shared_view_accumulator.shared_target_views,
                            calibrate_cameras=True)

                radius = 5
                frequency = 0.01

                output = CalibrationPipelineOutputData(
                    camera_node_output=camera_node_incoming_data,  # type: ignore
                    aggregation_layer_output=CalibrationAggregationLayerOutputData(
                        multi_frame_number=multi_frame_number,
                        points3d={
                            camera_id: (
                                camera_id,
                                radius * np.cos(multi_frame_number * frequency) + camera_id * 5,
                                radius * np.sin(multi_frame_number * frequency) + camera_id * 5
                            )
                            for camera_id in input_queues.keys()
                        },
                        # data=shared_view_accumulator.model_dump()
                    )
                )

                output_queue.put(output)
        except Exception as e:
            logger.exception(f"Error in aggregation processing node", exc_info=e)
            raise
        finally:
            logger.trace(f"Shutting down aggregation processing node")
            shutdown_event.set()
