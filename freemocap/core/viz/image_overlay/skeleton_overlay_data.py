import msgspec
import numpy as np
from skellycam.core.types.type_overloads import CameraIdString
from skellytracker.trackers.rtmpose_tracker.rtmpose_landmark_names import BODY_LANDMARK_NAMES, FACE_LANDMARK_NAMES, \
    LEFT_HAND_LANDMARK_NAMES
from skellytracker.trackers.rtmpose_tracker.rtmpose_observation import RTMPoseObservation


# from skellytracker.trackers.legacy_mediapipe_tracker import LegacyMediapipeObservation
# from skellytracker.trackers.mediapipe_tracker import MediapipeObservation


class SkeletonPointModel(msgspec.Struct):
    """A single detected Mediapipe landmark point."""
    name: str
    x: float
    y: float
    z: float
    visibility: float


class SkeletonMetadataModel(msgspec.Struct):
    """Metadata about the mediapipe detection."""
    n_body_detected: int
    n_right_hand_detected: int
    n_left_hand_detected: int
    n_face_detected: int
    image_width: int
    image_height: int


class SkeletonOverlayData(msgspec.Struct):
    """Complete message for transmitting mediapipe observation over websocket."""
    camera_id: str
    frame_number: int
    metadata: SkeletonMetadataModel
    message_type: str = "mediapipe_overlay"
    body_points: list[SkeletonPointModel] = []
    right_hand_points: list[SkeletonPointModel] = []
    left_hand_points: list[SkeletonPointModel] = []
    face_points: list[SkeletonPointModel] = []

    # @classmethod
    # def from_mediapipe_observation(
    #         cls,
    #         *,
    #         camera_id: CameraIdString,
    #         observation: LegacyMediapipeObservation | MediapipeObservation,
    #         scale: float = .5,
    #         include_face: bool = True,
    #         face_type: str = "contour",
    # ) -> "SkeletonOverlayData":
    #     """
    #     Convert MediapipeObservation (or MediapipeCompositeObservation) to
    #     Pydantic message model for websocket transmission.
    #
    #     Args:
    #         camera_id: ID of the camera that produced this observation
    #         observation: The observation to serialize
    #         scale: Scale factor for coordinates
    #         include_face: Whether to include face landmarks
    #         face_type: Type of face landmarks to include ("contour" or "tesselation")
    #     """
    #     all_points = observation.all_points(dimensions=3, face_type=face_type, scale_by=scale)
    #     body_visibility = observation.body_visibility
    #
    #     # Build body points
    #     body_points: list[SkeletonPointModel] = []
    #     if observation.has_pose:
    #         for i, name in enumerate(observation.body_landmark_names):
    #             if name in all_points:
    #                 x, y, z = all_points[name]
    #                 if np.isnan(x) or np.isnan(y) or np.isnan(z):
    #                     continue
    #                 body_points.append(
    #                     SkeletonPointModel(
    #                         name=name,
    #                         x=float(x),
    #                         y=float(y),
    #                         z=float(z),
    #                         visibility=float(body_visibility[i]),
    #                     )
    #                 )
    #
    #     # Build right hand points
    #     right_hand_points: list[SkeletonPointModel] = []
    #     if observation.has_right_hand:
    #         for name in observation.right_hand_landmark_names:
    #             if name in all_points:
    #                 x, y, z = all_points[name]
    #                 if np.isnan(x) or np.isnan(y) or np.isnan(z):
    #                     continue
    #                 right_hand_points.append(
    #                     SkeletonPointModel(
    #                         name=name.replace("right_hand.", ""),
    #                         x=float(x),
    #                         y=float(y),
    #                         z=float(z),
    #                         visibility=1.0,
    #                     )
    #                 )
    #
    #     # Build left hand points
    #     left_hand_points: list[SkeletonPointModel] = []
    #     if observation.has_left_hand:
    #         for name in observation.left_hand_landmark_names:
    #             if name in all_points:
    #                 x, y, z = all_points[name]
    #                 if np.isnan(x) or np.isnan(y) or np.isnan(z):
    #                     continue
    #                 left_hand_points.append(
    #                     SkeletonPointModel(
    #                         name=name.replace("left_hand.", ""),
    #                         x=float(x),
    #                         y=float(y),
    #                         z=float(z),
    #                         visibility=1.0,
    #                     )
    #                 )
    #
    #     # Build face points
    #     face_points: list[SkeletonPointModel] = []
    #     if include_face and observation.has_face:
    #         face_landmark_names = (
    #             observation.face_contour_landmark_names
    #             if face_type == "contour"
    #             else [f"face_{i:04d}" for i in range(observation.num_face_tesselation_points)]
    #         )
    #         for name in face_landmark_names:
    #             if name in all_points:
    #                 x, y, z = all_points[name]
    #                 if np.isnan(x) or np.isnan(y) or np.isnan(z):
    #                     continue
    #                 face_points.append(
    #                     SkeletonPointModel(
    #                         name=name,
    #                         x=float(x),
    #                         y=float(y),
    #                         z=float(z),
    #                         visibility=1.0,
    #                     )
    #                 )
    #
    #     metadata = SkeletonMetadataModel(
    #         n_body_detected=len(body_points),
    #         n_right_hand_detected=len(right_hand_points),
    #         n_left_hand_detected=len(left_hand_points),
    #         n_face_detected=len(face_points),
    #         image_width=observation.image_size[1],
    #         image_height=observation.image_size[0],
    #     )
    #
    #     return cls(
    #         camera_id=camera_id,
    #         frame_number=observation.frame_number,
    #         body_points=body_points,
    #         right_hand_points=right_hand_points,
    #         left_hand_points=left_hand_points,
    #         face_points=face_points,
    #         metadata=metadata,
    #     )

    @classmethod
    def from_rtmpose_observation(
            cls,
            *,
            camera_id: CameraIdString,
            observation: RTMPoseObservation,
            scale: float = 0.5,
            include_face: bool = True,
    ) -> "SkeletonOverlayData":
        """
        Convert an RTMPoseObservation to SkeletonOverlayData for websocket transmission.

        RTMPose packs all 133 COCO-WholeBody landmarks into observation.points in the
        fixed order: body (23), face (68), left hand (21), right hand (21). RTMPose is
        2D-only so every z coordinate is 0. The per-point `visibility` field carries
        the RTMPose heatmap-peak confidence score (arbitrary units, not [0, 1]).
        """
        n_body: int = len(BODY_LANDMARK_NAMES)
        n_face: int = len(FACE_LANDMARK_NAMES)
        n_hand: int = len(LEFT_HAND_LANDMARK_NAMES)
        expected_total: int = n_body + n_face + 2 * n_hand

        xyz: np.ndarray = observation.points.xyz * scale
        visibility: np.ndarray = observation.points.visibility
        names: tuple[str, ...] = observation.points.names

        if xyz.shape[0] != expected_total or len(names) != expected_total:
            raise ValueError(
                f"RTMPoseObservation point cloud has {xyz.shape[0]} points and "
                f"{len(names)} names; expected {expected_total} "
                f"(body={n_body}, face={n_face}, left_hand={n_hand}, right_hand={n_hand})."
            )

        body_start: int = 0
        face_start: int = n_body
        left_hand_start: int = n_body + n_face
        right_hand_start: int = n_body + n_face + n_hand

        def _build_points(*, start: int, count: int, strip_prefix: str) -> list[SkeletonPointModel]:
            built: list[SkeletonPointModel] = []
            for i in range(start, start + count):
                x, y, z = xyz[i]
                if np.isnan(x) or np.isnan(y) or np.isnan(z):
                    continue
                name: str = names[i].removeprefix(strip_prefix) if strip_prefix else names[i]
                built.append(
                    SkeletonPointModel(
                        name=name,
                        x=float(x),
                        y=float(y),
                        z=float(z),
                        visibility=float(visibility[i]),
                    )
                )
            return built

        body_points: list[SkeletonPointModel] = _build_points(
            start=body_start, count=n_body, strip_prefix="",
        )
        left_hand_points: list[SkeletonPointModel] = _build_points(
            start=left_hand_start, count=n_hand, strip_prefix="left_",
        )
        right_hand_points: list[SkeletonPointModel] = _build_points(
            start=right_hand_start, count=n_hand, strip_prefix="right_",
        )
        face_points: list[SkeletonPointModel] = (
            _build_points(start=face_start, count=n_face, strip_prefix="")
            if include_face
            else []
        )

        metadata: SkeletonMetadataModel = SkeletonMetadataModel(
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
            message_type="rtmpose_overlay",
            body_points=body_points,
            right_hand_points=right_hand_points,
            left_hand_points=left_hand_points,
            face_points=face_points,
            metadata=metadata,
        )
