"""Config for the centralized RealtimeSkeletonInferenceNode.

Kept separate from CameraNodeConfig so it can be toggled / tuned independently
of the per-camera detector knobs. The node-level skeleton detector config
(mode, model size, etc.) is still read from `CameraNodeConfig.skeleton_detector_config`
so a single source of truth governs which model is used in either pipeline mode."""
from pathlib import Path

from pydantic import BaseModel, Field


def _default_engine_cache_dir() -> Path:
    return Path.home() / ".cache" / "skellytracker" / "trt_engines"


class RealtimeSkeletonInferenceNodeConfig(BaseModel):
    # Upper bound on batch size. The node uses min(num_cameras, max_batch_size)
    # at runtime. Set to 1 to disable batching across cameras while keeping the
    # single-CUDA-context win.
    max_batch_size: int = 8

    # Where TensorRT engine + timing caches live. First TRT run compiles to here
    # (slow, 1-3 minutes); subsequent runs are a cache hit and load instantly.
    engine_cache_dir: Path = Field(default_factory=_default_engine_cache_dir)

    # If the requested execution provider isn't available, fall back automatically
    # (trt -> cuda -> cpu) instead of raising. Lets dev laptops without a GPU
    # still run the pipeline (slowly).
    fallback_on_missing_provider: bool = True
