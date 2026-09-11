"""Run the real realtime tracker over 5 synchronized videos and show where
predict_batch time actually goes.

Instruments OnnxSession.run so we can count, per frame, how many times each
model is invoked and with what batch shape. That tells us whether the person
detector is being skipped (redetect_interval=150) or re-run every frame.

Run:  .venv/Scripts/python.exe bench_tracker.py
"""

import collections
import logging
import statistics
import sys
import time
from pathlib import Path

import cv2
import numpy as np

logging.basicConfig(level=logging.WARNING, format="%(message)s")

from skellytracker.core.sessions.onnx_session import OnnxSession

from freemocap.core.tracking.tracker_factory import (
    build_configured_tracker,
    skeleton_tracker_config,
)

RECORDING = Path(
    r"C:\Users\jonma\freemocap_data\recordings\2026-08-24_08-08-44_GMT-4_calibration"
)
N_FRAMES = 220
MODEL = "rtmw-x-l_256x192"

# ---- instrument every ORT call -------------------------------------------
CALLS: list[tuple[str, tuple, float]] = []
_orig_run = OnnxSession.run


def _counting_run(self, model_name, inputs, output_names=None):
    shape = next(iter(inputs.values())).shape if inputs else ()
    t0 = time.perf_counter()
    out = _orig_run(self, model_name, inputs, output_names)
    CALLS.append((model_name, tuple(shape), (time.perf_counter() - t0) * 1e3))
    return out


OnnxSession.run = _counting_run
# --------------------------------------------------------------------------


def main() -> None:
    videos = sorted((RECORDING / "synchronized_videos").glob("*.mp4"))
    if not videos:
        sys.exit(f"no videos under {RECORDING}")
    caps = {v.name.split(".id-")[1].split(".")[0]: cv2.VideoCapture(str(v)) for v in videos}
    print(f"cameras: {list(caps)}")

    config = skeleton_tracker_config(
        model_name=MODEL,
        confidence_threshold=0.0025,
        video_fps=30.0,
        keypoint_bbox_expansion=0.05,
    )
    print(f"redetect_interval = {config.stages[0].bbox_policy.redetect_interval}")

    tracker = build_configured_tracker(config=config, batch_size=len(caps))
    states: dict = {}

    per_frame: list[float] = []
    calls_per_frame: list[collections.Counter] = []
    n_bboxes: list[int] = []

    for frame_number in range(N_FRAMES):
        images = {}
        for cam_id, cap in caps.items():
            ok, img = cap.read()
            if ok:
                images[cam_id] = img
        if len(images) != len(caps):
            break

        CALLS.clear()
        t0 = time.perf_counter()
        observations, states = tracker.process_batch(
            images=images, frame_number=frame_number, states=states
        )
        elapsed = (time.perf_counter() - t0) * 1e3

        counter = collections.Counter(name for name, _, _ in CALLS)
        found = sum(
            1
            for obs in observations.values()
            if (st := obs.stages.get("body")) is not None and st.keypoints is not None
        )
        if frame_number >= 5:  # skip warm-up frames
            per_frame.append(elapsed)
            calls_per_frame.append(counter)
            n_bboxes.append(found)

        if frame_number < 12 or frame_number % 10 == 0:
            detail = "  ".join(
                f"{n}x{name}{shape}={ms:.0f}ms"
                for (name, shape, ms) in (
                    (name, shape, ms) for name, shape, ms in CALLS
                )
                for n in [1]
            )
            print(f"frame {frame_number:3d}  {elapsed:7.1f} ms  people={found}  | {detail}")

    for cap in caps.values():
        cap.release()

    if not per_frame:
        sys.exit("no frames measured")

    print("\n================ steady state ================")
    print(f"frames measured           : {len(per_frame)}")
    print(f"process_batch median      : {statistics.median(per_frame):.1f} ms")
    print(f"process_batch min / max   : {min(per_frame):.1f} / {max(per_frame):.1f} ms")
    print(f"cameras with keypoints    : {statistics.median(n_bboxes)} (median)")

    models = sorted({m for c in calls_per_frame for m in c})
    print("\nORT invocations per frame (how often each model runs):")
    for model in models:
        counts = [c.get(model, 0) for c in calls_per_frame]
        ran = sum(1 for x in counts if x)
        print(
            f"  {model:<22} ran on {ran}/{len(counts)} frames "
            f"({100*ran/len(counts):.0f}%)   calls/frame median={statistics.median(counts)}"
        )

    total_gpu = statistics.median(per_frame)
    print(
        f"\nIf the detector runs every frame it costs ~82 ms of the "
        f"{total_gpu:.0f} ms budget on this GPU."
    )
    tracker.close()


if __name__ == "__main__":
    main()
