"""Standalone benchmark: what can this GPU actually do with the realtime models?

Reproduces the exact OnnxSession the realtime pipeline builds (batch_size=5,
auto provider), then times raw session.run() for each model:

  1. on the main thread, nothing else running  -> hardware ceiling
  2. on a background thread while other Python threads are active -> what the
     in-server (WorkerMode.THREAD) inference node actually gets

Run:  .venv/Scripts/python.exe bench_inference.py
"""

import logging
import statistics
import threading
import time

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(message)s")

from skellytracker.core.detectors.keypoint_detectors.rtmpose import RTMPoseKeypointDetector
from skellytracker.core.detectors.object_detectors.yolox import YoloxPersonDetector
from skellytracker.core.sessions.onnx_session import OnnxSession, OnnxSessionConfig

BATCH = 5
ITERS = 30
RTMPOSE_MODEL = "rtmw-x-l_256x192"
YOLOX_MODEL = "yolox-m"


def time_model(session: OnnxSession, spec, iters: int = ITERS) -> list[float]:
    ort_session = session.get_session(spec.name)
    h, w = spec.input_size
    dummy = np.random.rand(BATCH, 3, h, w).astype(np.float32)
    input_name = ort_session.get_inputs()[0].name
    for _ in range(5):  # warm
        ort_session.run(None, {input_name: dummy})
    times = []
    for _ in range(iters):
        t0 = time.perf_counter()
        ort_session.run(None, {input_name: dummy})
        times.append((time.perf_counter() - t0) * 1e3)
    return times


def report(label: str, times: list[float]) -> float:
    med = statistics.median(times)
    print(
        f"  {label:<44} median {med:7.1f} ms   "
        f"min {min(times):6.1f}   max {max(times):6.1f}"
    )
    return med


def gil_noise(stop: threading.Event) -> None:
    """Approximate the Python work the API server does alongside inference."""
    payload = bytearray(150 * 1024)
    while not stop.is_set():
        # asyncio-ish churn: lots of small object work + short sleeps
        for _ in range(2000):
            _ = len(payload) + 1
        time.sleep(0.001)


def main() -> None:
    yolox_spec = YoloxPersonDetector.model_spec(YOLOX_MODEL)
    rtmpose_spec = RTMPoseKeypointDetector.model_spec(RTMPOSE_MODEL)

    session = OnnxSession.create(
        OnnxSessionConfig(
            batch_size=BATCH,
            models=[yolox_spec, rtmpose_spec],
            execution_provider=None,
        )
    )
    print(f"\nprovider={session.execution_provider!r} device={session.device_id}")
    print(
        "active ORT providers:",
        session.get_session(rtmpose_spec.name).get_providers(),
    )

    print(f"\n--- ALONE on main thread (batch={BATCH}) ---")
    solo_pose = report(f"{RTMPOSE_MODEL} batch{BATCH}", time_model(session, rtmpose_spec))
    solo_det = report(f"{YOLOX_MODEL} batch{BATCH}", time_model(session, yolox_spec))

    print(f"\n--- on a BACKGROUND thread w/ 3 busy Python threads ---")
    stop = threading.Event()
    noise = [threading.Thread(target=gil_noise, args=(stop,), daemon=True) for _ in range(3)]
    for t in noise:
        t.start()

    results: dict[str, list[float]] = {}

    def run_bg() -> None:
        results["pose"] = time_model(session, rtmpose_spec)
        results["det"] = time_model(session, yolox_spec)

    bg = threading.Thread(target=run_bg)
    bg.start()
    bg.join()
    stop.set()

    con_pose = report(f"{RTMPOSE_MODEL} batch{BATCH}", results["pose"])
    con_det = report(f"{YOLOX_MODEL} batch{BATCH}", results["det"])

    print("\n--- summary ---")
    print(f"  rtmpose slowdown from thread contention: {con_pose / solo_pose:.2f}x")
    print(f"  yolox   slowdown from thread contention: {con_det / solo_det:.2f}x")
    print(f"\n  app reports predict_batch ~205 ms/frame at batch {BATCH}.")
    print(f"  hardware ceiling for one pose batch here: {solo_pose:.1f} ms")

    session.close()


if __name__ == "__main__":
    main()
