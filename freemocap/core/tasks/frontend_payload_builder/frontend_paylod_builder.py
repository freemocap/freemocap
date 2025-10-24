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


def frontend_payload_builder_worker(
        *,
        camera_group_shm_dto: CameraGroupSharedMemoryDTO,
        pipeline_config: PipelineConfig,
        update_latest_frontend_payload_callback: Callable[[FrontendPayload], None],
        process_frame_number_subscription: TopicSubscriptionQueue,
        camera_node_output_subscription: TopicSubscriptionQueue,
        aggregation_node_output_subscription: TopicSubscriptionQueue,
        ipc: PipelineIPC,
        lock: multiprocessing.Lock,
) -> None:
    """Worker function to build frontend payloads."""

    image_annotators: dict[CameraIdString, CameraNodeImageAnnotater] = {}
    for camera_node_config in pipeline_config.camera_node_configs.values():
        image_annotators[camera_node_config.camera_id] = CameraNodeImageAnnotater.from_pipeline_config(
            pipeline_config=pipeline_config,
            camera_id=camera_node_config.camera_id,
        )

    camera_group_shm = CameraGroupSharedMemory.recreate(shm_dto=camera_group_shm_dto, read_only=True)
    process_frame_number: FrameNumberInt = -1
    raw_frames: dict[CameraIdString, np.recarray] | None = None
    annotated_frames: dict[CameraIdString, np.recarray | None] = {camera_id: None for camera_id in
                                                                  pipeline_config.camera_configs.keys()}
    camera_node_outputs: dict[CameraIdString, CameraNodeOutputMessage | None] = {camera_id: None for camera_id in
                                                                                 pipeline_config.camera_configs.keys()}
    aggregation_node_output: AggregationNodeOutputMessage | None = None

    while ipc.should_continue:
        if not raw_frames and not camera_node_outputs and not aggregation_node_output:
            while not process_frame_number_subscription.empty() and ipc.should_continue:
                process_frame_number_message: ProcessFrameNumberMessage = process_frame_number_subscription.get()
                process_frame_number = process_frame_number_message.frame_number
                raw_frames = camera_group_shm.get_images_by_frame_number(frame_number=process_frame_number)

        if raw_frames and any(
                [output is None for output in camera_node_outputs.values()]) and not aggregation_node_output:
            while not camera_node_output_subscription.empty() and ipc.should_continue:
                camera_node_output_message: CameraNodeOutputMessage = camera_node_output_subscription.get()
                if not camera_node_output_message.camera_id in camera_node_outputs:
                    raise ValueError(f"Received output for unknown camera ID: {camera_node_output_message.camera_id}")
                if not camera_node_output_message.frame_number == process_frame_number:
                    raise ValueError(
                        f"Frame number mismatch in camera output. Expected {process_frame_number}, got {camera_node_output_message.frame_number}")
                camera_node_outputs[camera_node_output_message.camera_id] = camera_node_output_message
                annotated_frames[camera_node_output_message.camera_id].image[0] = image_annotators[
                    camera_node_output_message.camera_id].annotate_image(
                    image=raw_frames[camera_node_output_message.camera_id].image[0],
                    charuco_observation=camera_node_outputs[camera_node_output_message.camera_id].charuco_observation,
                    mediapipe_observaton=None  # TODO - add mocap task
                )

        if raw_frames and all(
                [output is not None for output in camera_node_outputs.values()]) and not aggregation_node_output:
            if not all([annotated_frame is not None for annotated_frame in annotated_frames.values()]):
                raise ValueError("Annotated frames are not all available when expected.")
            while not aggregation_node_output_subscription.empty() and ipc.should_continue:
                aggregation_node_output_message: AggregationNodeOutputMessage = aggregation_node_output_subscription.get()
                if not aggregation_node_output_message.frame_number == process_frame_number:
                    raise ValueError(
                        f"Frame number mismatch in aggregation output. Expected {process_frame_number}, got {aggregation_node_output_message.frame_number}")
                aggregation_node_output = aggregation_node_output_message

        if raw_frames and all([output is not None for output in camera_node_outputs.values()]) and all(
                [annotated_frame is not None for annotated_frame in
                 annotated_frames.values()]) and aggregation_node_output:
            _, _, frames_byte_array = create_frontend_payload(annotated_frames)
            frontend_payload = FrontendPayload(
                frame_number=process_frame_number,
                images_byte_array=frames_byte_array,
                camera_node_outputs=camera_node_outputs,
                aggregation_node_output=aggregation_node_output,
            )
            with lock:
                update_latest_frontend_payload_callback(frontend_payload)
            raw_frames = None
            camera_node_outputs = {camera_id: None for camera_id in pipeline_config.camera_configs.keys()}
            aggregation_node_output = None


# def frontend_payload_builder_worker(
#     *,
#     camera_group_shm_dto: CameraGroupSharedMemoryDTO,
#     pipeline_config: PipelineConfig,
#     update_latest_frontend_payload_callback: Callable[[FrontendPayload], None],
#     process_frame_number_subscription: TopicSubscriptionQueue,
#     camera_node_output_subscription: TopicSubscriptionQueue,
#     aggregation_node_output_subscription: TopicSubscriptionQueue,
#     ipc: PipelineIPC,
#     lock: multiprocessing.Lock,
# ) -> None:

@dataclass
class FrontendPayloadBuilder:
    lock: multiprocessing.Lock
    shutdown_self_flag: multiprocessing.Value = multiprocessing.Value('b', False)
    worker: threading.Thread| None = None
    _latest_frontend_payload: FrontendPayload | None = None

    @property
    def latest_frontend_payload(self) -> FrontendPayload | None:
        with self.lock:
            return self._latest_frontend_payload


    def update_latest_frontend_payload(self, value: FrontendPayload | None) -> None:
        with self.lock:
            self._latest_frontend_payload = value

    def start(self) -> None:
        if self.worker is None:
            raise RuntimeError("Worker thread has not been initialized.")
        logger.info("Starting FrontendPayloadBuilder worker thread.")
        self.worker.start()

    def shutdown(self   ):
        if self.worker is None:
            raise RuntimeError("Worker thread has not been initialized.")
        logger.info("Shutting down FrontendPayloadBuilder worker thread.")
        self.shutdown_self_flag.value = True
        self.worker.join()

    @classmethod
    def create(
            cls,
            camera_group_shm_dto: CameraGroupSharedMemoryDTO,
            pipeline_config: PipelineConfig,
            ipc: PipelineIPC,
    ) -> "FrontendPayloadBuilder":
        lock = multiprocessing.Lock()
        instance = cls(lock=lock)
        instance.worker = threading.Thread(target=frontend_payload_builder_worker,
                                  kwargs=dict(pipeline_config=pipeline_config,
                                              camera_group_shm_dto=camera_group_shm_dto,
                                              update_latest_frontend_payload_callback=instance.update_latest_frontend_payload,
                                              process_frame_number_subscription=ipc.pubsub.get_topic_subscription(
                                                  ProcessFrameNumberTopic),
                                              camera_node_output_subscription=ipc.pubsub.get_topic_subscription(
                                                  CameraNodeOutputTopic),
                                              aggregation_node_output_subscription=ipc.pubsub.get_topic_subscription(
                                                  AggregationNodeOutputTopic),
                                              ipc=ipc,
                                              lock=lock,
                                              ))
        return instance