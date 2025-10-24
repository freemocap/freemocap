import logging
import multiprocessing
import threading
from dataclasses import dataclass
from typing import Callable

import numpy as np
from pydantic import BaseModel
from skellycam.core.types.type_overloads import CameraIdString, TopicSubscriptionQueue
from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseImageAnnotator

from freemocap.core.pipeline.camera_node import CameraNode
from freemocap.core.pipeline.pipeline_configs import PipelineConfig
from freemocap.core.pipeline.pipeline_ipc import PipelineIPC
from freemocap.core.pubsub.pubsub_topics import ProcessFrameNumberTopic, CameraNodeOutputTopic, \
    AggregationNodeOutputTopic, AggregationNodeOutputMessage, CameraNodeOutputMessage, ProcessFrameNumberMessage
from freemocap.core.tasks.frontend_payload_builder.frontend_payload import FrontendPayload
from freemocap.core.types.type_overloads import FrameNumberInt
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryDTO, \
    CameraGroupSharedMemoryManager
logger = logging.getLogger(__name__)


def run_frontend_payload_builder(
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

    camera_group_shm = CameraGroupSharedMemoryManager.recreate(shm_dto=camera_group_shm_dto,read_only=True)
    process_frame_number: FrameNumberInt = -1
    raw_images: dict[CameraIdString, np.recarray]|None = None
    camera_node_outputs: dict[CameraIdString, CameraNodeOutputMessage]|None = None
    aggregation_node_output: AggregationNodeOutputMessage|None = None
    while ipc.should_continue:
        if not raw_images and not camera_node_outputs and not aggregation_node_output:
            while not process_frame_number_subscription.empty() and ipc.should_continue:
                process_frame_number_message:ProcessFrameNumberMessage = process_frame_number_subscription.get()
                process_frame_number = process_frame_number_message.frame_number
                raw_images = camera_group_shm.get_images_by_index(process_frame_number)
        if process_frame_number and not raw_images and not camera_node_outputs and not aggregation_node_output:
            while not camera_node_output_subscription.empty() and ipc.should_continue:
                camera_node_output_message:CameraNodeOutputMessage = camera_node_output_subscription.get()



        frame_number = process_frame_number_subscription.get()
        camera_outputs = camera_node_output_subscription.get()
        aggregation_output = aggregation_node_output_subscription.get()

        images = get_images_callback(frame_number)

        frontend_payload = FrontendPayload(
            frame_number=frame_number,
            images=images,
            camera_outputs=camera_outputs,
            aggregation_output=aggregation_output,
        )

        with lock:
            update_latest_frontend_payload_callback(frontend_payload)

@dataclass
class FrontendPayloadBuilder:


    worker: threading.Thread
    lock: multiprocessing.Lock
    latest_frontend_payload: FrontendPayload|None = None


    @classmethod
    def create(
        cls,
        ipc:PipelineIPC,
        get_images_callback: Callable[[FrameNumberInt], dict[CameraIdString, np.recarray]],
        pipeline_config: PipelineConfig,
    ) -> "FrontendPayloadBuilder":
        lock = multiprocessing.Lock()
        worker =  threading.Thread(target=cls._run,
                                   kwargs = dict(
                                       get_images_callback=get_images_callback,
                                       pipeline_config=pipeline_config,
                                       process_frame_number_subscription=ipc.pubsub.get_topic_subscription(
                                           ProcessFrameNumberTopic),
                                       camera_node_output_subscription=ipc.pubsub.get_topic_subscription(
                                           CameraNodeOutputTopic),
                                       aggregation_node_output_subscription=ipc.pubsub.get_topic_subscription(
                                           AggregationNodeOutputTopic),
                                       ipc=ipc,
                                       lock=lock,
                                   ))
        return cls(
            worker=worker,
            lock=lock,
        )


    def _run(self) -> FrontendPayload:


