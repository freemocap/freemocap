import multiprocessing
from abc import ABC
from dataclasses import dataclass

from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryDTO, \
    CameraGroupSharedMemoryManager
from skellycam.core.types.type_overloads import CameraGroupIdString, WorkerType, CameraIdString, WorkerStrategy, \
    TopicSubscriptionQueue
from skellycam.utilities.wait_functions import wait_1ms
from skellytracker.trackers.base_tracker.base_tracker_abcs import TrackerTypeString

from freemocap.core.pipeline.pipeline_ipc import PipelineIPC
from freemocap.core.pubsub.pubsub_topics import CameraNodeOutputMessage, PipelineConfigTopic, ProcessFrameNumberTopic, \
    ProcessFrameNumberMessage, AggregationNodeOutputMessage, AggregationNodeOutputTopic, LogsTopic

logger = multiprocessing.get_logger()

@dataclass
class AggregationNode(ABC):
    camera_group_id: CameraGroupIdString
    shutdown_self_flag: multiprocessing.Value
    worker: WorkerType

    @classmethod
    def create(cls,
               camera_group_id: CameraGroupIdString,
               camera_ids: list[CameraIdString],
               camera_group_shm_dto: CameraGroupSharedMemoryDTO,
               ipc: PipelineIPC,
               worker_strategy: WorkerStrategy):
        shutdown_self_flag = multiprocessing.Value('b', False)
        return cls(camera_group_id=camera_group_id,
                   shutdown_self_flag=shutdown_self_flag,
                   worker=worker_strategy.value(target=cls._run,
                                                name=f"CameraGroup-{camera_group_id}-AggregationNode",
                                                kwargs=dict(camera_group_id=camera_group_id,
                                                            camera_ids=camera_ids,
                                                            ipc=ipc,
                                                            shutdown_self_flag=shutdown_self_flag,
                                                            camera_node_subscription=ipc.pubsub.topics[CameraNodeOutputMessage].get_subscription(),
                                                            pipeline_config_subscription=ipc.pubsub.topics[PipelineConfigTopic].get_subscription(),
                                                            camera_group_shm_dto=camera_group_shm_dto,
                                                            ),
                                                daemon=True
                                                ),
                   )

    @staticmethod
    def _run(camera_group_id: CameraGroupIdString,
             camera_ids: list[CameraIdString],
             ipc: PipelineIPC,
             shutdown_self_flag: multiprocessing.Value,
             camera_node_subscription: TopicSubscriptionQueue,
             skellytracker_configs_subscription: TopicSubscriptionQueue,
             camera_group_shm_dto: CameraGroupSharedMemoryDTO
             ):
        if multiprocessing.parent_process():
            # Configure logging if multiprocessing (i.e. if there is a parent process)
            from freemocap.system.logging_configuration.configure_logging import configure_logging
            from freemocap import LOG_LEVEL
            configure_logging(LOG_LEVEL, ws_queue=ipc.pubsub.topics[LogsTopic].publication)
        logger.debug(f"Starting aggregation process for camera group {camera_group_id}")
        camera_node_outputs: dict[TrackerTypeString, dict[CameraIdString, CameraNodeOutputMessage | None] | None] = {}
        camera_group_shm = CameraGroupSharedMemoryManager.recreate(shm_dto=camera_group_shm_dto,
                                                                   read_only=True)
        latest_requested_frame: int = -1
        while ipc.should_continue and not shutdown_self_flag.value:
            wait_1ms()
            if camera_group_shm.latest_multiframe_number < 0 or any(
                    [tracker_results is None for tracker_results in camera_node_outputs.values()]):
                ipc.pubsub.topics[ProcessFrameNumberTopic].publish(
                    ProcessFrameNumberMessage(frame_number=camera_group_shm.latest_multiframe_number))
                latest_requested_frame = camera_group_shm.latest_multiframe_number
            # Check for Camera Node Output
            if not camera_node_subscription.empty():
                camera_node_output_message = camera_node_subscription.get()
                if not isinstance(camera_node_output_message, CameraNodeOutputMessage):
                    raise ValueError(
                        f"Expected CameraNodeOutputMessage got {type(camera_node_output_message)}")

                # Process the camera node output and aggregate it
                tracker_type = camera_node_output_message.tracker_type
                camera_id = camera_node_output_message.camera_id
                if not tracker_type in camera_node_outputs.keys() or camera_node_outputs[tracker_type] is None:
                    camera_node_outputs[tracker_type] = {camera_id: None for camera_id in camera_ids}
                if not camera_id in camera_ids:
                    raise ValueError(
                        f"Camera ID {camera_id} not in camera IDs {camera_ids}")
                if not tracker_type in camera_node_outputs.keys() or camera_node_outputs[tracker_type] is None:
                    camera_node_outputs[tracker_type] = {camera_id: None for camera_id in camera_ids}
                camera_node_outputs[tracker_type][camera_id] = camera_node_output_message

            # Check if ready to process a frame output
            for tracker_type, tracker_results in camera_node_outputs.items():
                if all([camera_node_output_message is not None for camera_node_output_message in
                        tracker_results.values()]):
                    # All cameras have observations for this tracker and the frame number is greater than or equal to the latest requested frame
                    if not all([camera_node_output_message.frame_metadata.frame_number == latest_requested_frame for
                                camera_node_output_message in tracker_results.values()]):
                        logger.warning(
                            f"Frame numbers from tracker results do not match - got {[camera_node_output_message.frame_metadata.frame_number for camera_node_output_message in tracker_results.values()]}")

                    camera_node_outputs[tracker_type] = None
                    aggregation_output: AggregationNodeOutputMessage = handle_aggregation_calculations(
                        tracker_type=tracker_type,
                        tracker_results=tracker_results
                    )
                    ipc.pubsub.topics[AggregationNodeOutputTopic].publish(aggregation_output)
                    logger.debug(
                        f"Published aggregation output for frame {latest_requested_frame} with points3d: {aggregation_output.tracked_points3d.keys()}")

    def start(self):
        logger.debug(f"Starting {self.__class__.__name__}")
        self.worker.start()

    def stop(self):
        logger.debug(f"Stopping {self.__class__.__name__}")
        self.shutdown_self_flag.value = True
        self.worker.join()


def handle_aggregation_calculations (tracker_type: TrackerTypeString,
                                    tracker_results: dict[
                                         CameraIdString, CameraNodeOutputMessage]) -> AggregationNodeOutputMessage:
    """ Calculate the aggregation output for a given tracker name and its results from camera nodes.
    This function aggregates the 3D points from the tracker results and returns a BaseAggregationLayerOutputData object.
    """
    frame_number_set = {result.frame_metadata.frame_number for result in tracker_results.values()}
    if len(frame_number_set) != 1:
        logger.warning(f"Frame numbers from tracker results do not match - got {frame_number_set}")
    frame_number = frame_number_set.pop()
    points3d = {}  # Do the aggregation logic here
    logger.info(f"Pretend we're aggregating 3D points for tracker {tracker_type} at frame {frame_number}")
    return AggregationNodeOutputMessage(
        frame_number=frame_number,
        tracked_points3d=points3d)
