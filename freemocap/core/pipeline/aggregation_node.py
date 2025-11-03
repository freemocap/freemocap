import logging
import multiprocessing
from dataclasses import dataclass

import numpy as np
from pydantic import BaseModel, ConfigDict
from skellycam.core.ipc.pubsub.pubsub_topics import SetShmMessage
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemory
from skellycam.core.types.type_overloads import CameraGroupIdString, CameraIdString, TopicSubscriptionQueue
from skellycam.utilities.wait_functions import wait_1ms

from freemocap.core.pipeline.pipeline_configs import PipelineConfig, AggregationNodeConfig
from freemocap.core.pipeline.pipeline_ipc import PipelineIPC
from freemocap.core.tasks.calibration_task.calibration_helpers.multi_camera_calibrator import MultiCameraCalibrator
from freemocap.core.tasks.calibration_task.point_triangulator import PointTriangulator
from freemocap.core.types.type_overloads import Point3d, PipelineIdString
from freemocap.pubsub.pubsub_topics import CameraNodeOutputMessage, PipelineConfigTopic, ProcessFrameNumberTopic, \
    ProcessFrameNumberMessage, AggregationNodeOutputMessage, AggregationNodeOutputTopic, CameraNodeOutputTopic, \
    ShouldCalibrateTopic, ShouldCalibrateMessage

logger = logging.getLogger(__name__)


class CameraNodeState(BaseModel):
    model_config = ConfigDict(
        validate_assignment=True,
        frozen=True
    )
    pipeline_id: PipelineIdString
    config: AggregationNodeConfig
    alive: bool
    last_seen_frame_number: int | None = None
    calibration_task_state: object | None = None
    mocap_task_state: object = None  # TODO - this


@dataclass
class AggregationNode:
    shutdown_self_flag: multiprocessing.Value
    worker: multiprocessing.Process

    @classmethod
    def create(cls,
               config: PipelineConfig,
               camera_group_id: CameraGroupIdString,
               subprocess_registry: list[multiprocessing.Process],
               ipc: PipelineIPC):
        shutdown_self_flag = multiprocessing.Value('b', False)
        worker = multiprocessing.Process(target=cls._run,
                                         name=f"CameraGroup-{camera_group_id}-AggregationNode",
                                         kwargs=dict(config=config,
                                                     camera_group_id=camera_group_id,
                                                     ipc=ipc,
                                                     shutdown_self_flag=shutdown_self_flag,
                                                     camera_node_subscription=ipc.pubsub.topics[
                                                         CameraNodeOutputTopic].get_subscription(),
                                                     pipeline_config_subscription=ipc.pubsub.topics[
                                                         PipelineConfigTopic].get_subscription(),
                                                     shm_subscription=ipc.shm_topic.get_subscription()
                                                     ),
                                         daemon=True
                                         )
        subprocess_registry.append(worker)
        return cls(shutdown_self_flag=shutdown_self_flag,
                   worker=worker
                   )

    @staticmethod
    def _run(config: PipelineConfig,
             camera_group_id: CameraGroupIdString,
             ipc: PipelineIPC,
             shutdown_self_flag: multiprocessing.Value,
             camera_node_subscription: TopicSubscriptionQueue,
             pipeline_config_subscription: TopicSubscriptionQueue,
             shm_subscription: TopicSubscriptionQueue,
             ):
        if multiprocessing.parent_process():
            # Configure logging if multiprocessing (i.e. if there is a parent process)
            from freemocap.system.logging_configuration.configure_logging import configure_logging
            from freemocap import LOG_LEVEL
            configure_logging(LOG_LEVEL, ws_queue=ipc.ws_queue)

        logger.debug("AggregationNode process started - waiting for SHM message")
        shm_message: SetShmMessage = shm_subscription.get(block=True)
        logger.debug("AggregationNode - received SHM message - starting main loop")
        try:
            logger.debug(f"Starting aggregation process for camera group {camera_group_id}")
            camera_node_outputs: dict[CameraIdString, CameraNodeOutputMessage | None] = {camera_id: None for camera_id
                                                                                         in
                                                                                         config.camera_configs.keys()}
            camera_group_shm = CameraGroupSharedMemory.recreate(shm_dto=shm_message.camera_group_shm_dto,
                                                                read_only=True)
            calibrator = MultiCameraCalibrator.from_camera_ids(camera_ids=config.camera_ids,
                                                               principal_camera_id=config.camera_ids[0])
            triangulator: PointTriangulator | None = None
            latest_requested_frame: int = -1
            last_received_frame: int = -1
            should_gather_observations: bool = True
            while ipc.should_continue and not shutdown_self_flag.value:
                wait_1ms()
                if camera_group_shm.latest_multiframe_number > latest_requested_frame and last_received_frame >= latest_requested_frame:
                    ipc.pubsub.topics[ProcessFrameNumberTopic].publish(
                        ProcessFrameNumberMessage(frame_number=camera_group_shm.latest_multiframe_number))
                    latest_requested_frame = camera_group_shm.latest_multiframe_number

                if should_gather_observations and calibrator.ready_to_calibrate:
                    logger.debug("Calibrator is ready to calibrate - triggering single-camera calibration")
                    should_gather_observations = False
                    ipc.pubsub.topics[ShouldCalibrateTopic].publish(ShouldCalibrateMessage())
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

                    if not triangulator and should_gather_observations:
                        calibrator.receive_camera_node_output(camera_node_output_by_camera=camera_node_outputs,
                                                              multi_frame_number=latest_requested_frame)
                        # if calibrator.ready_to_calibrate and not calibrator.has_calibration and False:
                        #     try:
                        #         print('calibrating...')
                        #         calibrator.calibrate()
                        #         print('running bundle adjustment...')
                        #         calibrator.run_bundle_adjustment()
                        #         print('creating triangulator...')
                        #         triangulator = create_triangulator_from_calibrator(calibrator)
                        #         logger.success(f"Calibration successful!")
                        #     except Exception as e:
                        #         logger.error(f"Error during calibration: {e}", exc_info=True)
                        #         raise
                    # else:
                    #     print("triangulating points...")
                    #     tik = time.perf_counter_ns()
                    #     triangulated_points3d = triangulator.triangulate_camera_node_outputs(
                    #         camera_node_outputs=camera_node_outputs,
                    #         undistort_points=False,  # fast enough for the real-time pipeline
                    #         compute_reprojection_error=False
                    #         # too slow for real-time (see diagnostics in PointTriangulator file)
                    #     )
                    #     tok = time.perf_counter_ns()
                    #     if triangulated_points3d:
                    #         logger.api(
                    #         f"Triangulated {len(triangulated_points3d)} points at frame {latest_requested_frame} in {(tok - tik) / 1e6:.3f} ms")
                    aggregation_output: AggregationNodeOutputMessage = AggregationNodeOutputMessage(
                        frame_number=latest_requested_frame,
                        pipeline_id=ipc.pipeline_id,
                        camera_group_id=camera_group_id,
                        pipeline_config=config,
                        camera_node_outputs=camera_node_outputs,
                        tracked_points3d={'fake_point': Point3d(x=np.sin(last_received_frame),
                                                                y=np.cos(last_received_frame),
                                                                z=np.cos(last_received_frame)
                                                                )}  # Placeholder for actual aggregation logic
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
