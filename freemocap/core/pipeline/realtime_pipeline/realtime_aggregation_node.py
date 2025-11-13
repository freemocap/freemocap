import logging
import multiprocessing
from dataclasses import dataclass

import numpy as np
from pydantic import BaseModel, ConfigDict
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemory, \
    CameraGroupSharedMemoryDTO
from skellycam.core.types.type_overloads import CameraGroupIdString, CameraIdString, TopicSubscriptionQueue
from skellycam.utilities.wait_functions import wait_1ms

from freemocap.core.pipeline.pipeline_configs import RealtimePipelineConfig
from freemocap.core.pipeline.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.posthoc_pipelines.posthoc_calibration_pipeline.calibration_helpers.charuco_observation_aggregator import \
    get_last_successful_calibration_toml_path
from freemocap.core.pipeline.posthoc_pipelines.posthoc_calibration_pipeline.calibration_helpers.freemocap_anipose import \
    AniposeCameraGroup
from freemocap.core.pipeline.posthoc_pipelines.posthoc_mocap_pipeline.mocap_helpers.triangulate_trajectory_array import \
    triangulate_frame_observations
from freemocap.core.pipeline.realtime_pipeline.realtime_tasks.calibration_task.shared_view_accumulator import \
    SharedViewAccumulator
from freemocap.core.types.type_overloads import Point3d, PipelineIdString
from freemocap.pubsub.pubsub_topics import CameraNodeOutputMessage, PipelineConfigUpdateTopic, ProcessFrameNumberTopic, \
    ProcessFrameNumberMessage, AggregationNodeOutputMessage, AggregationNodeOutputTopic, CameraNodeOutputTopic, \
    PipelineConfigUpdateMessage, ShouldCalibrateTopic

logger = logging.getLogger(__name__)


class RealtimeAggregationNodeState(BaseModel):
    model_config = ConfigDict(
        validate_assignment=True,
        frozen=True
    )
    pipeline_id: PipelineIdString
    config: RealtimePipelineConfig
    alive: bool
    last_seen_frame_number: int | None = None
    calibration_task_state: object | None = None
    mocap_task_state: object = None  # TODO - this


