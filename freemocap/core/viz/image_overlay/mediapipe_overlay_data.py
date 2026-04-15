import msgspec
import numpy as np
from skellycam.core.types.type_overloads import CameraIdString
from skellytracker.trackers.mediapipe_tracker import MediapipeObservation


class MediapipePointModel(msgspec.Struct):
    """A single detected Mediapipe landmark point."""
    name: str
    x: float
    y: float
    z: float
    visibility: float


class MediapipeMetadataModel(msgspec.Struct):
    """Metadata about the mediapipe detection."""
    n_body_detected: int
    n_right_hand_detected: int
    n_left_hand_detected: int
    n_face_detected: int
    image_width: int
    image_height: int


class MediapipeOverlayData(msgspec.Struct):
    """Complete message for transmitting mediapipe observation over websocket."""
    camera_id: str
    frame_number: int
    metadata: MediapipeMetadataModel
    message_type: str = "mediapipe_overlay"
    body_points: list[MediapipePointModel] = []
    right_hand_points: list[MediapipePointModel] = []
    left_hand_points: list[MediapipePointModel] = []
    face_points: list[MediapipePointModel] = []

    @classmethod
    def from_mediapipe_observation(
            cls,
            *,
            camera_id: CameraIdString,
            observation: MediapipeObservation,
            scale: float = .5,
            include_face: bool = True,
            face_type: str = "contour",
    ) -> "MediapipeOverlayData":
        """
        Convert MediapipeObservation (or MediapipeCompositeObservation) to
        Pydantic message model for websocket transmission.

        Args:
            camera_id: ID of the camera that produced this observation
            observation: The observation to serialize
            scale: Scale factor for coordinates
            include_face: Whether to include face landmarks
            face_type: Type of face landmarks to include ("contour" or "tesselation")
        """
        all_points = observation.all_points(dimensions=3, face_type=face_type, scale_by=scale)
        body_visibility = observation.body_visibility

        # Build body points
        body_points: list[MediapipePointModel] = []
        if observation.has_pose:
            for i, name in enumerate(observation.body_landmark_names):
                if name in all_points:
                    x, y, z = all_points[name]
                    if np.isnan(x) or np.isnan(y) or np.isnan(z):
                        continue
                    body_points.append(
                        MediapipePointModel(
                            name=name,
                            x=float(x),
                            y=float(y),
                            z=float(z),
                            visibility=float(body_visibility[i]),
                        )
                    )

        # Build right hand points
        right_hand_points: list[MediapipePointModel] = []
        if observation.has_right_hand:
            for name in observation.right_hand_landmark_names:
                if name in all_points:
                    x, y, z = all_points[name]
                    if np.isnan(x) or np.isnan(y) or np.isnan(z):
                        continue
                    right_hand_points.append(
                        MediapipePointModel(
                            name=name.replace("right_hand.", ""),
                            x=float(x),
                            y=float(y),
                            z=float(z),
                            visibility=1.0,
                        )
                    )

        # Build left hand points
        left_hand_points: list[MediapipePointModel] = []
        if observation.has_left_hand:
            for name in observation.left_hand_landmark_names:
                if name in all_points:
                    x, y, z = all_points[name]
                    if np.isnan(x) or np.isnan(y) or np.isnan(z):
                        continue
                    left_hand_points.append(
                        MediapipePointModel(
                            name=name.replace("left_hand.", ""),
                            x=float(x),
                            y=float(y),
                            z=float(z),
                            visibility=1.0,
                        )
                    )

        # Build face points
        face_points: list[MediapipePointModel] = []
        if include_face and observation.has_face:
            face_landmark_names = (
                observation.face_contour_landmark_names
                if face_type == "contour"
                else [f"face_{i:04d}" for i in range(observation.num_face_tesselation_points)]
            )
            for name in face_landmark_names:
                if name in all_points:
                    x, y, z = all_points[name]
                    if np.isnan(x) or np.isnan(y) or np.isnan(z):
                        continue
                    face_points.append(
                        MediapipePointModel(
                            name=name,
                            x=float(x),
                            y=float(y),
                            z=float(z),
                            visibility=1.0,
                        )
                    )

        metadata = MediapipeMetadataModel(
            n_body_detected=len(body_points),
            n_right_hand_detected=len(right_hand_points),
            n_left_hand_detected=len(left_hand_points),
            n_face_detected=len(face_points),
            image_width=observation.image_size[1],
            image_height=observation.image_size[0],
        )

        return cls(
            camera_id=camera_id,
            frame_number=observation.frame_number,
            body_points=body_points,
            right_hand_points=right_hand_points,
            left_hand_points=left_hand_points,
            face_points=face_points,
            metadata=metadata,
        )