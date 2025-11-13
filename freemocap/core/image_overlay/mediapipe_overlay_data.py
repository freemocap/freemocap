from typing import Literal
from pydantic import BaseModel, Field

from skellycam.core.types.type_overloads import CameraIdString
from skellytracker.trackers.mediapipe_tracker.mediapipe_observation import MediapipeObservation


class MediapipePointModel(BaseModel):
    """A single detected Mediapipe landmark point."""
    name: str = Field(description="Landmark name")
    x: float = Field(description="X coordinate in image space")
    y: float = Field(description="Y coordinate in image space")
    z: float = Field(description="Z coordinate (normalized depth)")
    visibility: float = Field(description="Visibility confidence 0-1", ge=0, le=1)


class MediapipeMetadataModel(BaseModel):
    """Metadata about the mediapipe detection."""
    n_body_detected: int = Field(description="Number of body landmarks detected")
    n_right_hand_detected: int = Field(description="Number of right hand landmarks detected")
    n_left_hand_detected: int = Field(description="Number of left hand landmarks detected")
    n_face_detected: int = Field(description="Number of face landmarks detected")
    image_width: int = Field(description="Width of the image in pixels")
    image_height: int = Field(description="Height of the image in pixels")


class MediapipeOverlayData(BaseModel):
    """Complete message for transmitting mediapipe observation over websocket."""
    message_type: Literal["mediapipe_overlay"] = "mediapipe_overlay"
    camera_id: CameraIdString = Field(description="ID of the camera that produced this observation")
    frame_number: int = Field(description="Frame number of this observation")
    body_points: list[MediapipePointModel] = Field(
        default_factory=list,
        description="List of detected body landmark points"
    )
    right_hand_points: list[MediapipePointModel] = Field(
        default_factory=list,
        description="List of detected right hand landmark points"
    )
    left_hand_points: list[MediapipePointModel] = Field(
        default_factory=list,
        description="List of detected left hand landmark points"
    )
    face_points: list[MediapipePointModel] = Field(
        default_factory=list,
        description="List of detected face landmark points"
    )
    metadata: MediapipeMetadataModel = Field(description="Detection metadata and statistics")

    @classmethod
    def from_mediapipe_observation(
            cls,
            *,
            camera_id: CameraIdString,
            observation: MediapipeObservation,
            scale: float = 1.0,
            include_face: bool = True,
            face_type: str = "contour",  # "contour" or "tesselation"
    ):
        """
        Convert MediapipeObservation to Pydantic message model for websocket transmission.

        Args:
            camera_id: ID of the camera that produced this observation
            observation: The MediapipeObservation to serialize
            scale: Scale factor for coordinates (default 1.0)
            include_face: Whether to include face landmarks
            face_type: Type of face landmarks to include ("contour" or "tesselation")

        Returns:
            MediapipeOverlayData ready for JSON serialization
        """
        
        # Get all points with proper scaling
        all_points = observation.all_points(dimensions=3, face_type=face_type, scale_by=scale)
        
        # Build body points
        body_points: list[MediapipePointModel] = []
        if observation.pose_landmarks is not None:
            for name in observation.body_landmark_names:
                if name in all_points:
                    x, y, z = all_points[name]
                    # Get visibility from the original landmark
                    landmark_idx = observation.body_landmark_names.index(name)
                    visibility = observation.pose_landmarks.landmark[landmark_idx].visibility if observation.pose_landmarks else 0.0
                    
                    body_points.append(
                        MediapipePointModel(
                            name=name.replace("body.", ""),  # Remove "body." prefix
                            x=float(x),
                            y=float(y),
                            z=float(z),
                            visibility=float(visibility),
                        )
                    )
        
        # Build right hand points
        right_hand_points: list[MediapipePointModel] = []
        if observation.right_hand_landmarks is not None:
            for name in observation.right_hand_landmark_names:
                if name in all_points:
                    x, y, z = all_points[name]
                    right_hand_points.append(
                        MediapipePointModel(
                            name=name.replace("right_hand.", ""),  # Remove prefix
                            x=float(x),
                            y=float(y),
                            z=float(z),
                            visibility=1.0,  # Hand landmarks don't have visibility in MediaPipe
                        )
                    )
        
        # Build left hand points
        left_hand_points: list[MediapipePointModel] = []
        if observation.left_hand_landmarks is not None:
            for name in observation.left_hand_landmark_names:
                if name in all_points:
                    x, y, z = all_points[name]
                    left_hand_points.append(
                        MediapipePointModel(
                            name=name.replace("left_hand.", ""),  # Remove prefix
                            x=float(x),
                            y=float(y),
                            z=float(z),
                            visibility=1.0,  # Hand landmarks don't have visibility in MediaPipe
                        )
                    )
        
        # Build face points (if requested)
        face_points: list[MediapipePointModel] = []
        if include_face and observation.face_landmarks is not None:
            face_landmark_names = (
                observation.face_contour_landmark_names 
                if face_type == "contour" 
                else [f"face_{i:04d}" for i in range(observation.num_face_tesselation_points)]
            )
            
            for name in face_landmark_names:
                if name in all_points:
                    x, y, z = all_points[name]
                    face_points.append(
                        MediapipePointModel(
                            name=name,
                            x=float(x),
                            y=float(y),
                            z=float(z),
                            visibility=1.0,  # Face landmarks don't have visibility
                        )
                    )
        
        # Build metadata
        metadata = MediapipeMetadataModel(
            n_body_detected=len(body_points),
            n_right_hand_detected=len(right_hand_points),
            n_left_hand_detected=len(left_hand_points),
            n_face_detected=len(face_points),
            image_width=observation.image_size[0],
            image_height=observation.image_size[1],
        )
        
        # Build complete message
        return cls(
            camera_id=camera_id,
            frame_number=observation.frame_number,
            body_points=body_points,
            right_hand_points=right_hand_points,
            left_hand_points=left_hand_points,
            face_points=face_points,
            metadata=metadata,
        )

