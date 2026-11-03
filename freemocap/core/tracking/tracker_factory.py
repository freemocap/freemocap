"""Application settings translation and Tracker session lifecycle coordination.

SkellyTracker owns recipes, detector registration, schemas and keypoint assembly.
Core supplies settings and coordinates session construction with its inference
services, provider diagnostics and shared resource lifecycle.
"""

from __future__ import annotations

from skellytracker.core.detectors.keypoint_detectors.mediapipe.mediapipe_model_manager import MediapipePoseModelComplexity

import logging
import threading
from contextlib import ExitStack, nullcontext

from skellytracker.core import (
    Tracker,
    TrackerConfig,
)
from skellytracker.core.detectors.keypoint_detectors.charuco import (
    CharucoBoardDefinition,
)
from skellytracker.core.sessions.mediapipe_session import (
    MediaPipeSession,
    MediaPipeSessionConfig,
)
from skellytracker.core.sessions.shared_sessions import SessionRequest
from skellytracker.core.sessions.session import Session  # noqa: TC002
from skellytracker.core.tracker import tracker_session_requests as registry_session_requests
from skellytracker.core.sessions.cpu_session import CpuSession, CpuSessionConfig
from skellytracker.core.sessions.onnx_session import OnnxSession, OnnxSessionConfig
from skellytracker.core.sessions.execution_provider_name import ExecutionProviderName  # noqa: TC002


logger = logging.getLogger(__name__)
# Serialize direct in-process ONNX construction; Tracker file locks protect shared caches across processes.
_onnx_session_build_lock = threading.Lock()
CHARUCO_STAGE_NAME = "charuco"


def build_configured_tracker(*, config: TrackerConfig, batch_size: int,
                             execution_provider: ExecutionProviderName | None = None) -> Tracker:
    """Allocate the backends and models declared by every stage of a tracker.

    The returned tracker owns the sessions and closes them through Tracker.close.
    Construction failures release sessions before propagating the error.
    """
    requests = tracker_session_requests(config=config, batch_size=batch_size, execution_provider=execution_provider)
    with ExitStack() as cleanup:
        sessions: dict[str, Session] = {}
        for request in requests:
            with _onnx_session_build_lock if request.config.backend == "onnx" else nullcontext():
                session = request.session_type.create(request.config)
            sessions[request.config.backend] = session
            cleanup.callback(session.close)
            if request.config.backend == "onnx":
                from freemocap.core.tracking.execution_providers import inspect_onnx_session
                inspect_onnx_session(session, request.config)
        tracker = Tracker.create(config=config, sessions=sessions)
        cleanup.pop_all()
    return tracker


def tracker_session_requests(
    *, config: TrackerConfig, batch_size: int, execution_provider: ExecutionProviderName | None,
    mediapipe_disable_gpu: bool | None = None,
) -> tuple[SessionRequest, ...]:
    """Describe Tracker registry resources without allocating inference sessions."""
    overrides = {"execution_provider": execution_provider}
    if config.preset_name == "dlc":
        if execution_provider not in ("cpu", "cuda"):
            raise ValueError("DLC requires an explicit CPU or CUDA execution provider; auto and TensorRT are unsupported")
        overrides["fp16"] = False
    requests = registry_session_requests(
        config,
        batch_size=batch_size,
        onnx_overrides=overrides,
        mediapipe_overrides={"disable_gpu": mediapipe_disable_gpu},
    )
    if not requests:
        raise ValueError("Tracker configuration requires at least one detector")
    from freemocap.core.tracking.execution_providers import application_provider
    return tuple(SessionRequest(session_type=request.session_type,
        config=request.config.model_copy(update={"execution_provider": application_provider(request.config.execution_provider)}))
        if request.config.backend == "onnx" else request for request in requests)


