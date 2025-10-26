import logging
import multiprocessing
import time
from dataclasses import dataclass

import numpy as np
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryDTO, \
    CameraGroupSharedMemory
from skellycam.core.types.type_overloads import CameraGroupIdString, CameraIdString, TopicSubscriptionQueue
from skellycam.utilities.wait_functions import wait_1ms

from freemocap.core.pipeline.pipeline_configs import AggregationNodeConfig
from freemocap.core.pipeline.pipeline_ipc import PipelineIPC
from freemocap.core.pubsub.pubsub_topics import CameraNodeOutputMessage, PipelineConfigTopic, ProcessFrameNumberTopic, \
    ProcessFrameNumberMessage, AggregationNodeOutputMessage, AggregationNodeOutputTopic, CameraNodeOutputTopic
from freemocap.core.tasks.calibration_task.shared_view_accumulator import SharedViewAccumulator
from freemocap.core.tasks.calibration_task.point_triangulator import PointTriangulator
from freemocap.core.tasks.calibration_task.v1_capture_volume_calibration.anipose_camera_calibration.freemocap_anipose import \
    AniposeCameraGroup, AniposeCharucoBoard, Camera
from freemocap.core.tasks.calibration_task.v1_capture_volume_calibration.charuco_observation_aggregator import \
    anipose_calibration_from_charuco_observations

from freemocap.core.types.type_overloads import Point3d
from freemocap.system.default_paths import get_default_recording_folder_path, get_default_calibration_toml_path

logger = logging.getLogger(__name__)


