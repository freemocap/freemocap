"""Application provider policy and startup diagnostics, never per-frame work."""
from dataclasses import dataclass
import logging
import sys

logger = logging.getLogger(__name__)

# Application/API spellings paired with ONNX Runtime's public provider names.
PROVIDER_NAMES = {
    'trt': 'TensorrtExecutionProvider', 'cuda': 'CUDAExecutionProvider',
    'coreml': 'CoreMLExecutionProvider', 'directml': 'DmlExecutionProvider',
    'cpu': 'CPUExecutionProvider',
}


def advertised_providers() -> list[str]:
    import onnxruntime
    installed = set(onnxruntime.get_available_providers())
    return [name for name, native in PROVIDER_NAMES.items()
            if native in installed and (name != 'coreml' or sys.platform == 'darwin')]


def application_provider(requested: str | None) -> str:
    """Use CUDA for Auto and obsolete TensorRT settings, with platform fallback."""
    if requested not in (None, 'trt'):
        return requested
    available = advertised_providers()
    for provider in ('cuda', 'coreml', 'directml', 'cpu'):
        if provider in available:
            return provider
    raise ValueError('No supported inference provider is available')


@dataclass(frozen=True)
class ModelProviderStatus:
    model_name: str
    requested_provider: str | None
    applied_providers: tuple[str, ...]


def inspect_onnx_session(session, config) -> tuple[ModelProviderStatus, ...]:
    """Report loaded EPs; reject explicit choices that ORT silently dropped.

    Automatic mode retains Tracker's fallback policy. Registered EPs describe
    session configuration, not proof that every graph operation runs on a GPU.
    """
    result = []
    for model in config.models:
        actual = tuple(session.get_session(model.name).get_providers())
        status = ModelProviderStatus(model.name, config.execution_provider, actual)
        logger.info('ONNX model=%s requested_provider=%s applied_providers=%s',
                    model.name, config.execution_provider or 'auto', actual)
        result.append(status)
        if config.execution_provider is not None and PROVIDER_NAMES[config.execution_provider] not in actual:
            from skellytracker.core.sessions.session_errors import SessionCreationError
            raise SessionCreationError(
                f'Model {model.name!r}: requested provider {config.execution_provider!r} did not load; '
                f'actual providers: {actual}. Choose Auto to permit fallback or select another provider.')
    return tuple(result)


def inspect_tracker_providers(tracker, requests) -> tuple[ModelProviderStatus, ...]:
    """Inspect borrowed sessions through public detector references at startup."""
    onnx_requests = [request for request in requests if request.config.backend == 'onnx']
    if not onnx_requests:
        return ()
    stages = list(tracker.stages)
    while stages:
        stage = stages.pop()
        stages.extend(stage.children)
        for detector in [stage.object_detector, *stage.keypoint_detectors]:
            session = getattr(detector, 'session', None)
            if session is not None and session.kind == 'onnx':
                # One session per backend is guaranteed by SharedSessionPool.
                return inspect_onnx_session(session, onnx_requests[0].config)
    raise RuntimeError('ONNX session requested but no ONNX detector was constructed')
