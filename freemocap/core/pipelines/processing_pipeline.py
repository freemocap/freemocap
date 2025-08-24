import logging
import logging
import multiprocessing
import uuid
from abc import ABC
from copy import deepcopy
from dataclasses import dataclass
from enum import Enum, auto
from typing import Hashable

import numpy as np
from numpydantic import NDArray, Shape
from pydantic import BaseModel, ConfigDict
from skellycam.core.ipc.shared_memory.frame_payload_shared_memory_ring_buffer import FramePayloadSharedMemoryRingBuffer
from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import SharedMemoryRingBufferDTO
from skellycam.core.ipc.shared_memory.shared_memory_number import SharedMemoryNumber
from skellycam.core.types.type_overloads import CameraIdString, WorkerType, WorkerStrategy, TopicSubscriptionQueue, \
    CameraGroupIdString
from skellycam.utilities.wait_functions import wait_1ms
from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseTracker, BaseImageAnnotator, \
    BaseImageAnnotatorConfig
from skellytracker.trackers.base_tracker.base_tracker_abcs import TrackerTypeString
from skellytracker.trackers.charuco_tracker import CharucoTracker, CharucoTrackerConfig
from skellytracker.trackers.mediapipe_tracker import MediapipeTracker, MediapipeTrackerConfig

from freemocap.core.pubsub.pubsub_manager import TopicTypes
from freemocap.core.pubsub.pubsub_topics import SkellyTrackerConfigsMessage, ProcessFrameNumberMessage, \
    CameraNodeOutputMessage, AggregationNodeOutputMessage
from freemocap.core.types.type_overloads import PipelineIdString
from freemocap.core.pipelines.pipeline_ipc import PipelineIPC

logger = logging.getLogger(__name__)


class ReadTypes(str, Enum):
    LATEST = auto()  # For realtime processing, i.e. drop frames to keep up to date
    NEXT = auto()  # For offline processing, i.e. make sure to process every frame


class BasePipelineData(BaseModel, ABC):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )
    pass


class BaseAggregationLayerOutputData(BasePipelineData):
    multi_frame_number: int
    points3d: dict[Hashable, NDArray[Shape["3"], np.float64]]


class BaseCameraNodeOutputData(BasePipelineData):
    frame_metadata: np.recarray  # dtype: FRAME_METADATA_DTYPE
    time_to_retrieve_frame_ns: int
    time_to_process_frame_ns: int


class BasePipelineOutputData(BasePipelineData):
    camera_node_output: dict[CameraIdString, BaseCameraNodeOutputData]
    aggregation_layer_output: BaseAggregationLayerOutputData

    @property
    def multi_frame_number(self) -> int:
        frame_numbers = [camera_node_output.frame_metadata.frame_number for camera_node_output in
                         self.camera_node_output.values()]
        if len(set(frame_numbers)) > 1:
            raise ValueError(f"Frame numbers from camera nodes do not match - got {frame_numbers}")
        return frame_numbers[0]


