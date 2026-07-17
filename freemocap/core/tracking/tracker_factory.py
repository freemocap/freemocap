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
from skellytracker.core.detectors.object_detectors.yolox import (
    YoloxPersonDetector,
    YoloxPersonDetectorConfig,
)
from skellytracker.core.sessions.cpu_session import CpuSession, CpuSessionConfig
from skellytracker.core.sessions.onnx_session import OnnxSession, OnnxSessionConfig
from skellytracker.core.sessions.execution_provider_name import ExecutionProviderName
from skellytracker.core.temporal_processing.temporal_processing_config import (
    BBoxPolicyConfig,
    KeypointResetPolicyConfig,
    KeypointsWithinBBoxRatioConfig,
)

logger = logging.getLogger(__name__)


def build_charuco_tracker(board_def: CharucoBoardDefinition) -> tuple[Tracker, CpuSession]:
    """Build a charuco board tracker backed by a CpuSession.

    Returns both the Tracker and the underlying CpuSession so the caller can
    call tracker.close() / session.close() when done.
    """
    session = CpuSession.create(CpuSessionConfig())
    config = TrackerConfig(
        stages=[
            DetectionStageConfig(
                name="charuco",
                keypoint_detectors=[CharucoDetectorConfig(board=board_def)],
            )
        ]
    )
    tracker = Tracker.create(config, {"cpu": session})
    return tracker, session


def build_skeleton_onnx_session(
    *,
    batch_size: int,
    execution_provider: ExecutionProviderName | None = None,
    device_id: int | None = None,
    model_name: str = "rtmw-x-l_256x192",
    yolox_model_name: str = "yolox-m",
) -> OnnxSession:
    """Create an OnnxSession for RTMPose+YOLOX inference.

    Args:
        batch_size: Number of cameras (images) per batched inference call.
        execution_provider: Force a specific provider ('cuda', 'trt', 'cpu',
            etc.). None = auto-detect best available.
        device_id: GPU device index. None = auto-select.
        model_name: RTMPose model variant.
        yolox_model_name: YOLOX person detector model variant.
    """
    from skellytracker.core.detectors.keypoint_detectors.rtmpose import (
        RTMPoseKeypointDetector,
        RTMPOSE_MODEL_SPECS,
    )

    yolox_spec = YoloxPersonDetector.model_spec(yolox_model_name)
    rtmpose_spec = RTMPoseKeypointDetector.model_spec(model_name)

    session = OnnxSession.create(
        OnnxSessionConfig(
            batch_size=batch_size,
            models=[yolox_spec, rtmpose_spec],
            execution_provider=execution_provider,
            device_id=device_id,
        )
    )
    return session


def build_skeleton_tracker(
    *,
    onnx_session: OnnxSession,
    model_name: str = "rtmw-x-l_256x192",
    confidence_threshold: float = 0.004,
    redetect_interval: int = 5,
    keypoint_bbox_expansion: float = 0.2,
) -> Tracker:
    """Build a body-pose Tracker (RTMPose + YOLOX) backed by an OnnxSession.

    The session must have been created with build_skeleton_onnx_session() using
    matching model names.
    """
    config = TrackerConfig(
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
                    fitness_checks=[KeypointsWithinBBoxRatioConfig(threshold=0.6)],
                ),
            )
        ]
    )
    return Tracker.create(config, {"onnx": onnx_session})


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
    """
    from skellytracker.core.detectors.keypoint_detectors.mediapipe.body.mediapipe_pose_detector import (
        MediapipePoseDetectorConfig,
    )
    from skellytracker.core.detectors.keypoint_detectors.mediapipe.face.mediapipe_face_detector import (
        MediapipeFaceDetectorConfig,
    )
    from skellytracker.core.detectors.keypoint_detectors.mediapipe.hands.mediapipe_hand_detector import (
        MediapipeHandDetectorConfig,
    )
    from skellytracker.core.detectors.keypoint_detectors.mediapipe.mediapipe_model_manager import (
        MediapipePoseModelComplexity,
    )
    from skellytracker.core.sessions.mediapipe_session import (
        MediaPipeSession,
        MediaPipeSessionConfig,
    )

    if model_complexity is None:
        model_complexity = MediapipePoseModelComplexity.HEAVY

    session = MediaPipeSession.create(MediaPipeSessionConfig())
    config = TrackerConfig(
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
                    MediapipeHandDetectorConfig(
                        num_hands=num_hands,
                        min_hand_detection_confidence=detection_confidence,
                        min_hand_presence_confidence=presence_confidence,
                        min_hand_tracking_confidence=tracking_confidence,
                    ),
                    MediapipeFaceDetectorConfig(
                        num_faces=num_faces,
                        min_face_detection_confidence=detection_confidence,
                        min_face_presence_confidence=presence_confidence,
                        min_face_tracking_confidence=tracking_confidence,
                    ),
                ],
                keypoint_reset_policy=KeypointResetPolicyConfig(max_consecutive_misses=10),
            )
        ]
    )
    tracker = Tracker.create(config, {"mediapipe": session})
    return tracker, session
