"""
Flat, schema-driven skeleton overlay payload.

A `SkeletonOverlayData` carries a per-camera snapshot of a tracker's output as
a single list of fully-prefixed named points (e.g. `body.nose`, `left_hand.wrist`,
`face.contour_0`). It references a tracker schema by id — the frontend looks up
the matching `TrackedObjectDefinition` (sent separately over the `tracker_schemas`
WebSocket message) to draw connections.

This decoupling means adding a new tracker requires authoring a YAML definition,
not editing renderer code on either side.
"""
import msgspec
import numpy as np
from skellycam.core.types.type_overloads import CameraIdString
from skellytracker.core.data_primitives.observation import Observation

from freemocap.core.tracking.tracker_definitions import RTMPOSE_WHOLEBODY_DEFINITION


class SkeletonPointModel(msgspec.Struct):
    """A single detected landmark point. `name` is the fully-prefixed id that
    matches an entry in the active tracker's `TrackedObjectDefinition.tracked_points`."""
    name: str
    x: float
    y: float
    z: float
    visibility: float


class SkeletonOverlayData(msgspec.Struct):
    """Per-camera flat list of detected skeleton points for a single frame.

    `tracker_id` points at a `TrackedObjectDefinition` already sent to the
    frontend via the `tracker_schemas` handshake message. The frontend resolves
    connections by name against that schema.
    """
    camera_id: str
    frame_number: int
    tracker_id: str
    image_width: int
    image_height: int
    message_type: str = "skeleton_overlay"
    points: list[SkeletonPointModel] = []
    # Debug: person bounding box in image pixel coords (xyxy). NaN when absent.
    bbox_x1: float = float("nan")
    bbox_y1: float = float("nan")
    bbox_x2: float = float("nan")
    bbox_y2: float = float("nan")

    @classmethod
    def from_observation(
            cls,
            *,
            camera_id: CameraIdString,
            observation: Observation,
            scale: float = 1.0,
    ) -> "SkeletonOverlayData":
        """Flatten a skeleton Observation into the schema-driven payload.

        Names come from the "body" stage keypoints directly (unqualified, e.g.
        "nose", "left_eye") so they match the schema connection names in
        RTMPOSE_WHOLEBODY_DEFINITION. NaN rows are dropped. z is always 0.
        """
        body_stage = observation.stages.get("body")

        points: list[SkeletonPointModel] = []
        if body_stage is not None and body_stage.keypoints is not None:
            kpts = body_stage.keypoints
            xyz: np.ndarray = kpts.xyz * scale
            visibility: np.ndarray = kpts.visibility
            names: tuple[str, ...] = kpts.names

            for i, name in enumerate(names):
                x, y, z = xyz[i]
                if np.isnan(x) or np.isnan(y):
                    continue
                points.append(
                    SkeletonPointModel(
                        name=name,
                        x=float(x),
                        y=float(y),
                        z=float(z),
                        visibility=float(visibility[i]),
                    )
                )

        bbox_x1 = bbox_y1 = bbox_x2 = bbox_y2 = float("nan")
        if body_stage is not None and body_stage.bounding_boxes:
            bb = body_stage.bounding_boxes[0]
            bbox_x1 = float(bb.x1) * scale
            bbox_y1 = float(bb.y1) * scale
            bbox_x2 = float(bb.x2) * scale
            bbox_y2 = float(bb.y2) * scale

        return cls(
            camera_id=camera_id,
            frame_number=observation.frame_number,
            tracker_id=RTMPOSE_WHOLEBODY_DEFINITION.name,
            image_width=observation.image_size[1],
            image_height=observation.image_size[0],
            message_type="skeleton_overlay",
            points=points,
            bbox_x1=bbox_x1,
            bbox_y1=bbox_y1,
            bbox_x2=bbox_x2,
            bbox_y2=bbox_y2,
        )
