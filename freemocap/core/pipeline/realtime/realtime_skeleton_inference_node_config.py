"""Config for the centralized RealtimeSkeletonInferenceNode."""
from pydantic import BaseModel
from skellytracker.core.sessions.execution_provider_name import ExecutionProviderName


class RealtimeSkeletonInferenceNodeConfig(BaseModel):
    # Upper bound on batch size. The node uses min(num_cameras, max_batch_size)
    # at runtime. Set to 1 to disable batching across cameras while keeping the
    # single-CUDA-context win.
    max_batch_size: int = 8

    # None: auto-select best available (trt → cuda → coreml → cpu) — recommended.
    # "trt":  TensorRT EP — 2-5x faster than CUDA EP, requires NVIDIA GPU +
    #         `pip install tensorrt`. Compiles engines on first run (1-5 min).
    # "cuda": CUDA EP — requires NVIDIA GPU + onnxruntime-gpu, no extra install.
    # "cpu":  CPU EP — no GPU required, slowest.
    # Note: explicit provider raises immediately if unavailable; None silently falls back.
    execution_provider: ExecutionProviderName | None = None

    # When True, writes debug frames with bbox overlays to
    # {freemocap_data}/debug_bboxes/. (requires GPU mode)
    debug_draw_bboxes: bool = False
