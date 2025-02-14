import logging
import multiprocessing
import time
from dataclasses import dataclass
from multiprocessing import Queue, Process
from threading import Thread
from typing import Dict

import numpy as np
from skellycam import CameraId

from freemocap.pipelines.calibration_pipeline.calibration_camera_node_output_data import CalibrationCameraNodeOutputData
from freemocap.pipelines.calibration_pipeline.multi_camera_calibrator import MultiCameraCalibrator, \
    MultiCameraCalibrationEstimate
from freemocap.pipelines.pipeline_abcs import BaseAggregationLayerOutputData, BasePipelineStageConfig, \
    BaseAggregationNode, BasePipelineOutputData

logger = logging.getLogger(__name__)


class CalibrationAggregationLayerOutputData(BaseAggregationLayerOutputData):
    multi_camera_calibration_estimate: MultiCameraCalibrationEstimate | None = None
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
               shutdown_event: multiprocessing.Event,
               use_thread: bool = False):

        if use_thread:
            worker = Thread(target=cls._run,
                            kwargs=dict(config=config,
                                        input_queues=input_queues,
                                        output_queue=output_queue,
                                        all_ready_events=all_ready_events,
                                        shutdown_event=shutdown_event)
                            )
        else:
            worker = Process(target=cls._run,
                             kwargs=dict(config=config,
                                         input_queues=input_queues,
                                         output_queue=output_queue,
                                         all_ready_events=all_ready_events,
                                         shutdown_event=shutdown_event)
                             )
        return cls(config=config,
                   process=worker,
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

        multi_camera_calibrator = MultiCameraCalibrator.from_camera_ids(camera_ids=list(input_queues.keys()))
        try:

            while not shutdown_event.is_set():

                if any([queue.empty() for queue in input_queues.values()]):
                    time.sleep(0.001)
                    continue

                for camera_id in input_queues.keys():
                    camera_node_output = input_queues[camera_id].get()
                    if not isinstance(camera_node_output, CalibrationCameraNodeOutputData):
                        raise ValueError(
                            f"Unexpected data type received from camera {camera_id}: {type(camera_node_output)}")
                    camera_node_incoming_data[camera_id] = camera_node_output

                frame_numbers = set(
                    [camera_node_output.frame_metadata.frame_number for camera_node_output in
                     camera_node_incoming_data.values()])
                if len(frame_numbers) > 1:
                    raise ValueError(f"Frame numbers from camera nodes do not match! got {frame_numbers}")
                multi_frame_number = frame_numbers.pop()

                if not multi_camera_calibrator.has_calibration:

                    if multi_frame_number % 5 == 0:
                        # Accumulate shared views
                        multi_camera_calibrator.receive_camera_node_output(multi_frame_number=multi_frame_number,
                                                                           camera_node_output_by_camera=camera_node_incoming_data)
                        if multi_camera_calibrator.all_cameras_have_min_shared_views() and not multi_camera_calibrator.has_calibration:
                            multi_camera_calibrator.calibrate()
                else:
                    logger.info("Do triangulation and stuff with the calibration data")
                radius = 1
                frequency = 0.1

                points3d = {
                    camera_id: (
                        radius * np.cos(multi_frame_number * frequency) + camera_id,
                        camera_id,
                        radius * np.sin(multi_frame_number * frequency) + camera_id
                    )
                    for camera_id in input_queues.keys()
                }
                if multi_camera_calibrator.has_calibration:
                    for camera_id, transform in multi_camera_calibrator.multi_camera_calibration_estimate.camera_transforms_by_camera_id.items():
                        points3d[f"camera-{camera_id}"] = transform.translation_vector.vector

                output = CalibrationPipelineOutputData(
                    camera_node_output=camera_node_incoming_data,  # type: ignore
                    aggregation_layer_output=CalibrationAggregationLayerOutputData(
                        multi_frame_number=multi_frame_number,
                        multi_camera_calibration_estimate=multi_camera_calibrator.multi_camera_calibration_estimate,
                        points3d=points3d,
                    )
                )

                output_queue.put(output)
        except Exception as e:
            logger.exception(f"Error in aggregation processing node", exc_info=e)
            raise
        finally:
            logger.trace(f"Shutting down aggregation processing node")
            shutdown_event.set()
