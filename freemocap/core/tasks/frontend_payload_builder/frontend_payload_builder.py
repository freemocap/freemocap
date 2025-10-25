import logging
import multiprocessing
import threading
from dataclasses import dataclass
from typing import Callable

from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryDTO, \
    CameraGroupSharedMemory
from skellycam.core.types.type_overloads import CameraIdString, TopicSubscriptionQueue

from freemocap.core.pipeline.camera_node import CameraNodeImageAnnotater
from freemocap.core.pipeline.pipeline_configs import PipelineConfig
from freemocap.core.pipeline.pipeline_ipc import PipelineIPC
from freemocap.core.pubsub.pubsub_topics import ProcessFrameNumberTopic, CameraNodeOutputTopic, \
    AggregationNodeOutputTopic, AggregationNodeOutputMessage, CameraNodeOutputMessage, ProcessFrameNumberMessage
from freemocap.core.tasks.frontend_payload_builder.frontend_payload import FrontendPayload, UnpackagedFrontendPayload
from freemocap.core.types.type_overloads import FrameNumberInt
from freemocap.utilities.wait_functions import wait_10ms

logger = logging.getLogger(__name__)


def frontend_payload_builder_worker(
        *,
        camera_group_shm_dto: CameraGroupSharedMemoryDTO,
        pipeline_config: PipelineConfig,
        update_latest_frontend_payload_callback: Callable[[FrontendPayload, bytes], None],
        process_frame_number_subscription: TopicSubscriptionQueue,
        camera_node_output_subscription: TopicSubscriptionQueue,
        aggregation_node_output_subscription: TopicSubscriptionQueue,
        ipc: PipelineIPC,
) -> None:
    """Worker function to build frontend payloads."""

    image_annotators: dict[CameraIdString, CameraNodeImageAnnotater] = {}
    for camera_node_config in pipeline_config.camera_node_configs.values():
        image_annotators[camera_node_config.camera_id] = CameraNodeImageAnnotater.from_pipeline_config(
            pipeline_config=pipeline_config,
            camera_id=camera_node_config.camera_id,
        )

    camera_group_shm = CameraGroupSharedMemory.recreate(shm_dto=camera_group_shm_dto, read_only=True)
    unpackaged_frames: dict[FrameNumberInt, UnpackagedFrontendPayload] = {}

    while ipc.should_continue:
        wait_10ms()
        if not process_frame_number_subscription.empty():
            process_frame_number_message: ProcessFrameNumberMessage = process_frame_number_subscription.get()
            if not process_frame_number_message.frame_number in unpackaged_frames:
                unpackaged_frames[process_frame_number_message.frame_number] = UnpackagedFrontendPayload.from_frame_number(
                    frame_number=process_frame_number_message.frame_number,
                    frames=camera_group_shm.get_images_by_frame_number(
                        frame_number=process_frame_number_message.frame_number))

        if not camera_node_output_subscription.empty():
            camera_node_output_message: CameraNodeOutputMessage = camera_node_output_subscription.get()
            if not camera_node_output_message.frame_number in unpackaged_frames:
                unpackaged_frames[camera_node_output_message.frame_number] = UnpackagedFrontendPayload.from_frame_number(
                    frame_number=camera_node_output_message.frame_number,
                    frames=camera_group_shm.get_images_by_frame_number(
                        frame_number=camera_node_output_message.frame_number))
            else:
                unpackaged_frames[camera_node_output_message.frame_number].add_camera_node_output(camera_node_output_message)

        if not aggregation_node_output_subscription.empty():
            aggregation_node_output_message: AggregationNodeOutputMessage = aggregation_node_output_subscription.get()
            if not aggregation_node_output_message.frame_number in unpackaged_frames:
                unpackaged_frames[aggregation_node_output_message.frame_number] = UnpackagedFrontendPayload.from_aggregation_node_output(
                    aggregation_node_output=aggregation_node_output_message,
                    frames=camera_group_shm.get_images_by_frame_number(
                        frame_number=aggregation_node_output_message.frame_number))
            else:
                unpackaged_frames[aggregation_node_output_message.frame_number].add_aggregation_node_output(
                    aggregation_node_output=aggregation_node_output_message)


        ready_to_go: list[UnpackagedFrontendPayload] = []
        for frame_number, unpackaged_frame in unpackaged_frames.items():
            if unpackaged_frame.ready_to_package:
                ready_to_go.append(unpackaged_frame)
        for unpackaged_frame in ready_to_go:
            del unpackaged_frames[unpackaged_frame.frame_number]
        if ready_to_go:
            ready_to_go.sort(key=lambda x: x.frame_number)
            newest_frame = ready_to_go[-1]
            frontend_payload, frame_bytearray = newest_frame.to_frontend_payload(annotators=image_annotators)
            update_latest_frontend_payload_callback(frontend_payload, frame_bytearray)



@dataclass
class FrontendPayloadBuilder:
    lock: multiprocessing.Lock
    ipc: PipelineIPC
    worker: threading.Thread | None = None
    _latest_frontend_payload: FrontendPayload | None = None
    _latest_frame_bytearray: bytes | None = None

    @property
    def latest_frontend_payload(self) -> tuple[FrontendPayload | None, bytes | None]:
        with self.lock:
            return self._latest_frontend_payload, self._latest_frame_bytearray


    def update_latest_frontend_payload(self, frontend_payload: FrontendPayload, frame_bytearray:bytes) -> None:
        with self.lock:
            self._latest_frontend_payload = frontend_payload
            self._latest_frame_bytearray = frame_bytearray

    def start(self) -> None:
        if self.worker is None:
            raise RuntimeError("Worker thread has not been initialized.")
        logger.info("Starting FrontendPayloadBuilder worker thread.")
        self.worker.start()

    def shutdown(self):
        if self.worker is None:
            raise RuntimeError("Worker thread has not been initialized.")
        logger.info("Shutting down FrontendPayloadBuilder worker thread.")
        self.ipc.pipeline_shutdown_flag.value = True
        self.worker.join()

    @classmethod
    def create(
            cls,
            camera_group_shm_dto: CameraGroupSharedMemoryDTO,
            pipeline_config: PipelineConfig,
            ipc: PipelineIPC,
    ) -> "FrontendPayloadBuilder":
        lock = multiprocessing.Lock()
        instance = cls(lock=lock, ipc=ipc)
        instance.worker = threading.Thread(target=frontend_payload_builder_worker,
                                           kwargs=dict(pipeline_config=pipeline_config,
                                                       camera_group_shm_dto=camera_group_shm_dto,
                                                       update_latest_frontend_payload_callback=instance.update_latest_frontend_payload,
                                                       process_frame_number_subscription=ipc.pubsub.get_subscription(
                                                           ProcessFrameNumberTopic),
                                                       camera_node_output_subscription=ipc.pubsub.get_subscription(
                                                           CameraNodeOutputTopic),
                                                       aggregation_node_output_subscription=ipc.pubsub.get_subscription(
                                                           AggregationNodeOutputTopic),
                                                       ipc=ipc,
                                                       ))
        return instance
