import logging
import multiprocessing
from dataclasses import dataclass
from multiprocessing import Queue
from typing import Dict

from skellycam import CameraId
from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.shmorchestrator.shared_memory.single_slot_camera_group_shared_memory import \
    CameraSharedMemoryDTOs
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload
from skellytracker.trackers.charuco_tracker import CharucoTrackerConfig
from skellytracker.trackers.charuco_tracker.charuco_annotator import CharucoImageAnnotator, CharucoAnnotatorConfig

from freemocap.pipelines.calibration_pipeline.calibration_aggregation_node import CalibrationAggregationNodeConfig, \
    CalibrationAggregationProcessNode, CalibrationAggregationLayerOutputData, CalibrationPipelineOutputData
from freemocap.pipelines.calibration_pipeline.calibration_camera_node import CalibrationPipelineCameraNodeConfig, \
    CalibrationCameraNode, CalibrationCameraNodeOutputData
from freemocap.pipelines.pipeline_abcs import BasePipelineConfig, BaseProcessingPipeline, BaseProcessingServer, \
    PipelineImageAnnotator, BasePipelineOutputData

logger = logging.getLogger(__name__)


@dataclass
class CalibrationPipelineConfig(BasePipelineConfig):
    camera_node_configs: dict[CameraId, CalibrationPipelineCameraNodeConfig]
    aggregation_node_config: CalibrationAggregationNodeConfig

    @classmethod
    def create(cls, camera_configs: CameraConfigs, tracker_config: CharucoTrackerConfig):
        return cls(camera_node_configs={camera_id: CalibrationPipelineCameraNodeConfig(camera_config=camera_config,
                                                                                       tracker_config=tracker_config)
                                        for
                                        camera_id, camera_config in camera_configs.items()},
                   aggregation_node_config=CalibrationAggregationNodeConfig())




@dataclass
class CalibrationPipelineImageAnnotator(PipelineImageAnnotator):
    camera_node_annotators: dict[CameraId, CharucoImageAnnotator]

    @classmethod
    def create(cls, configs: dict[CameraId, CharucoAnnotatorConfig]):
        return cls(camera_node_annotators={camera_id: CharucoImageAnnotator.create(config=config)
                                           for camera_id, config in configs.items()}
                   )

    def annotate_images(self, multiframe_payload: MultiFramePayload, pipeline_output: CalibrationPipelineOutputData) -> MultiFramePayload:
        for camera_id, annotator in self.camera_node_annotators.items():
            multiframe_payload = annotator.annotate_image(multiframe_payload.frames[camera_id],
                                                          pipeline_output.camera_node_output[camera_id].charuco_observation)
        return multiframe_payload


@dataclass
class CalibrationPipeline(BaseProcessingPipeline):
    config: CalibrationPipelineConfig
    camera_nodes: Dict[CameraId, CalibrationCameraNode]
    aggregation_node: CalibrationAggregationProcessNode
    annotator: CalibrationPipelineImageAnnotator

    @classmethod
    def create(cls,
               config: CalibrationPipelineConfig,
               camera_shm_dtos: CameraSharedMemoryDTOs,
               shutdown_event: multiprocessing.Event):
        if not all(camera_id in camera_shm_dtos.keys() for camera_id in config.camera_node_configs.keys()):
            raise ValueError("Camera IDs provided in config not in camera shared memory DTOS!")
        camera_output_queues = {camera_id: Queue() for camera_id in camera_shm_dtos.keys()}
        aggregation_output_queue = Queue()

        camera_nodes = {camera_id: CalibrationCameraNode.create(config=config,
                                                                camera_id=CameraId(camera_id),
                                                                camera_shm_dto=camera_shm_dtos[
                                                                    camera_id],
                                                                output_queue=camera_output_queues[
                                                                    camera_id],
                                                                shutdown_event=shutdown_event)
                        for camera_id, config in config.camera_node_configs.items()}
        return cls(config=config,
                   camera_nodes=camera_nodes,
                   aggregation_node=CalibrationAggregationProcessNode.create(config=config.aggregation_node_config,
                                                                             input_queues=camera_output_queues,
                                                                             output_queue=aggregation_output_queue,
                                                                             shutdown_event=shutdown_event),
                   # NOTE - this `annotator` is not the same annotator as the one that will be created in the tracker, but will be able to process its outputs
                   annotator=CalibrationPipelineImageAnnotator.create(
                       configs={camera_id: config.tracker_config.annotator_config for camera_id, config in
                                config.camera_node_configs.items()}),
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