@dataclass
class CameraNode:
    camera_id: CameraIdString
    shutdown_self_flag: multiprocessing.Value
    worker: WorkerType

    @classmethod
    def create(cls,
               camera_id: CameraIdString,
               camera_shm_dto: SharedMemoryRingBufferDTO,
               worker_strategy: WorkerStrategy,
               ipc: PipelineIPC):
        shutdown_self_flag = multiprocessing.Value('b', False)
        return cls(camera_id=camera_id,
                   shutdown_self_flag=shutdown_self_flag,
                   worker=worker_strategy.value(target=cls._run,
                                                name =f"CameraProcessingNode-{camera_id}",
                                                kwargs=dict(camera_id=camera_id,
                                                            camera_shm_dto=camera_shm_dto,
                                                            ipc=ipc,
                                                            shutdown_self_flag=shutdown_self_flag,
                                                            process_frame_number_subscription=ipc.pubsub.topics[
                                                                TopicTypes.PROCESS_FRAME_NUMBER].subscription,
                                                            skelly_tracker_configs_subscription=ipc.pubsub.topics[
                                                                TopicTypes.SKELLY_TRACKER_CONFIGS].subscription,
                                                            ),
                                                daemon=True
                                                ),
                   )

    @staticmethod
    def _run(camera_id: CameraIdString,
             mf_ring_shm_dto: SharedMemoryRingBufferDTO,
             ipc: PipelineIPC,
             process_frame_number_subscription: TopicSubscriptionQueue,
             skelly_tracker_configs_subscription: TopicSubscriptionQueue,
             shutdown_self_flag: multiprocessing.Value,
             ):
        if multiprocessing.parent_process():
            # Configure logging if multiprocessing (i.e. if there is a parent process)
            from freemocap.system.logging_configuration.configure_logging import configure_logging
            from freemocap import LOG_LEVEL
            configure_logging(LOG_LEVEL, ws_queue=ipc.pubsub.topics[TopicTypes.LOGS].publication)
        logger.trace(f"Starting camera processing node for camera {camera_id}")
        camera_shm = FramePayloadSharedMemoryRingBuffer.recreate(dto=mf_ring_shm_dto,
                                                                 read_only=False)
        trackers: list[BaseTracker] = []
        frame_rec_array: np.recarray | None = None
        while ipc.should_continue and not shutdown_self_flag.value:
            wait_1ms()

            # Check trackers config updates
            if not skelly_tracker_configs_subscription.empty():
                skelly_tracker_configs_message = skelly_tracker_configs_subscription.get()
                if not isinstance(skelly_tracker_configs_message, SkellyTrackerConfigsMessage):
                    raise ValueError(f"Expected SkellyTrackerConfigsMessage got {type(skelly_tracker_configs_message)}")
                logger.debug(f"Received new skelly tracker s for camera {camera_id}: {skelly_tracker_configs_message}")

                # TODO - This method of updating trackers is sloppy and won't scale as we add more trackers, should make more sophisticated
                tracker_configs = deepcopy(skelly_tracker_configs_message.tracker_configs)
                # Create or update the tracker for this camera
                delete_these = []
                for existing_tracker in trackers:
                    for tracker_index, tracker_config in enumerate(tracker_configs):
                        if isinstance(existing_tracker.config, tracker_config):
                            existing_tracker.update_config(tracker_config)
                            delete_these.append(tracker_index)
                # Remove trackers that were updated
                for index in delete_these:
                    del tracker_configs[index]

                for tracker_config in tracker_configs:
                    if isinstance(tracker_config, CharucoTrackerConfig):
                        trackers.append(CharucoTracker.create(config=tracker_config))
                    elif isinstance(tracker_config, MediapipeTrackerConfig):
                        trackers.append(MediapipeTracker.create(config=tracker_config))
                    else:
                        raise ValueError(f"Unknown tracker config type: {type(tracker_config)}")

                logger.debug(
                    f"Camera {camera_id}, created/updates trackers: {', '.join([tracker.__class__.__name__ for tracker in trackers])}")

            # Check for new frame to process
            if not process_frame_number_subscription.empty():
                process_frame_number_message = process_frame_number_subscription.get()
                if not isinstance(process_frame_number_message, ProcessFrameNumberMessage):
                    raise ValueError(
                        f"Expected ProcessFrameNumberMessage for process frame number, got {type(process_frame_number_message)}")

                logger.debug(
                    f"Camera {camera_id} received request to process frame number {process_frame_number_message.frame_number}")

                # Process the frame
                frame_rec_array = camera_shm.get_data_by_index(index=process_frame_number_message.frame_number,
                                                               frame_rec_array=frame_rec_array)
                for tracker in trackers:
                    observation = tracker.process_image(frame_number=frame_rec_array.frame_metadata.frame_number,
                                                        image=frame_rec_array.image, )
                    if observation is not None:
                        # Publish the observation to the IPC
                        ipc.pubsub.topics[TopicTypes.CAMERA_NODE_OUTPUT].publish(
                            CameraNodeOutputMessage(frame_metadata=frame_rec_array.metadata,
                                                    tracker_name=tracker.__class__.__name__,
                                                    observation=observation))

    def start(self):
        logger.debug(f"Starting {self.__class__.__name__} for camera {self.camera_id}")
        self.worker.start()

    def stop(self):
        logger.debug(f"Stopping {self.__class__.__name__} for camera {self.camera_id}")
        self.shutdown_self_flag.value = True
        self.worker.join()


