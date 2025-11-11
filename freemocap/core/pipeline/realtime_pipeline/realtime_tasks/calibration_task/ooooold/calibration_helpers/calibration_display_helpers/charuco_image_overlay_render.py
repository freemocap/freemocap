import logging

import numpy as np
from skellycam.core.types.type_overloads import CameraIdString
from skellytracker.trackers.charuco_tracker.charuco_observation import BaseObservation

from freemocap.core.pipeline.realtime_pipeline.realtime_tasks.calibration_task.ooooold.calibration_helpers.calibration_display_helpers.charuco_python_converter import \
    charuco_observation_to_overlay_data, charuco_observation_to_metadata
from freemocap.core.pipeline.realtime_pipeline.realtime_tasks.calibration_task.ooooold.calibration_helpers.calibration_display_helpers.charuco_topology_python import \
    create_charuco_topology
from freemocap.core.pipeline.realtime_pipeline.realtime_tasks.calibration_task.ooooold.calibration_helpers.calibration_display_helpers.image_overlay_system import \
    OverlayRenderer

logger = logging.getLogger(__name__)


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
            charuco_observation: BaseObservation,
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