def build_charuco_tracker(
    board_def: CharucoBoardDefinition,
) -> tuple[Tracker, CpuSession]:
    """Build a charuco board tracker backed by a CpuSession.

    Returns both the Tracker and the underlying CpuSession so the caller can
    call tracker.close() / session.close() when done.
    """
    session = CpuSession.create(CpuSessionConfig())
    from skellytracker.core.tracker.tracker_presets import charuco_tracker_config
    config = charuco_tracker_config(board_def)
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
    """Create an OnnxSession for RTMW+YOLOX inference.

    Args:
        batch_size: Number of cameras (images) per batched inference call.
        execution_provider: Force a specific provider ('cuda', 'trt', 'cpu',
            etc.). None = auto-detect best available.
        device_id: GPU device index. None = auto-select.
        model_name: RTMW model variant.
        yolox_model_name: YOLOX person detector model variant.
    """
    from skellytracker.core.tracker.tracker_presets import skeleton_model_specs
    from freemocap.core.tracking.execution_providers import application_provider
    execution_provider = application_provider(execution_provider)
    model_specs = skeleton_model_specs(model_name=model_name, yolox_model_name=yolox_model_name)

    with _onnx_session_build_lock:
        session = OnnxSession.create(
            OnnxSessionConfig(
                batch_size=batch_size,
                models=model_specs,
                execution_provider=execution_provider,
                device_id=device_id,
            )
        )
    from freemocap.core.tracking.execution_providers import inspect_onnx_session
    try:
        inspect_onnx_session(session, OnnxSessionConfig(batch_size=batch_size, models=model_specs, execution_provider=execution_provider))
    except Exception:
        session.close()
        raise
    return session




def build_skeleton_tracker(
    *,
    onnx_session: OnnxSession,
    model_name: str = "rtmw-x-l_256x192",
    confidence_threshold: float = 0.4,
    video_fps: float = 30.0,
    keypoint_bbox_expansion: float = 0.05,
) -> Tracker:
    """Build a body-pose Tracker (RTMW + YOLOX) backed by an OnnxSession.

    The session must have been created with build_skeleton_onnx_session() using
    matching model names.
    """
    config = skeleton_tracker_config(model_name=model_name, confidence_threshold=confidence_threshold,
        video_fps=video_fps, keypoint_bbox_expansion=keypoint_bbox_expansion)
    return Tracker.create(config, {"onnx": onnx_session})


def build_mediapipe_tracker(
    *,
    model_complexity: MediapipePoseModelComplexity | None = None,
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
    if model_complexity is None:
        model_complexity = MediapipePoseModelComplexity.HEAVY

    config = mediapipe_tracker_config(model_complexity=model_complexity,
        detection_confidence=detection_confidence, presence_confidence=presence_confidence,
        tracking_confidence=tracking_confidence, num_hands=num_hands, num_faces=num_faces)
    with ExitStack() as cleanup:
        session = MediaPipeSession.create(MediaPipeSessionConfig())
        cleanup.callback(session.close)
        cpu_session = CpuSession.create(CpuSessionConfig())
        cleanup.callback(cpu_session.close)
        tracker = Tracker.create(config, {"mediapipe": session, "cpu": cpu_session})
        cleanup.pop_all()
    return tracker, session


# Tracker owns recipes and keypoint assembly; these aliases preserve Core callers.
from skellytracker.core.tracker.tracker_presets import (
    skeleton_tracker_config, build_mediapipe_tracker_config as build_mediapipe_tracker_config, mediapipe_tracker_config,
    human_tracker_config,
)

def tracker_config_for_settings(settings, *, video_fps: float = 30.0) -> TrackerConfig:
    """Translate application setting names into Tracker's public preset interface."""
    if settings.detector_type == "dlc":
        from skellytracker.core.tracker.tracker_presets import dlc_tracker_config
        from skellytracker.core.sidecar.errors import SidecarError
        if not settings.dlc_model_path:
            raise ValueError("Select or import a DLC model before starting tracking (dlc_model_path)")
        try:
            return dlc_tracker_config(sidecar_path=settings.dlc_model_path,
                                      confidence_threshold=settings.dlc_confidence_threshold)
        except (SidecarError, OSError) as error:
            raise ValueError(f"Invalid DLC model selection: {error}") from error
    return human_tracker_config(
        preset=settings.detector_type, model_name=settings.rtmpose_model_name,
        confidence_threshold=settings.rtmpose_confidence_threshold, video_fps=video_fps,
        model_complexity=settings.mediapipe_model_complexity,
        detection_confidence=settings.mediapipe_detection_confidence,
        presence_confidence=settings.mediapipe_presence_confidence,
        tracking_confidence=settings.mediapipe_tracking_confidence,
        num_faces=settings.mediapipe_num_faces,
    )