@dataclass
class AggregationNode(ABC):
    camera_group_id: CameraGroupIdString
    shutdown_self_flag: multiprocessing.Value
    worker: WorkerType

    @classmethod
    def create(cls,
               camera_group_id: CameraGroupIdString,
               camera_ids: list[CameraIdString],
               latest_multiframe_number_shm: SharedMemoryNumber,
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
                                                            camera_node_subscription=ipc.pubsub.get_subscription(
                                                                TopicTypes.CAMERA_NODE_OUTPUT),
                                                            skellytracker_configs_subscription=ipc.pubsub.get_subscription(
                                                                TopicTypes.SKELLY_TRACKER_CONFIGS)),
                                                latest_multiframe_number_shm=latest_multiframe_number_shm,
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
             latest_multiframe_number_shm: SharedMemoryNumber,
             ):
        if multiprocessing.parent_process():
            # Configure logging if multiprocessing (i.e. if there is a parent process)
            from freemocap.system.logging_configuration.configure_logging import configure_logging
            from freemocap import LOG_LEVEL
            configure_logging(LOG_LEVEL, ws_queue=ipc.pubsub.topics[TopicTypes.LOGS].publication)
        logger.debug(f"Starting aggregation process for camera group {camera_group_id}")
        camera_node_outputs: dict[TrackerTypeString, dict[CameraIdString, CameraNodeOutputMessage | None] | None] = {}
        latest_requested_frame: int = -1
        while ipc.should_continue and not shutdown_self_flag.value:
            wait_1ms()
            if latest_requested_frame < 0 or any(
                    [tracker_results is None for tracker_results in camera_node_outputs.values()]):
                ipc.pubsub.topics[TopicTypes.PROCESS_FRAME_NUMBER].publish(
                    ProcessFrameNumberMessage(frame_number=latest_multiframe_number_shm.value))
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
                    aggregation_output: AggregationNodeOutputMessage = handle_aggregration_calculations(
                        tracker_type=tracker_type,
                        tracker_results=tracker_results
                    )
                    ipc.pubsub.topics[TopicTypes.AGGREGATION_NODE_OUTPUT].publish(aggregation_output)
                    logger.debug(
                        f"Published aggregation output for frame {latest_requested_frame} with points3d: {aggregation_output.tracked_points3d.keys()}")

    def start(self):
        logger.debug(f"Starting {self.__class__.__name__}")
        self.worker.start()

    def stop(self):
        logger.debug(f"Stopping {self.__class__.__name__}")
        self.shutdown_self_flag.value = True
        self.worker.join()


def handle_aggregration_calculations(tracker_type: TrackerTypeString,
                                     tracker_results: dict[
                                         CameraIdString, CameraNodeOutputMessage]) -> AggregationNodeOutputMessage:
    """ Calculate the aggregation output for a given tracker name and its results from camera nodes.
    This function aggregates the 3D points from the tracker results and returns a BaseAggregationLayerOutputData object.
    """
    frame_number_set = {result.frame_metadata.frame_number for result in tracker_results.values()}
    if len(frame_number_set) != 1:
        logger.warning(f"Frame numbers from tracker results do not match - got {frame_number_set}")
    frame_number = frame_number_set.pop()
    points3d = {}  # Do the aggregation logic here, e.g. averaging points from different cameras
    return AggregationNodeOutputMessage(
        frame_number=frame_number,
        tracked_points3d=points3d)


class PipelineImageAnnotator(BaseModel, ABC):
    camera_node_annotators: dict[CameraIdString, BaseImageAnnotator]

    @classmethod
    def create(cls, configs: dict[CameraIdString, BaseImageAnnotatorConfig]):
        raise NotImplementedError(
            "You need to re-implement this method with your pipeline's version of the PipelineImageAnnotator ")

    def annotate_images(self, mf_rec_array: np.recarray,
                        pipeline_output: BasePipelineOutputData) -> np.recarray:
        raise NotImplementedError(
            "You need to re-implement this method with your pipeline's version of the PipelineImageAnnotator ")


from skellycam.core.camera_group.camera_group import CameraGroup