@dataclass
class AggregationNode:
    shutdown_self_flag: multiprocessing.Value
    worker: multiprocessing.Process

    @classmethod
    def create(cls,
               config: AggregationNodeConfig,
               camera_group_id: CameraGroupIdString,
               camera_group_shm_dto: CameraGroupSharedMemoryDTO,
               ipc: PipelineIPC):
        shutdown_self_flag = multiprocessing.Value('b', False)
        return cls(shutdown_self_flag=shutdown_self_flag,
                   worker=multiprocessing.Process(target=cls._run,
                                                  name=f"CameraGroup-{camera_group_id}-AggregationNode",
                                                  kwargs=dict(config=config,
                                                              camera_group_id=camera_group_id,
                                                              ipc=ipc,
                                                              shutdown_self_flag=shutdown_self_flag,
                                                              camera_node_subscription=ipc.pubsub.topics[
                                                                  CameraNodeOutputTopic].get_subscription(),
                                                              pipeline_config_subscription=ipc.pubsub.topics[
                                                                  PipelineConfigTopic].get_subscription(),
                                                              camera_group_shm_dto=camera_group_shm_dto,
                                                              ),
                                                  daemon=True
                                                  ),
                   )

    @staticmethod
    def _run(config: AggregationNodeConfig,
             camera_group_id: CameraGroupIdString,
             ipc: PipelineIPC,
             shutdown_self_flag: multiprocessing.Value,
             camera_node_subscription: TopicSubscriptionQueue,
             pipeline_config_subscription: TopicSubscriptionQueue,
             camera_group_shm_dto: CameraGroupSharedMemoryDTO
             ):
        if multiprocessing.parent_process():
            # Configure logging if multiprocessing (i.e. if there is a parent process)
            from freemocap.system.logging_configuration.configure_logging import configure_logging
            from freemocap import LOG_LEVEL
            configure_logging(LOG_LEVEL, ws_queue=ipc.ws_queue)
        logger.debug(f"Starting aggregation process for camera group {camera_group_id}")
        camera_node_outputs: dict[CameraIdString, CameraNodeOutputMessage | None] = {camera_id: None for camera_id in
                                                                                     config.camera_configs.keys()}
        camera_group_shm = CameraGroupSharedMemory.recreate(shm_dto=camera_group_shm_dto,
                                                                   read_only=True)
        shared_view_accumulator = SharedViewAccumulator.create(camera_ids=config.camera_ids)
        point_triangulator: PointTriangulator | None = None
        triangulated_points3d: np.ndarray | None = None
        latest_requested_frame: int = -1
        last_received_frame: int = -1
        tik:int|None = None
        tok:int|None = None
        tok2:int|None = None
        while ipc.should_continue and not shutdown_self_flag.value:
            wait_1ms()
            if camera_group_shm.latest_multiframe_number > latest_requested_frame and last_received_frame >= latest_requested_frame:
                if tik is not None:
                    raise RuntimeError("Request for new frame happened before expected")
                tik = time.perf_counter_ns()
                ipc.pubsub.topics[ProcessFrameNumberTopic].publish(
                    ProcessFrameNumberMessage(frame_number=camera_group_shm.latest_multiframe_number))
                latest_requested_frame = camera_group_shm.latest_multiframe_number
            # Check for Camera Node Output
            if not camera_node_subscription.empty():
                camera_node_output_message: CameraNodeOutputMessage = camera_node_subscription.get()
                # Process the camera node output and aggregate it
                camera_id = camera_node_output_message.camera_id
                if not camera_id in config.camera_configs.keys():
                    raise ValueError(
                        f"Camera ID {camera_id} not in camera IDs {list(config.camera_configs.keys())}")
                camera_node_outputs[camera_id] = camera_node_output_message


            # Check if ready to process a frame output
            if all([isinstance(camera_node_output_message, CameraNodeOutputMessage) for camera_node_output_message in
                        camera_node_outputs.values()]):
                if not all([camera_node_output_message.frame_number == latest_requested_frame for
                            camera_node_output_message in camera_node_outputs.values()]):
                    logger.warning(
                        f"Frame numbers from tracker results do not match expected ({latest_requested_frame}) - got {[camera_node_output_message.frame_number for camera_node_output_message in camera_node_outputs.values()]}")
                if tok is not None:
                    raise RuntimeError("tok should be None at this point")
                tok = time.perf_counter_ns()
                last_received_frame = latest_requested_frame
                if not point_triangulator:
                    shared_view_accumulator.receive_camera_node_output(camera_node_output_by_camera=camera_node_outputs,multi_frame_number=latest_requested_frame)


                    # Check if ready to calibrate
                    calibration_observations = shared_view_accumulator.get_calibration_observations_if_ready(min_shared_views=500)

                    try:
                        if calibration_observations is not None:
                            logger.info(f"Starting calibration from aggregated charuco observations at frame {latest_requested_frame}, number of frames with shared views: {len(calibration_observations)}")
                            anipose_cameras = [
                                Camera(name=cam_id,
                                       size=(config.camera_configs[cam_id].resolution.width,
                                             config.camera_configs[cam_id].resolution.height),
                                       ) for cam_id in config.camera_ids
                            ]
                            anipose_camera_group = AniposeCameraGroup(cameras=anipose_cameras)

                            anipose_charuco_board = AniposeCharucoBoard()
                            logger.info('Performing Anipose calibration from charuco observations...')
                            calibration_toml_path = get_default_calibration_toml_path()
                            logger.info(f'Saving calibration to {calibration_toml_path}')
                            triangulator = anipose_calibration_from_charuco_observations(
                                charuco_observations_by_frame=calibration_observations,
                                charuco_board=anipose_charuco_board,
                                anipose_camera_group=anipose_camera_group,
                                calibration_toml_save_path=calibration_toml_path,
                                # ... other params
                            )
                            logger.info('Anipose calibration completed and saved.')
                    except Exception as e:
                        logger.error(f"Error during calibration: {e}", exc_info=True)
                        raise
                else:
                    tik = time.perf_counter_ns()
                    triangulated_points3d = point_triangulator.triangulate_camera_node_outputs(
                        camera_node_outputs=camera_node_outputs,
                        undistort_points=True, # fast enough for the real-time pipeline
                        compute_reprojection_error=False # too slow for real-time (see diagnostics in PointTriangulator file)
                    )
                    tok  = time.perf_counter_ns()
                    logger.api(f"Triangulated {len(triangulated_points3d)} points at frame {latest_requested_frame} in {(tok - tik)/1e6:.3f} ms")
                aggregation_output: AggregationNodeOutputMessage = AggregationNodeOutputMessage(
                    frame_number=latest_requested_frame,
                    camera_group_id=camera_group_id,
                    tracked_points3d={'fake_point': Point3d(x=np.sin(last_received_frame),
                                                            y=np.cos(last_received_frame),
                                                            z=np.cos(last_received_frame)
                                                            )}  # Placeholder for actual aggregation logic
                )
                ipc.pubsub.topics[AggregationNodeOutputTopic].publish(aggregation_output)
                camera_node_outputs = {camera_id: None for camera_id in camera_node_outputs.keys()}
                if tok2 is not None:
                    raise RuntimeError("tok2 should be None at this point")
                tok2 = time.perf_counter_ns()
                logger.success(f"Aggegator node request for frame {latest_requested_frame} processed in {(tok-tik)/1e6:.2f} ms, publishing took {(tok2 - tok)/1e6:.2f} ms- shared view accumulator shared view counter by camera:  {shared_view_accumulator.get_shared_view_count_per_camera()}")
                tik = None
                tok = None
                tok2 = None
    def start(self):
        logger.debug(f"Starting AggregationNode worker")
        self.worker.start()

    def shutdown(self):
        logger.debug(f"Stopping AggregationNode worker")
        self.shutdown_self_flag.value = True
        self.worker.join()


