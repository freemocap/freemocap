"""Factory functions for building skellytracker Tracker instances.

Centralizes all Tracker.create() calls so import side-effects (detector
registration), config construction, and session creation live in one place.

All other modules should import from here rather than calling Tracker.create()
directly, so the registry-side-effect imports are guaranteed to have run.
"""
from __future__ import annotations

import logging
from pathlib import Path

import skellytracker.core.detectors.keypoint_detectors.charuco    # noqa: F401 (registry)
import skellytracker.core.detectors.keypoint_detectors.mediapipe  # noqa: F401 (registry)
import skellytracker.core.detectors.keypoint_detectors.rtmpose    # noqa: F401 (registry)
import skellytracker.core.detectors.object_detectors.yolox        # noqa: F401 (registry)

from skellytracker.core import (
    DetectionStageConfig,
    Keypoints,
    Observation,
    Tracker,
    TrackerConfig,
)
from skellytracker.core.detectors.keypoint_detectors.charuco import (
    CharucoBoardDefinition,
    CharucoDetectorConfig,
)
from skellytracker.core.detectors.keypoint_detectors.rtmpose import (
    RTMPoseDetectorConfig,
)
from skellytracker.core.detectors.object_detectors.keypoint_bbox import (
    KeypointBoundingBoxDetectorConfig,
)
from skellytracker.core.detectors.object_detectors.yolox import (
    YoloxPersonDetectorConfig,
)
from skellytracker.core.sessions.cpu_session import CpuSession
from skellytracker.core.sessions.execution_provider_name import ExecutionProviderName  # noqa: TC002
from skellytracker.core.temporal_processing.temporal_processing_config import (
    BBoxPolicyConfig,
    BBoxSmoothingConfig,
    KeypointResetPolicyConfig,
    KeypointsWithinBBoxRatioConfig,
)
from skellytracker.core.tracker.tracker_factory import build_tracker as _st_build_tracker

logger = logging.getLogger(__name__)


def build_charuco_tracker(board_def: CharucoBoardDefinition) -> tuple[Tracker, CpuSession]:
    """Build a charuco board tracker backed by a CpuSession.

    Returns both the Tracker and the underlying CpuSession so the caller can
    call tracker.close() / session.close() when done.
    """
    config = TrackerConfig(
        stages=[
            DetectionStageConfig(
                name="charuco",
                keypoint_detectors=[CharucoDetectorConfig(board=board_def)],
            )
        ]
    )
    tracker = _st_build_tracker(config)
    return tracker, tracker.sessions["cpu"]


_REDETECT_SECONDS = 5.0


def _rtmpose_config(
    *,
    model_name: str = "rtmw-x-l_256x192",
    confidence_threshold: float = 0.004,
    video_fps: float = 30.0,
    keypoint_bbox_expansion: float = 0.05,
) -> TrackerConfig:
    redetect_interval = max(1, round(_REDETECT_SECONDS * video_fps))
    return TrackerConfig(
        stages=[
            DetectionStageConfig(
                name="body",
                object_detector=YoloxPersonDetectorConfig(),
                keypoint_detectors=[
                    RTMPoseDetectorConfig(
                        model_name=model_name,
                        confidence_threshold=confidence_threshold,
                    )
                ],
                bbox_policy=BBoxPolicyConfig(
                    redetect_interval=redetect_interval,
                    keypoint_bbox_expansion=keypoint_bbox_expansion,
                    fitness_checks=[KeypointsWithinBBoxRatioConfig(threshold=0.5)],
                    min_shrink_ratio_per_frame=0.995,
                    min_bbox_size_px=80.0,
                ),
                bbox_smoothing=BBoxSmoothingConfig(alpha=0.4),
            )
        ]
    )


def build_rtmpose_tracker(
    *,
    batch_size: int,
    execution_provider: ExecutionProviderName | None = None,
    device_id: int | None = None,
    model_name: str = "rtmw-x-l_256x192",
    confidence_threshold: float = 0.004,
    video_fps: float = 30.0,
    keypoint_bbox_expansion: float = 0.05,
) -> Tracker:
    """Build a body-pose Tracker (RTMPose + YOLOX) backed by an OnnxSession.

    Args:
        batch_size: Number of cameras (images) per batched inference call.
        execution_provider: Force a specific provider ('cuda', 'trt', 'cpu',
            etc.). None = auto-detect best available.
        device_id: GPU device index. None = auto-select.
        model_name: RTMPose model variant.
        confidence_threshold: Minimum keypoint confidence to accept.
        video_fps: Source video/stream frame rate, used to size the
            bbox-redetect interval.
        keypoint_bbox_expansion: Fractional padding added to a keypoint-derived
            bounding box.
    """
    config = _rtmpose_config(
        model_name=model_name,
        confidence_threshold=confidence_threshold,
        video_fps=video_fps,
        keypoint_bbox_expansion=keypoint_bbox_expansion,
    )
    return _st_build_tracker(
        config,
        onnx_overrides={
            "batch_size": batch_size,
            "execution_provider": execution_provider,
            "device_id": device_id,
        },
    )


