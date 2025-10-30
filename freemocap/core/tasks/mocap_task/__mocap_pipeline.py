import logging
import multiprocessing
from dataclasses import dataclass
from multiprocessing import Queue
from typing import Dict

from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.shmorchestrator.shared_memory.single_slot_camera_group_shared_memory import \
    CameraSharedMemoryDTOs
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload
from skellytracker.trackers.mediapipe_tracker import MediapipeTrackerConfig
from skellytracker.trackers.mediapipe_tracker.mediapipe_annotator import MediapipeImageAnnotator, \
    MediapipeAnnotatorConfig

from freemocap.core.pipeline.processing_pipeline import BasePipelineConfig, PipelineImageAnnotator, \
    BaseProcessingPipeline
from freemocap.core.tasks.mocap_task.mocap_aggregation_node import MocapAggregationNodeConfig, \
    MocapPipelineOutputData, MocapAggregationProcessNode
from freemocap.core.tasks.mocap_task.mocap_camera_node import MocapPipelineCameraNodeConfig, MocapCameraNode

logger = logging.getLogger(__name__)


@dataclass
class MocapPipelineConfig(BasePipelineConfig):
    camera_node_configs: dict[CameraId, MocapPipelineCameraNodeConfig]
    aggregation_node_config: MocapAggregationNodeConfig

    @classmethod
    def create(cls, camera_configs: CameraConfigs, tracker_config: MediapipeTrackerConfig):
        return cls(camera_node_configs={camera_id: MocapPipelineCameraNodeConfig(camera_config=camera_config,
                                                                                 tracker_config=tracker_config)
                                        for camera_id, camera_config in camera_configs.items()},
                   aggregation_node_config=MocapAggregationNodeConfig())


class MocapPipelineImageAnnotator(PipelineImageAnnotator):
    camera_node_annotators: dict[CameraId, MediapipeImageAnnotator]

    @classmethod
    def create(cls, configs: dict[CameraId, MediapipeAnnotatorConfig]):
        return cls(camera_node_annotators={camera_id: MediapipeImageAnnotator.create(config=config)
                                           for camera_id, config in configs.items()}
                   )

    def annotate_images(self, multiframe_payload: MultiFramePayload,
                        pipeline_output: MocapPipelineOutputData) -> MultiFramePayload:
        for camera_id, annotator in self.camera_node_annotators.items():
            multiframe_payload.frames[camera_id].image = annotator.annotate_image(
                image=multiframe_payload.frames[camera_id].image,
                latest_observation=pipeline_output.camera_node_output[camera_id].mediapipe_observation)
        return multiframe_payload


class MocapPipeline(BaseProcessingPipeline):
    config: MocapPipelineConfig
    camera_nodes: Dict[CameraId, MocapCameraNode]
    aggregation_node: MocapAggregationProcessNode
    annotator: MocapPipelineImageAnnotator

    @classmethod
    def create(cls,
               config: MocapPipelineConfig,
               camera_shm_dtos: CameraSharedMemoryDTOs,
               shutdown_event: multiprocessing.Event):
        if not all(camera_id in camera_shm_dtos.keys() for camera_id in config.camera_node_configs.keys()):
            raise ValueError("Camera IDs provided in config not in camera shared memory DTOS!")
        camera_output_queues = {camera_id: Queue() for camera_id in camera_shm_dtos.keys()}
        aggregation_output_queue = Queue()

        all_ready_events = {camera_id: multiprocessing.Event() for camera_id in camera_shm_dtos.keys()}
        all_ready_events[-1] = multiprocessing.Event()
        camera_nodes = {camera_id: MocapCameraNode.create(config=config,
                                                          camera_id=CameraId(camera_id),
                                                          camera_shm_dto=camera_shm_dtos[
                                                              camera_id],
                                                          output_queue=camera_output_queues[
                                                              camera_id],
                                                          all_ready_events=all_ready_events,
                                                          shutdown_event=shutdown_event)
                        for camera_id, config in config.camera_node_configs.items()}
        return cls(config=config,
                   camera_nodes=camera_nodes,
                   aggregation_node=MocapAggregationProcessNode.create(config=config.aggregation_node_config,
                                                                       input_queues=camera_output_queues,
                                                                       output_queue=aggregation_output_queue,
                                                                       all_ready_events=all_ready_events,
                                                                       shutdown_event=shutdown_event),
                   # NOTE - this `annotator` is not the same annotator as the one that will be created in the tracker, but will be able to process its outputs
                   annotator=MocapPipelineImageAnnotator.create(
                       configs={camera_id: config.tracker_config.annotator_config for camera_id, config in
                                config.camera_node_configs.items()}),
                   all_ready_events=all_ready_events,
                   shutdown_event=shutdown_event,
                   )
