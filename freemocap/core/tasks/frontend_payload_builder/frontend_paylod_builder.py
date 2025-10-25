import logging
import multiprocessing
import threading
from dataclasses import dataclass
from typing import Callable

import numpy as np
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryDTO, \
    CameraGroupSharedMemory
from skellycam.core.types.frontend_payload_bytearray import create_frontend_payload
from skellycam.core.types.type_overloads import CameraIdString, TopicSubscriptionQueue

from freemocap.core.pipeline.camera_node import CameraNodeImageAnnotater
from freemocap.core.pipeline.pipeline_configs import PipelineConfig
from freemocap.core.pipeline.pipeline_ipc import PipelineIPC
from freemocap.core.pubsub.pubsub_topics import ProcessFrameNumberTopic, CameraNodeOutputTopic, \
    AggregationNodeOutputTopic, AggregationNodeOutputMessage, CameraNodeOutputMessage, ProcessFrameNumberMessage
from freemocap.core.tasks.frontend_payload_builder.frontend_payload import FrontendPayload
from freemocap.core.types.type_overloads import FrameNumberInt

logger = logging.getLogger(__name__)


def wait_for_frame_number(
        *,
        process_frame_number_subscription: TopicSubscriptionQueue,
        camera_group_shm: CameraGroupSharedMemory,
        ipc: PipelineIPC,
) -> tuple[FrameNumberInt, dict[CameraIdString, np.recarray]]|None:
    """Wait for a frame number message and retrieve raw frames from shared memory."""
    while ipc.should_continue:
        while not process_frame_number_subscription.empty():
            message: ProcessFrameNumberMessage = process_frame_number_subscription.get()
            frame_number = message.frame_number
            raw_frames = camera_group_shm.get_images_by_frame_number(
                frame_number=frame_number,
                frame_recarrays=None
            )
            return frame_number, raw_frames
    return None


def wait_for_camera_node_outputs(
        *,
        frame_number: FrameNumberInt,
        raw_frames: dict[CameraIdString, np.recarray],
        camera_node_output_subscription: TopicSubscriptionQueue,
        image_annotators: dict[CameraIdString, CameraNodeImageAnnotater],
        camera_ids: list[CameraIdString],
        ipc: PipelineIPC,
) -> tuple[dict[CameraIdString, CameraNodeOutputMessage|None], dict[CameraIdString, np.recarray]]:
    """Wait for all camera node outputs and create annotated frames."""
    camera_node_outputs: dict[CameraIdString, CameraNodeOutputMessage|None] = {camera_id:None for camera_id in camera_ids}
    annotated_frames: dict[CameraIdString, np.recarray] = {}

    while any([output is None for output in camera_node_outputs.values()]) and ipc.should_continue:
        while  not camera_node_output_subscription.empty():
            message: CameraNodeOutputMessage = camera_node_output_subscription.get()

            if message.camera_id not in camera_ids:
                raise ValueError(f"Received output for unknown camera ID: {message.camera_id}")

            if message.frame_number != frame_number:
                raise ValueError(
                    f"Frame number mismatch in camera node output for camera {message.camera_id}. "
                    f"Expected {frame_number}, got {message.frame_number}"
                )

            camera_node_outputs[message.camera_id] = message

            # Create annotated frame
            annotated_frame = raw_frames[message.camera_id].copy()
            annotated_frame.image[0] = image_annotators[message.camera_id].annotate_image(
                image=raw_frames[message.camera_id].image[0],
                charuco_observation=message.charuco_observation,
            )
            annotated_frames[message.camera_id] = annotated_frame

    return camera_node_outputs, annotated_frames


def wait_for_aggregation_node_output(
        *,
        frame_number: FrameNumberInt,
        aggregation_node_output_subscription: TopicSubscriptionQueue,
        ipc: PipelineIPC,
) -> AggregationNodeOutputMessage:
    """Wait for aggregation node output."""
    while ipc.should_continue:
        if not aggregation_node_output_subscription.empty():
            message: AggregationNodeOutputMessage = aggregation_node_output_subscription.get()

            if message.frame_number != frame_number:
                raise ValueError(
                    f"Frame number mismatch in aggregation output. Expected {frame_number}, got {message.frame_number}"
                )

            return message

    raise RuntimeError("IPC shutdown before aggregation node output received")