def _mediapipe_hand_child_stage(
    side: str,
    *,
    detection_confidence: float,
    presence_confidence: float,
    tracking_confidence: float,
) -> DetectionStageConfig:
    """Build a wrist-cropped hand child stage for the given side ('left'/'right').

    Crops tightly around the wrist using the parent body stage's own
    wrist/index/pinky keypoints (pure keypoint arithmetic, no inference — see
    KeypointBoundingBoxDetectorConfig), then runs MediaPipe's hand landmarker
    on that zoomed-in crop with a fixed handedness, since MediaPipe's own
    per-crop handedness guess is unreliable on a tight single-hand crop.
    """
    from skellytracker.core.detectors.keypoint_detectors.mediapipe.hands.mediapipe_hand_detector import (
        MediapipeHandDetectorConfig,
    )

    return DetectionStageConfig(
        name=f"{side}_hand",
        object_detector=KeypointBoundingBoxDetectorConfig(
            center_keypoint_names=(f"{side}_index", f"{side}_pinky"),
            scale_keypoint_pairs=(
                (f"{side}_wrist", f"{side}_index"),
                (f"{side}_wrist", f"{side}_pinky"),
            ),
            scale_factor=3.0,
            min_box_size_px=30.0,
        ),
        keypoint_detectors=[
            MediapipeHandDetectorConfig(
                num_hands=1,
                assumed_handedness=side,
                min_hand_detection_confidence=detection_confidence,
                min_hand_presence_confidence=presence_confidence,
                min_hand_tracking_confidence=tracking_confidence,
            )
        ],
        bbox_smoothing=BBoxSmoothingConfig(alpha=0.4),
    )


def build_mediapipe_tracker_config(
    *,
    model_complexity=None,
    detection_confidence: float = 0.5,
    presence_confidence: float = 0.5,
    tracking_confidence: float = 0.5,
    num_faces: int = 1,
) -> TrackerConfig:
    """Build a MediaPipe body+hands+face TrackerConfig.

    Pose is the parent "body" stage; left_hand/right_hand are wrist-cropped
    child stages (see _mediapipe_hand_child_stage) instead of full-frame
    sibling detectors, since hands occupy a tiny fraction of a full-body frame
    and MediaPipe's palm detector struggles to find them at that scale. Face
    is also a child stage (full-frame, no crop) purely to preserve the
    existing pose/right_hand/left_hand/face point ordering that
    merge_mediapipe_hand_face_children() and tracker_definitions.py expect.
    """
    from skellytracker.core.detectors.keypoint_detectors.mediapipe.body.mediapipe_pose_detector import (
        MediapipePoseDetectorConfig,
    )
    from skellytracker.core.detectors.keypoint_detectors.mediapipe.face.mediapipe_face_detector import (
        MediapipeFaceDetectorConfig,
    )
    from skellytracker.core.detectors.keypoint_detectors.mediapipe.mediapipe_model_manager import (
        MediapipePoseModelComplexity,
    )

    if model_complexity is None:
        model_complexity = MediapipePoseModelComplexity.HEAVY

    return TrackerConfig(
        stages=[
            DetectionStageConfig(
                name="body",
                keypoint_detectors=[
                    MediapipePoseDetectorConfig(
                        model_complexity=model_complexity,
                        num_poses=1,
                        min_pose_detection_confidence=detection_confidence,
                        min_pose_presence_confidence=presence_confidence,
                        min_pose_tracking_confidence=tracking_confidence,
                    ),
                ],
                children=[
                    _mediapipe_hand_child_stage(
                        "right",
                        detection_confidence=detection_confidence,
                        presence_confidence=presence_confidence,
                        tracking_confidence=tracking_confidence,
                    ),
                    _mediapipe_hand_child_stage(
                        "left",
                        detection_confidence=detection_confidence,
                        presence_confidence=presence_confidence,
                        tracking_confidence=tracking_confidence,
                    ),
                    DetectionStageConfig(
                        name="face",
                        keypoint_detectors=[
                            MediapipeFaceDetectorConfig(
                                num_faces=num_faces,
                                min_face_detection_confidence=detection_confidence,
                                min_face_presence_confidence=presence_confidence,
                                min_face_tracking_confidence=tracking_confidence,
                            )
                        ],
                    ),
                ],
                keypoint_reset_policy=KeypointResetPolicyConfig(max_consecutive_misses=10),
            )
        ]
    )


def merge_mediapipe_hand_face_children(obs: Observation) -> None:
    """Merge left_hand/right_hand/face child-stage keypoints back into the
    top-level "body" stage, preserving the flat right_hand_*/left_hand_*
    naming and pose+right_hand+left_hand+face ordering every downstream
    consumer (skeleton_rigidifier, recording_status, export_to_blender,
    tracker_definitions, freemocap-ui) expects. Mutates `obs` in place.
    No-op for non-mediapipe configs (no "body" stage or no children).
    """
    body_stage = obs.stages.get("body")
    if body_stage is None or not body_stage.children:
        return
    parts = [body_stage.keypoints] if body_stage.keypoints is not None else []
    for name in ("right_hand", "left_hand", "face"):
        child = body_stage.children.pop(name, None)
        if child is not None and child.keypoints is not None:
            parts.append(child.keypoints)
    if len(parts) > 1:
        body_stage.keypoints = Keypoints.concatenate(parts)


def build_mediapipe_tracker(
    *,
    model_complexity=None,
    detection_confidence: float = 0.5,
    presence_confidence: float = 0.5,
    tracking_confidence: float = 0.5,
    num_hands: int = 2,
    num_faces: int = 1,
) -> tuple[Tracker, object]:
    """Build a MediaPipe body+hands+face Tracker backed by a MediaPipeSession.

    Returns (tracker, session). The session type is MediaPipeSession from
    skellytracker.core.sessions.mediapipe_session.

    `num_hands` is accepted for API compatibility but unused: each hand child
    stage is a dedicated single-hand, wrist-cropped detector (see
    _mediapipe_hand_child_stage), so MediaPipe always looks for exactly one
    hand per stage rather than sharing a full-frame budget across both hands.
    """
    config = build_mediapipe_tracker_config(
        model_complexity=model_complexity,
        detection_confidence=detection_confidence,
        presence_confidence=presence_confidence,
        tracking_confidence=tracking_confidence,
        num_faces=num_faces,
    )
    tracker = _st_build_tracker(config)
    return tracker, tracker.sessions["mediapipe"]
