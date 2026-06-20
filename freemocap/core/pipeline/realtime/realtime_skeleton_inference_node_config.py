"""Config for the centralized RealtimeSkeletonInferenceNode.

Kept separate from CameraNodeConfig so it can be toggled / tuned independently
of the per-camera detector knobs. The node-level skeleton detector config
(mode, model size, etc.) is still read from `CameraNodeConfig.skeleton_detector_config`
so a single source of truth governs which model is used in either pipeline mode."""
from pathlib import Path

from pydantic import BaseModel, Field
from skellytracker.utilities.gpu_utils.execution_provider_name import ExecutionProviderName


def _default_engine_cache_dir() -> Path:
    return Path.home() / ".cache" / "skellytracker" / "trt_engines"


class RealtimeSkeletonInferenceNodeConfig(BaseModel):
    # Upper bound on batch size. The node uses min(num_cameras, max_batch_size)
    # at runtime. Set to 1 to disable batching across cameras while keeping the
    # single-CUDA-context win.
    max_batch_size: int = 8

    # Where TensorRT engine + timing caches live. First TRT run compiles to here
    # (slow, 1-5 minutes); subsequent runs are a cache hit and load instantly.
    engine_cache_dir: Path = Field(default_factory=_default_engine_cache_dir)

    # If the requested execution provider isn't available, fall back automatically
    # (trt -> cuda -> cpu) instead of raising.
    fallback_on_missing_provider: bool = True

    # "trt":  TensorRT EP — 2-5x faster than CUDA EP, requires NVIDIA GPU +
    #         `pip install tensorrt`. Compiles engines on first run (1-5 min),
    #         cached to engine_cache_dir on all subsequent runs.
    # "cuda": CUDA EP — requires NVIDIA GPU + onnxruntime-gpu, no extra install.
    # "cpu":  CPU EP — no GPU required, slowest.
    execution_provider: ExecutionProviderName = "cuda"
    # Downscale images before YOLOX person detection (0 < scale ≤ 1.0).
    # Lower = faster YOLOX pass, but too low may miss small/distant people.
    # The RTMPose skeleton estimator always crops from the original full-res
    # image, so pose accuracy is unaffected — only detection recall changes.
    # 0.5 = half resolution. 1.0 = no downscaling (most reliable).
    yolox_image_scale: float = 1.0
    # When True, skip YOLOX by reusing the previous frame's keypoint-derived
    # bbox (expanded by a small margin). YOLOX re-runs every ~5 seconds and
    # whenever pose confidence drops.
    enable_tracking_skip: bool = True
    # When True, writes debug frames with bbox overlays to
    # {freemocap_data}/debug_bboxes/. Green = YOLOX bbox, orange = tracking.
    debug_draw_bboxes: bool = True
