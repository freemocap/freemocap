import logging

import numpy as np
from skellycam.core.types.type_overloads import CameraIdString
from skellytracker.trackers.charuco_tracker.charuco_annotator import CharucoImageAnnotator, CharucoAnnotatorConfig

from freemocap.core.pipeline.tasks.calibration_task.calibration_aggregation_node import CalibrationPipelineOutputData
from freemocap.core.pipeline.processing_pipeline import PipelineImageAnnotator

logger = logging.getLogger(__name__)




class CalibrationPipelineImageAnnotator(PipelineImageAnnotator):
    camera_node_annotators: dict[CameraIdString, CharucoImageAnnotator]

    @classmethod
    def create(cls, configs: dict[CameraIdString, CharucoAnnotatorConfig]):
        return cls(camera_node_annotators={camera_id: CharucoImageAnnotator.create(config=config)
                                           for camera_id, config in configs.items()}
                   )

    def annotate_images(self,  mf_recarray: np.recarray,
                        pipeline_output: CalibrationPipelineOutputData) -> np.recarray:
        for camera_id, annotator in self.camera_node_annotators.items():
             mf_recarray.frames[camera_id].image = annotator.annotate_image(
                image= mf_recarray.frames[camera_id].image,
                latest_observation=pipeline_output.camera_node_output[camera_id].charuco_observation)
        return  mf_recarray

#
# @dataclass
# class CalibrationPipeline(BaseProcessingPipeline):
#     config: CalibrationPipelineConfig
#     camera_nodes: dict[CameraIdString, CalibrationCameraNode]
#     aggregation_node: CalibrationAggregationProcessNode
#     annotator: CalibrationPipelineImageAnnotator
#
#     @classmethod
#     def create(cls,
#                config: CalibrationPipelineConfig,
#                camera_shm_dtos: CameraSharedMemoryDTOs,
#                shutdown_event: multiprocessing.Event,
#                use_thread: bool = True):
#         if not all(camera_id in camera_shm_dtos.keys() for camera_id in config.camera_node_configs.keys()):
#             raise ValueError("Camera IDs provided in config not in camera shared memory DTOS!")
#         camera_output_queues = {camera_id: Queue() for camera_id in camera_shm_dtos.keys()}
#         aggregation_output_queue = Queue()
#
#         all_ready_events = {camera_id: multiprocessing.Event() for camera_id in camera_shm_dtos.keys()}
#         all_ready_events[-1] = multiprocessing.Event()
#         camera_nodes = {camera_id: CalibrationCameraNode.create(config=config,
#                                                                 camera_id=CameraIdString(camera_id),
#                                                                 camera_shm_dto=camera_shm_dtos[
#                                                                     camera_id],
#                                                                 output_queue=camera_output_queues[
#                                                                     camera_id],
#                                                                 all_ready_events=all_ready_events,
#                                                                 shutdown_event=shutdown_event,
#                                                                 use_thread=use_thread)
#                         for camera_id, config in config.camera_node_configs.items()}
#         return cls(config=config,
#                    camera_nodes=camera_nodes,
#                    aggregation_node=CalibrationAggregationProcessNode.create(config=config.aggregation_node_config,
#                                                                              input_queues=camera_output_queues,
#                                                                              output_queue=aggregation_output_queue,
#                                                                              all_ready_events=all_ready_events,
#                                                                              shutdown_event=shutdown_event,
#                                                                              use_thread=use_thread),
#                    # NOTE - this `annotator` is not the same annotator as the one that will be created in the tracker, but will be able to process its outputs
#                    annotator=CalibrationPipelineImageAnnotator.create(
#                        configs={camera_id: config.tracker_config.annotator_config for camera_id, config in
#                                 config.camera_node_configs.items()}),
#                    all_ready_events=all_ready_events,
#                    shutdown_event=shutdown_event,
#                    )