@dataclass
class RealtimeAggregationNode:
    shutdown_self_flag: multiprocessing.Value
    worker: multiprocessing.Process

    @classmethod
    def create(cls,
               config: RealtimePipelineConfig,
               camera_group_id: CameraGroupIdString,
               subprocess_registry: list[multiprocessing.Process],
               camera_group_shm_dto: CameraGroupSharedMemoryDTO,
               ipc: PipelineIPC):
        shutdown_self_flag = multiprocessing.Value('b', False)
        worker = multiprocessing.Process(target=cls._run,
                                         name=f"CameraGroup-{camera_group_id}-AggregationNode",
                                         kwargs=dict(config=config,
                                                     camera_group_id=camera_group_id,
                                                     ipc=ipc,
                                                     shutdown_self_flag=shutdown_self_flag,
                                                     camera_group_shm_dto=camera_group_shm_dto,
                                                     camera_node_subscription=ipc.pubsub.topics[
                                                         CameraNodeOutputTopic].get_subscription(),
                                                     pipeline_config_subscription=ipc.pubsub.topics[
                                                         PipelineConfigUpdateTopic].get_subscription(),
                                                     should_calibrate_subscription=ipc.pubsub.topics[
                                                         ShouldCalibrateTopic].get_subscription(),
                                                     ),

                                         )
        subprocess_registry.append(worker)
        return cls(shutdown_self_flag=shutdown_self_flag,
                   worker=worker
                   )

    @staticmethod
    def _run(config: RealtimePipelineConfig,
             camera_group_id: CameraGroupIdString,
             ipc: PipelineIPC,
             shutdown_self_flag: multiprocessing.Value,
             camera_group_shm_dto: CameraGroupSharedMemoryDTO,
             camera_node_subscription: TopicSubscriptionQueue,
             pipeline_config_subscription: TopicSubscriptionQueue,
             should_calibrate_subscription: TopicSubscriptionQueue
             ):
        if multiprocessing.parent_process():
            # Configure logging if multiprocessing (i.e. if there is a parent process)
            from freemocap.system.logging_configuration.configure_logging import configure_logging
            from freemocap import LOG_LEVEL
            configure_logging(LOG_LEVEL, ws_queue=ipc.ws_queue)

        logger.debug("AggregationNode  - starting main loop")
        try:
            logger.debug(f"Starting aggregation process for camera group {camera_group_id}")
            camera_node_outputs: dict[CameraIdString, CameraNodeOutputMessage | None] = {camera_id: None for camera_id
                                                                                         in
                                                                                         config.camera_configs.keys()}
            camera_group_shm = CameraGroupSharedMemory.recreate(shm_dto=camera_group_shm_dto,
                                                                read_only=True)
            shared_view_accumulator = SharedViewAccumulator.create(camera_ids=config.camera_ids)
            latest_requested_frame: int = -1
            last_received_frame: int = -1
            anipose_camera_group = AniposeCameraGroup.load(str(get_last_successful_calibration_toml_path()))
            while ipc.should_continue and not shutdown_self_flag.value:
                wait_1ms()

                # Check for updated Pipeline Config
                while not pipeline_config_subscription.empty():
                    pipeline_config_message: PipelineConfigUpdateMessage = pipeline_config_subscription.get()
                    config = pipeline_config_message.pipeline_config
                    logger.info(f"AggregationNode for camera group {camera_group_id} received updated config")

                # Check if we should request a new frame to process
                if camera_group_shm.latest_multiframe_number > latest_requested_frame and last_received_frame >= latest_requested_frame:
                    ipc.pubsub.topics[ProcessFrameNumberTopic].publish(
                        ProcessFrameNumberMessage(frame_number=camera_group_shm.latest_multiframe_number))
                    latest_requested_frame = camera_group_shm.latest_multiframe_number

                # Check for Camera Node Output
                if not camera_node_subscription.empty():
                    camera_node_output_message: CameraNodeOutputMessage = camera_node_subscription.get()
                    camera_id = camera_node_output_message.camera_id
                    if not camera_id in config.camera_configs.keys():
                        raise ValueError(
                            f"Camera ID {camera_id} not in camera IDs {list(config.camera_configs.keys())}")
                    camera_node_outputs[camera_id] = camera_node_output_message

                # Check if ready to process a frame output
                if all([isinstance(camera_node_output_message, CameraNodeOutputMessage) for camera_node_output_message
                        in
                        camera_node_outputs.values()]):
                    if not all([camera_node_output_message.frame_number == latest_requested_frame for
                                camera_node_output_message in camera_node_outputs.values()]):
                        logger.warning(
                            f"Frame numbers from tracker results do not match expected ({latest_requested_frame}) - got {[camera_node_output_message.frame_number for camera_node_output_message in camera_node_outputs.values()]}")
                    last_received_frame = latest_requested_frame

                    # shared_view_accumulator.receive_camera_node_output(
                    #     camera_node_output_by_camera=camera_node_outputs,
                    #     multi_frame_number=latest_requested_frame)
                    triangulated = triangulate_frame_observations(frame_number=latest_requested_frame,
                                                                  frame_observations_by_camera={camera_id: camera_node_outputs[camera_id].observation
                                                     for camera_id in camera_node_outputs.keys()},
                                                                  anipose_camera_group=anipose_camera_group,
                                                                  )

                    aggregation_output: AggregationNodeOutputMessage = AggregationNodeOutputMessage(
                        frame_number=latest_requested_frame,
                        pipeline_id=ipc.pipeline_id,
                        camera_group_id=camera_group_id,
                        pipeline_config=config,
                        camera_node_outputs=camera_node_outputs,
                        tracked_points3d=triangulated.to_point_dictionary()
                    )
                    ipc.pubsub.topics[AggregationNodeOutputTopic].publish(aggregation_output)
                    camera_node_outputs = {camera_id: None for camera_id in camera_node_outputs.keys()}


        except Exception as e:
            logger.error(f"Exception in AggregationNode for camera group {camera_group_id}: {e}", exc_info=True)
            ipc.kill_everything()
            raise
        finally:
            logger.debug(f"Shutting down aggregation process for camera group {camera_group_id}")

    def start(self):
        logger.debug(f"Starting AggregationNode worker")
        self.worker.start()

    def shutdown(self):
        logger.debug(f"Stopping AggregationNode worker")
        self.shutdown_self_flag.value = True
        self.worker.join()
        logger.debug(f"AggregationNode worker stopped")