def frontend_payload_builder_worker(
        *,
        camera_group_shm_dto: CameraGroupSharedMemoryDTO,
        pipeline_config: PipelineConfig,
        update_latest_frontend_payload_callback: Callable[[FrontendPayload], None],
        process_frame_number_subscription: TopicSubscriptionQueue,
        camera_node_output_subscription: TopicSubscriptionQueue,
        aggregation_node_output_subscription: TopicSubscriptionQueue,
        ipc: PipelineIPC,
) -> None:
    """Worker function to build frontend payloads."""

    # Initialize image annotators
    image_annotators: dict[CameraIdString, CameraNodeImageAnnotater] = {}
    for camera_node_config in pipeline_config.camera_node_configs.values():
        image_annotators[camera_node_config.camera_id] = CameraNodeImageAnnotater.from_pipeline_config(
            pipeline_config=pipeline_config,
            camera_id=camera_node_config.camera_id,
        )

    camera_group_shm = CameraGroupSharedMemory.recreate(shm_dto=camera_group_shm_dto, read_only=True)
    camera_ids = list(pipeline_config.camera_configs.keys())

    # Main processing loop - one iteration per frame
    while ipc.should_continue:
        # Stage 1: Wait for frame number and get raw frames
        frame_number, raw_frames = wait_for_frame_number(
            process_frame_number_subscription=process_frame_number_subscription,
            camera_group_shm=camera_group_shm,
            ipc=ipc,
        )

        # Stage 2: Wait for all camera node outputs and create annotated frames
        camera_node_outputs, annotated_frames = wait_for_camera_node_outputs(
            frame_number=frame_number,
            raw_frames=raw_frames,
            camera_node_output_subscription=camera_node_output_subscription,
            image_annotators=image_annotators,
            camera_ids=camera_ids,
            ipc=ipc,
        )

        # Stage 3: Wait for aggregation node output
        aggregation_node_output = wait_for_aggregation_node_output(
            frame_number=frame_number,
            aggregation_node_output_subscription=aggregation_node_output_subscription,
            ipc=ipc,
        )

        # Stage 4: Create and publish frontend payload
        _, _, frames_byte_array = create_frontend_payload(annotated_frames)
        frontend_payload = FrontendPayload(
            frame_number=frame_number,
            images_byte_array=frames_byte_array,
            camera_node_outputs=camera_node_outputs,
            aggregation_node_output=aggregation_node_output,
        )
        update_latest_frontend_payload_callback(frontend_payload)


@dataclass
class FrontendPayloadBuilder:
    lock: multiprocessing.Lock
    ipc: PipelineIPC
    worker: threading.Thread | None = None
    _latest_frontend_payload: FrontendPayload | None = None

    @property
    def latest_frontend_payload(self) -> FrontendPayload | None:
        with self.lock:
            if self._latest_frontend_payload:
                logger.info(f"Accessing latest_frontend_payload #{self._latest_frontend_payload.frame_number}")
            return self._latest_frontend_payload

    def update_latest_frontend_payload(self, value: FrontendPayload | None) -> None:
        with self.lock:
            self._latest_frontend_payload = value

    def start(self) -> None:
        if self.worker is None:
            raise RuntimeError("Worker thread has not been initialized.")
        logger.info("Starting FrontendPayloadBuilder worker thread.")
        self.worker.start()

    def shutdown(self) -> None:
        if self.worker is None:
            raise RuntimeError("Worker thread has not been initialized.")
        logger.info("Shutting down FrontendPayloadBuilder worker thread.")
        self.ipc.should_continue = False
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
        instance.worker = threading.Thread(
            target=frontend_payload_builder_worker,
            kwargs=dict(
                pipeline_config=pipeline_config,
                camera_group_shm_dto=camera_group_shm_dto,
                update_latest_frontend_payload_callback=instance.update_latest_frontend_payload,
                process_frame_number_subscription=ipc.pubsub.get_subscription(ProcessFrameNumberTopic),
                camera_node_output_subscription=ipc.pubsub.get_subscription(CameraNodeOutputTopic),
                aggregation_node_output_subscription=ipc.pubsub.get_subscription(AggregationNodeOutputTopic),
                ipc=ipc,
            )
        )
        return instance