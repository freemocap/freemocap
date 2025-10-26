import logging
import multiprocessing
import threading
import time
from dataclasses import dataclass
from typing import Callable

import numpy as np
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import (
    CameraGroupSharedMemoryDTO,
    CameraGroupSharedMemory,
)
from skellycam.core.types.frontend_payload_bytearray import create_frontend_payload
from skellycam.core.types.type_overloads import CameraIdString, TopicSubscriptionQueue
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation

from freemocap.core.pipeline.pipeline_configs import PipelineConfig
from freemocap.core.pipeline.pipeline_ipc import PipelineIPC
from freemocap.core.pubsub.pubsub_topics import (
    ProcessFrameNumberTopic,
    CameraNodeOutputTopic,
    AggregationNodeOutputTopic,
    AggregationNodeOutputMessage,
    CameraNodeOutputMessage,
    ProcessFrameNumberMessage,
)
from freemocap.core.tasks.calibration_task.charuco_python_converter import (
    charuco_observation_to_overlay_data,
    charuco_observation_to_metadata,
)
from freemocap.core.tasks.calibration_task.charuco_topology_python import (
    create_charuco_topology,
)
# NEW: Import overlay system
from freemocap.core.tasks.calibration_task.image_overlay_system import (
    OverlayRenderer,
)
from freemocap.core.tasks.frontend_payload_builder.frontend_payload import (
    FrontendPayload,
    UnpackagedFrontendPayload,
)
from freemocap.core.types.type_overloads import FrameNumberInt
from freemocap.utilities.wait_functions import wait_10ms

logger = logging.getLogger(__name__)


