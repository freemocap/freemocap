import logging
import multiprocessing
import time
from dataclasses import dataclass
from multiprocessing import Queue, Process
from typing import Dict

from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.pipeline.aggregation_node import AggregationNode
from freemocap.core.pipeline.processing_pipeline import BaseAggregationLayerOutputData, BasePipelineStageConfig, \
    BasePipelineOutputData
from freemocap.core.tasks.mocap_task.mocap_camera_node import MocapCameraNodeOutputData
from freemocap.core.tasks.mocap_task.old_point_trangulator import PointTriangulator

logger = logging.getLogger(__name__)


@dataclass
class MocapAggregationLayerOutputData(BaseAggregationLayerOutputData):
    pass


@dataclass
class MocapAggregationNodeConfig(BasePipelineStageConfig):
    param2: int = 2


class MocapPipelineOutputData(BasePipelineOutputData):
    camera_node_output: dict[CameraId, MocapCameraNodeOutputData]
    aggregation_layer_output: MocapAggregationLayerOutputData


class MocapAggregationProcessNode(AggregationNode):
    @classmethod
    def create(cls,
               config: MocapAggregationNodeConfig,
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
    def _run(config: MocapAggregationNodeConfig,
             input_queues: Dict[CameraId, Queue],
             output_queue: Queue,
             all_ready_events: dict[CameraId | str, multiprocessing.Event],
             shutdown_event: multiprocessing.Event):
        all_ready_events[-1].set()
        logger.trace(f"Aggregation processing node ready!")
        point_triangulator = PointTriangulator.create()
        while not all([value.is_set() for value in all_ready_events.values()]):
            time.sleep(0.001)
        logger.trace(f"All processing nodes ready!")
        try:
            camera_node_incoming_data: dict[CameraId, MocapCameraNodeOutputData | None] = {camera_id: None for
                                                                                           camera_id in
                                                                                           input_queues.keys()}

            while not shutdown_event.is_set():

                while any([queue.empty() for queue in input_queues.values()]):
                    time.sleep(0.001)
                    continue

                for camera_id in input_queues.keys():
                    camera_node_output = input_queues[camera_id].get()
                    if not isinstance(camera_node_output, MocapCameraNodeOutputData):
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
                latest_frame_number = frame_numbers.pop()

                # TODO: Fix triangulation, until then just return the single camera 3d estimates
                # points2d_by_camera = {camera_id: camera_node_output.mediapipe_observation.all_points(dimensions=2) for
                #                       camera_id, camera_node_output in camera_node_incoming_data.items()}
                # points3d: dict[str, tuple] = point_triangulator.triangulate(points2d_by_camera=points2d_by_camera,
                #                                                             scale_by=0.001)

                points3d = {}
                for camera_id, camera_node_output in camera_node_incoming_data.items():
                    if camera_node_output is None:
                        raise ValueError(f"Camera {camera_id} did not send any data!")

                    points3d.update({f"Cam{camera_id}.{name}": tuple(point_xyz) for name, point_xyz in
                                     camera_node_output.mediapipe_observation.all_points(dimensions=3,
                                                                                         scale_by=0.001).items()})

                output = MocapPipelineOutputData(camera_node_output=camera_node_incoming_data,  # type: ignore
                                                 aggregation_layer_output=MocapAggregationLayerOutputData(
                                                     multi_frame_number=latest_frame_number,
                                                     points3d=points3d)
                                                 )

                output_queue.put(output)
        except Exception as e:
            logger.exception(f"Error in aggregation processing node", exc_info=e)
            raise
        finally:
            logger.trace(f"Shutting down aggregation processing node")
            shutdown_event.set()
