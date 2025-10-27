import logging
import queue
import threading
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import (
    CameraGroupSharedMemory,
)
from skellycam.core.types.frontend_payload_bytearray import create_frontend_payload
from skellycam.core.types.type_overloads import CameraIdString, TopicSubscriptionQueue
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation

from freemocap.core.pipeline.pipeline_ipc import PipelineIPC
from freemocap.core.pubsub.pubsub_topics import (
    AggregationNodeOutputMessage,
)
from freemocap.core.tasks.calibration_task.charuco_python_converter import (
    charuco_observation_to_overlay_data,
    charuco_observation_to_metadata,
)
from freemocap.core.tasks.calibration_task.charuco_topology_python import (
    create_charuco_topology,
)
from freemocap.core.tasks.calibration_task.image_overlay_system import (
    OverlayRenderer,
)
from freemocap.core.types.type_overloads import FrameNumberInt
from freemocap.utilities.wait_functions import wait_10ms

logger = logging.getLogger(__name__)


@dataclass
class LatestPayload:
    """Container for the latest frontend payload."""
    message: AggregationNodeOutputMessage | None
    images: bytes | None


class CameraOverlayRenderer:
    """Manages overlay rendering for a single camera using the overlay system."""

    def __init__(
            self,
            *,
            camera_id: CameraIdString,
            image_width: int,
            image_height: int,
    ):
        self.camera_id = camera_id
        self.image_width = image_width
        self.image_height = image_height

        # Create topology based on pipeline config
        self.topology = create_charuco_topology(
            width=self.image_width,
            height=self.image_height,
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


@dataclass
class FrontendPayloadBuilder:
    worker: threading.Thread | None = None
    _shutdown_self: threading.Event = field(default_factory=threading.Event)
    _latest_payload: LatestPayload = field(default_factory=lambda: LatestPayload(None, None))
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def get_latest_frontend_payload(self, if_newer_than:FrameNumberInt) -> tuple[AggregationNodeOutputMessage|None, bytes|None] :
        if not self.alive:
            logger.warning("FrontendPayloadBuilder worker thread is not alive.")
        with self._lock:
            if self._latest_payload and self._latest_payload.message and self._latest_payload.message.frame_number > if_newer_than:
                return self._latest_payload.message, self._latest_payload.images
            else:
                return None,None


    def set_latest_payload(self, aggregator_output: AggregationNodeOutputMessage, images_bytearray: bytes) -> None:
        with self._lock:
            logger.debug(f"Setting latest frontend payload for frame {aggregator_output.frame_number} - images_bytearray size: {len(images_bytearray)} bytes")
            self._latest_payload = LatestPayload(
                message=deepcopy(aggregator_output),
                images=images_bytearray
            )
    @property
    def alive(self):
        return self.worker.is_alive() if self.worker else False

    @classmethod
    def create(
            cls,
            *,
            aggregation_node_output_subscription: TopicSubscriptionQueue,
            camera_group_shm: CameraGroupSharedMemory,
            ipc: PipelineIPC,
    ) -> "FrontendPayloadBuilder":

        instance = cls()
        instance.worker = threading.Thread(
            target=build_frontend_payloads,
            kwargs=dict(
                aggregation_node_output_subscription=aggregation_node_output_subscription,
                camera_group_shm=camera_group_shm,
                shutdown_self=instance._shutdown_self,
                ipc=ipc,
                update_latest_payload_callback=instance.set_latest_payload,
            ),
            daemon=True
        )
        return instance

    def start(self) -> None:
        if self.worker is None:
            raise RuntimeError("Worker thread not initialized.")
        logger.debug("Starting FrontendPayloadBuilder worker thread.")
        self.worker.start()

    def shutdown(self) -> None:
        logger.debug("Shutting down FrontendPayloadBuilder worker thread.")
        self._shutdown_self.set()
        if self.worker is not None:
            self.worker.join()
            logger.debug("FrontendPayloadBuilder worker thread has exited.")


def build_frontend_payloads(
        aggregation_node_output_subscription: TopicSubscriptionQueue,
        camera_group_shm: CameraGroupSharedMemory,
        shutdown_self: threading.Event,
        ipc: PipelineIPC,
        update_latest_payload_callback: Callable[[AggregationNodeOutputMessage, bytes], None],
) -> None:
    overlay_renderers: dict[CameraIdString, CameraOverlayRenderer] = {}
    latest_frames: dict[CameraIdString, np.recarray] | None = None

    try:
        while ipc.should_continue and not shutdown_self.is_set():

            aggregation_node_output_message: AggregationNodeOutputMessage | None = None
            while not aggregation_node_output_subscription.empty():
                aggregation_node_output_message = aggregation_node_output_subscription.get_nowait()
            if aggregation_node_output_message is None:
                wait_10ms()
                print('butttt')
                continue
            logger.info(f"Building frontend payload for frame {aggregation_node_output_message.frame_number}")
            for camera_config in aggregation_node_output_message.pipeline_config.camera_configs.values():
                if camera_config.camera_id not in overlay_renderers:
                    logger.debug(f"Creating overlay renderer for camera {camera_config.camera_id}")
                    overlay_renderers[camera_config.camera_id] = CameraOverlayRenderer(
                        camera_id=camera_config.camera_id,
                        image_width=camera_config.resolution.width,
                        image_height=camera_config.resolution.height
                    )

                # Update dimensions if they changed
                renderer = overlay_renderers[camera_config.camera_id]
                if (camera_config.resolution.width != renderer.image_width or
                        camera_config.resolution.height != renderer.image_height):
                    renderer.image_width = camera_config.resolution.width
                    renderer.image_height = camera_config.resolution.height

            # Clean up renderers for cameras that are no longer in the config
            overlay_renderers = {
                cam_id: renderer
                for cam_id, renderer in overlay_renderers.items()
                if cam_id in aggregation_node_output_message.pipeline_config.camera_ids
            }

            if not camera_group_shm.valid:
                logger.warning("Camera group shared memory is not valid.")
                continue

            latest_frames = camera_group_shm.get_images_by_frame_number(
                frame_number=aggregation_node_output_message.frame_number,
                frame_recarrays=latest_frames
            )

            for camera_id, camera_node_output in aggregation_node_output_message.camera_node_outputs.items():
                logger.debug(f"Annotating image for camera {camera_id} at frame {aggregation_node_output_message.frame_number}")
                overlay_renderer = overlay_renderers[camera_id]

                latest_frames[camera_id].image[0] = overlay_renderer.annotate_image(
                    image=latest_frames[camera_id].image[0],
                    charuco_observation=camera_node_output.charuco_observation,
                )

            _, _, images_bytearray = create_frontend_payload(latest_frames)

            update_latest_payload_callback(
                aggregation_node_output_message,
                images_bytearray
            )
    except Exception as e:
        logger.error(f"Exception in build_frontend_payloads: {e}", exc_info=True)
    logger.info("Exiting build_frontend_payloads thread.")