class CameraOverlayRenderer:
    """Manages overlay rendering for a single camera using the overlay system."""

    def __init__(
            self,
            *,
            camera_id: CameraIdString,
            image_width: int,
            image_height: int,
            pipeline_config: PipelineConfig,
    ):
        self.camera_id = camera_id

        # Create topology based on pipeline config
        self.topology = create_charuco_topology(
            width=image_width,
            height=image_height,
            show_charuco_corners=True,
            show_charuco_ids=True,
            show_aruco_markers=True,
            show_aruco_ids=True,
            show_board_outline=False,  # Can make configurable
            max_charuco_corners=100,
            max_aruco_markers=30,
        )

        # Create renderer
        self.renderer = OverlayRenderer(topology=self.topology)

        logger.info(
            f"Initialized overlay renderer for camera {camera_id} "
            f"({image_width}x{image_height})"
        )

    def annotate_image(
            self,
            *,
            image: np.ndarray,
            charuco_observation: CharucoObservation,
            total_frames: int | None = None,
    ) -> np.ndarray:
        """
        Annotate image with charuco detection overlay.

        Args:
            image: OpenCV image (BGR numpy array)
            charuco_observation: Detection results
            total_frames: Total number of frames for progress display

        Returns:
            Annotated image (BGR numpy array)
        """
        try:
            # Convert observation to overlay format
            points = charuco_observation_to_overlay_data(charuco_observation)
            metadata = charuco_observation_to_metadata(
                charuco_observation,
                total_frames=total_frames
            )

            # Render overlay
            return self.renderer.composite_on_image(
                image=image,
                points=points,
                metadata=metadata
            )

        except Exception as e:
            logger.warning(
                f"Failed to annotate image for camera {self.camera_id}: {e}"
            )
            return image  # Return original image if annotation fails


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

    # Setup overlay renderers
    overlay_renderers: dict[CameraIdString, CameraOverlayRenderer] = {}

    for camera_node_config in pipeline_config.camera_node_configs.values():
        # Get image dimensions from config
        image_width = camera_node_config.camera_config.resolution.width
        image_height = camera_node_config.camera_config.resolution.height

        overlay_renderers[camera_node_config.camera_id] = CameraOverlayRenderer(
            camera_id=camera_node_config.camera_id,
            image_width=image_width,
            image_height=image_height,
            pipeline_config=pipeline_config,
        )

    camera_group_shm = CameraGroupSharedMemory.recreate(
        shm_dto=camera_group_shm_dto, read_only=True
    )
    unpackaged_frames: dict[FrameNumberInt, UnpackagedFrontendPayload] = {}

    while ipc.should_continue:
        wait_10ms()

        # Clean up stale frames
        current_latest_frame = camera_group_shm.latest_multiframe_number
        stale_frames = [
            fn for fn in list(unpackaged_frames.keys())
            if current_latest_frame - fn > 10
        ]
        for frame_number in stale_frames:
            del unpackaged_frames[frame_number]

        # Process frame number messages
        while not process_frame_number_subscription.empty():
            msg: ProcessFrameNumberMessage = process_frame_number_subscription.get()
            if msg.frame_number not in unpackaged_frames:
                try:
                    frames = camera_group_shm.get_images_by_frame_number(
                        frame_number=msg.frame_number
                    )
                    unpackaged_frames[msg.frame_number] = (
                        UnpackagedFrontendPayload.from_frame_number(
                            frame_number=msg.frame_number, frames=frames
                        )
                    )
                    print(f"fe pl blder - got new frame# {msg.frame_number}")
                except (IndexError, Exception):
                    pass  # Frame overwritten or other error, skip

        # Process camera node outputs
        while not camera_node_output_subscription.empty():
            msg: CameraNodeOutputMessage = camera_node_output_subscription.get()
            print(f"fe pl blder - got new  camera group node outputs from frame# {msg.frame_number}")
            if msg.frame_number not in unpackaged_frames:
                try:
                    frames = camera_group_shm.get_images_by_frame_number(
                        frame_number=msg.frame_number
                    )
                    unpackaged_frames[msg.frame_number] = (
                        UnpackagedFrontendPayload.from_frame_number(
                            frame_number=msg.frame_number, frames=frames
                        )
                    )
                    print(f"fe pl blder - got new frame# {msg.frame_number} (in cgnoutputs)")
                except (IndexError, Exception):
                    continue

            try:
                unpackaged_frames[msg.frame_number].add_camera_node_output(msg)

            except (KeyError, ValueError, Exception):
                pass  # Frame disappeared or invalid

        # Process aggregation node outputs
        while not aggregation_node_output_subscription.empty():
            msg: AggregationNodeOutputMessage = aggregation_node_output_subscription.get()
            print(f"fe pl blder - got new frame# {msg.frame_number} aggrgrgegagted node")
            if msg.frame_number not in unpackaged_frames:
                try:
                    frames = camera_group_shm.get_images_by_frame_number(
                        frame_number=msg.frame_number
                    )
                    unpackaged_frames[msg.frame_number] = (
                        UnpackagedFrontendPayload.from_aggregation_node_output(
                            aggregation_node_output=msg, frames=frames
                        )
                    )
                    print(f"fe pl blder - got new frame# {msg.frame_number} (in agggg)")
                except (IndexError, Exception):
                    continue

            try:
                unpackaged_frames[msg.frame_number].add_aggregation_node_output(
                    aggregation_node_output=msg
                )
            except (KeyError, ValueError, Exception):
                pass  # Frame disappeared or invalid

        # Find ready frames - use snapshot for thread safety
        ready_frames: list[UnpackagedFrontendPayload] = []
        for frame_number, unpackaged_frame in list(unpackaged_frames.items()):
            if frame_number in unpackaged_frames and unpackaged_frame.ready_to_package:
                print(f"fe pl blder - appppppppppending #{frame_number}")
                ready_frames.append(unpackaged_frame)

        if not ready_frames:
            continue

        # Keep only the most recent frame
        ready_frames.sort(key=lambda x: x.frame_number)
        newest_frame = ready_frames[-1]

        # Remove all ready frames from tracking
        for frame in ready_frames:
            unpackaged_frames.pop(frame.frame_number, None)

        # Annotate images using NEW overlay system
        for camera_id, overlay_renderer in overlay_renderers.items():
            try:
                if (
                        camera_id in newest_frame.frames
                        and camera_id in newest_frame.camera_node_outputs
                        and newest_frame.camera_node_outputs[camera_id].charuco_observation
                        is not None
                ):
                    charuco_obs = newest_frame.camera_node_outputs[camera_id].charuco_observation

                    # Use overlay system to annotate
                    newest_frame.frames[camera_id].image[0] = overlay_renderer.annotate_image(
                        image=newest_frame.frames[camera_id].image[0],
                        charuco_observation=charuco_obs,
                        total_frames=None,  # Can pass if available
                    )
            except Exception as e:
                logger.warning(
                    f"Failed to annotate camera {camera_id} frame {newest_frame.frame_number}: {e}"
                )
                # Continue with other cameras

        # Create bytearray
        try:
            frame_bytearray = bytes(create_frontend_payload(newest_frame.frames))
        except Exception as e:
            logger.error(f"Failed to create bytearray: {e}")
            continue

        # Create frontend payload
        try:
            frontend_payload = FrontendPayload(
                frame_number=newest_frame.frame_number,
                camera_node_outputs=newest_frame.camera_node_outputs,
                aggregation_node_output=newest_frame.aggregation_node_output,
            )
        except Exception as e:
            logger.error(f"Failed to create frontend payload: {e}")
            continue

        # Update shared state
        try:
            update_latest_frontend_payload_callback(frontend_payload, frame_bytearray)
        except Exception as e:
            logger.error(f"Callback failed: {e}")
            continue

    logger.info("Frontend payload builder exiting")


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
            if self._latest_frontend_payload is not None:
                print("self._latest_frontend_payload is not noneeeeeeeeeee")
            if self._latest_frame_bytearray is not None:
                print("self._latest_frame_bytearray is not noneeeeeeeeee--------------")
            return self._latest_frontend_payload, self._latest_frame_bytearray

    def update_latest_frontend_payload(
            self, frontend_payload: FrontendPayload, frame_bytearray: bytes
    ) -> None:
        with self.lock:
            print(f"Updating latest fe payload with frame# {frontend_payload.frame_number}")
            self._latest_frontend_payload = frontend_payload
            self._latest_frame_bytearray = frame_bytearray

    @property
    def is_alive(self) -> bool:
        """Check if worker thread is alive."""
        return self.worker is not None and self.worker.is_alive()

    def start(self) -> None:
        if self.worker is None:
            raise RuntimeError("Worker thread not initialized")
        self.worker.start()
        time.sleep(0.1)
        if not self.is_alive:
            raise RuntimeError("Worker thread failed to start")

    def shutdown(self) -> None:
        if self.worker is None:
            raise RuntimeError("Worker thread not initialized")
        self.ipc.pipeline_shutdown_flag.value = True

        # Wait for graceful shutdown
        for _ in range(50):
            if not self.is_alive:
                break
            time.sleep(0.01)

        self.worker.join(timeout=5.0)

        if self.is_alive:
            raise RuntimeError("Worker thread did not stop")

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
            name="FrontendPayloadBuilderWorker",
            kwargs=dict(
                pipeline_config=pipeline_config,
                camera_group_shm_dto=camera_group_shm_dto,
                update_latest_frontend_payload_callback=instance.update_latest_frontend_payload,
                process_frame_number_subscription=ipc.pubsub.get_subscription(
                    ProcessFrameNumberTopic
                ),
                camera_node_output_subscription=ipc.pubsub.get_subscription(
                    CameraNodeOutputTopic
                ),
                aggregation_node_output_subscription=ipc.pubsub.get_subscription(
                    AggregationNodeOutputTopic
                ),
                ipc=ipc,
            ),
            daemon=True,
        )
        return instance