@dataclass
class ProcessingPipeline:
    id: PipelineIdString
    camera_nodes: dict[CameraIdString, CameraNode]
    aggregation_node: AggregationNode
    ipc: PipelineIPC

    @property
    def alive(self) -> bool:
        return all([camera_node.worker.is_alive() for camera_node in
                    self.camera_nodes.values()]) and self.aggregation_node.worker.is_alive()

    @classmethod
    def from_camera_group(cls,
                          camera_group: CameraGroup,
                          camera_node_strategy: WorkerStrategy = WorkerStrategy.PROCESS,
                          aggregation_node_strategy: WorkerStrategy = WorkerStrategy.PROCESS, ):
        ipc = PipelineIPC.create(global_kill_flag=camera_group.ipc.global_kill_flag,
                                 )
        camera_group_shm_dto = camera_group.shm.to_dto()
        camera_nodes = {camera_id: CameraNode.create(camera_id=camera_id,
                                                     camera_shm_dto=camera_group_shm_dto.camera_shm_dtos[camera_id],
                                                     worker_strategy=camera_node_strategy,
                                                     ipc=ipc)
                        for camera_id, config in camera_group.configs}
        aggregation_process = AggregationNode.create(camera_group_id=camera_group.id,
                                                     camera_ids=list(camera_nodes.keys()),
                                                     latest_multiframe_number_shm=camera_group.shm.latest_multiframe_number,
                                                     ipc=ipc,
                                                     worker_strategy=aggregation_node_strategy,
                                                     )

        return cls(camera_nodes=camera_nodes,
                   aggregation_node=aggregation_process,
                   ipc=ipc,
                   id=str(uuid.uuid4())[:6]
                   )

    #
    # async def process_multiframe_payload(self, multiframe_payload: MultiFramePayload, annotate_images: bool = True) -> \
    #         tuple[MultiFramePayload, BasePipelineOutputData]:
    #     self.intake_data(multiframe_payload)
    #     pipeline_output = await self.get_next_data_async()
    #     if not multiframe_payload.multi_frame_number == pipeline_output.multi_frame_number:
    #         raise ValueError(
    #             f"Frame number mismatch: {multiframe_payload.multi_frame_number} != {pipeline_output.multi_frame_number}")
    #     annotated_payload = self.annotate_images(multiframe_payload, pipeline_output)
    #     return annotated_payload, pipeline_output
    #
    # def intake_data(self, multiframe_payload: MultiFramePayload):
    #     if not self.ready_to_intake:
    #         raise ValueError("Pipeline not ready to intake data!")
    #     if not all(camera_id in self.camera_nodes.keys() for camera_id in multiframe_payload.camera_ids):
    #         raise ValueError("Data provided for camera IDs not in camera processes!")
    #     for camera_id, frame_payload in multiframe_payload.frames.items():
    #         if not frame_payload.frame_number == multiframe_payload.multi_frame_number:
    #             raise ValueError(
    #                 f"Frame number mismatch: {frame_payload.frame_number} != {multiframe_payload.multi_frame_number}")
    #         self.camera_nodes[camera_id].intake_data(frame_payload)
    #
    # def get_next_data(self) -> BasePipelineOutputData | None:
    #     if self.aggregation_node.output_queue.empty():
    #         return None
    #     data = self.aggregation_node.output_queue.get()
    #     return data
    #
    # async def get_next_data_async(self) -> BasePipelineOutputData:
    #     while self.aggregation_node.output_queue.empty():
    #         await asyncio.sleep(0.001)
    #     data = self.aggregation_node.output_queue.get()
    #     return data
    #
    # def get_latest_data(self) -> BasePipelineOutputData | None:
    #     while not self.aggregation_node.output_queue.empty():
    #         self.latest_pipeline_data = self.aggregation_node.output_queue.get()
    #
    #     return self.latest_pipeline_data
    #
    # def get_output_for_frame(self, target_frame_number: int) -> BasePipelineOutputData | None:
    #     while not self.aggregation_node.output_queue.empty():
    #         self.latest_pipeline_data: BasePipelineOutputData = self.aggregation_node.output_queue.get()
    #         print(f"Frame Annotator got data for frame {self.latest_pipeline_data.multi_frame_number}")
    #         if self.latest_pipeline_data.multi_frame_number > target_frame_number:
    #             raise ValueError(
    #                 f"We missed the target frame number {target_frame_number} - current output is for frame {self.latest_pipeline_data.multi_frame_number}")
    #
    #         if self.latest_pipeline_data.multi_frame_number == target_frame_number:
    #             return self.latest_pipeline_data
    #
    # def annotate_images(self, multiframe_payload: MultiFramePayload,
    #                     pipeline_output: BasePipelineOutputData | None) -> MultiFramePayload:
    #     if pipeline_output is None:
    #         return multiframe_payload
    #     return self.annotator.annotate_images(multiframe_payload, pipeline_output)

    def start(self):
        logger.debug(f"Starting {self.__class__.__name__} with camera processes {list(self.camera_nodes.keys())}...")
        self.aggregation_node.start()
        for camera_id, camera_node in self.camera_nodes.items():
            camera_node.start()
        self.started = True

    def shutdown(self):
        logger.debug(f"Shutting down {self.__class__.__name__}...")
        self.started = False
        self.global_kill_flag.value = True
        self.aggregation_node.stop()
        for camera_id, camera_process in self.camera_nodes.items():
            camera_process.stop()
