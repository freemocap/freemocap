"""Compare candidate bbox-fitness policies on real 5-camera footage.

Reports MEAN frame time (sustained throughput is governed by the mean, not the
median — the current policy produces a bimodal distribution that a median hides).

A = current              keypoints_within_bbox_ratio @ 0.5   (compares keypoints
                         against smooth_bbox, which is NOT the region RTMPose
                         decodes into -> false positives)
B = no fitness checks    upper bound on speed
C = bbox_area_collapse   catches "person left / track switched"
D = corrected containment check: same intent as A, but measured against the
    region the model actually decodes into (1.25x padding + model aspect),
    body keypoints only, and inert when too few points are available

Run:  .venv/Scripts/python.exe bench_final.py
"""

import collections
import logging
import statistics
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

logging.basicConfig(level=logging.WARNING, format="%(message)s")

from skellytracker.core.data_primitives.bounding_box import BoundingBox
from skellytracker.core.detectors.keypoint_detectors.rtmpose.rtmpose_preprocessing import (
    bbox_xyxy2cs,
)
from skellytracker.core.sessions.onnx_session import OnnxSession
from skellytracker.core.temporal_processing.temporal_processing_config import (
    BBoxAreaCollapseConfig,
    KeypointsWithinBBoxRatioConfig,
)

from freemocap.core.tracking.tracker_factory import (
    build_configured_tracker,
    skeleton_tracker_config,
)

RECORDING = Path(
    r"C:\Users\jonma\freemocap_data\recordings\2026-08-24_08-08-44_GMT-4_calibration"
)
N_FRAMES = 220
WARMUP = 5
MODEL_INPUT = (256, 192)  # (H, W)

CALLS: collections.Counter = collections.Counter()
_orig_run = OnnxSession.run


def _counting_run(self, model_name, inputs, output_names=None):
    CALLS[model_name] += 1
    return _orig_run(self, model_name, inputs, output_names)


OnnxSession.run = _counting_run


def _decode_window(bbox: BoundingBox) -> BoundingBox:
    """Region RTMPose actually decodes into: 1.25x padding + model aspect."""
    arr = np.array([bbox.x1, bbox.y1, bbox.x2, bbox.y2], dtype=np.float64)
    center, scale = bbox_xyxy2cs(arr, padding=1.25)
    h, w = MODEL_INPUT
    aspect = w / h
    bw, bh = float(scale[0]), float(scale[1])
    sw, sh = (bw, bw / aspect) if bw > bh * aspect else (bh * aspect, bh)
    cx, cy = float(center[0]), float(center[1])
    return BoundingBox(x1=cx - sw / 2, y1=cy - sh / 2, x2=cx + sw / 2, y2=cy + sh / 2)


_FACE_HAND = ("eye", "ear", "nose", "mouth", "lip", "face",
              "thumb", "index", "middle", "ring", "pinky", "finger", "hand")


@dataclass
class CorrectedContainmentCheck:
    """Proposed replacement for KeypointsWithinBBoxRatioCheck."""

    threshold: float = 0.5
    min_visibility: float = 0.0
    min_points: int = 4

    def fails(self, frame_number: int, stage_state) -> bool:
        kpts = stage_state.last_keypoints
        bbox = stage_state.bbox_state.smooth_bbox
        if kpts is None or bbox is None:
            return False
        mask = kpts.valid_mask
        if self.min_visibility > 0.0:
            mask = mask & (kpts.visibility >= self.min_visibility)
        body = np.array(
            [not any(t in n.lower() for t in _FACE_HAND) for n in kpts.names]
        )
        mask = mask & body
        if int(mask.sum()) < self.min_points:
            return False  # not enough evidence to claim the crop drifted
        window = _decode_window(bbox)
        xy = kpts.xy[mask]
        inside = (
            (xy[:, 0] >= window.x1) & (xy[:, 0] <= window.x2)
            & (xy[:, 1] >= window.y1) & (xy[:, 1] <= window.y2)
        )
        return float(inside.mean()) < self.threshold


def run_case(label: str, checks: list, override=None) -> tuple[float, int, int]:
    videos = sorted((RECORDING / "synchronized_videos").glob("*.mp4"))
    caps = {v.name.split(".id-")[1].split(".")[0]: cv2.VideoCapture(str(v)) for v in videos}

    config = skeleton_tracker_config(
        model_name="rtmw-x-l_256x192", confidence_threshold=0.0025,
        video_fps=30.0, keypoint_bbox_expansion=0.05,
    )
    config.stages[0].bbox_policy.fitness_checks = checks
    tracker = build_configured_tracker(config=config, batch_size=len(caps))
    if override is not None:
        tracker.stages[0].bbox_policy.fitness_checks = [override]

    states: dict = {}
    CALLS.clear()
    times: list[float] = []
    locked: list[int] = []
    detector_frames = 0

    for frame_number in range(N_FRAMES):
        images = {}
        for cam_id, cap in caps.items():
            ok, img = cap.read()
            if ok:
                images[cam_id] = img
        if len(images) != len(caps):
            break
        before = sum(v for k, v in CALLS.items() if "yolox" in k)
        t0 = time.perf_counter()
        observations, states = tracker.process_batch(
            images=images, frame_number=frame_number, states=states
        )
        elapsed = (time.perf_counter() - t0) * 1e3
        after = sum(v for k, v in CALLS.items() if "yolox" in k)
        if frame_number >= WARMUP:
            times.append(elapsed)
            detector_frames += after - before
            locked.append(sum(
                1 for obs in observations.values()
                if (st := obs.stages.get("body")) is not None and st.keypoints is not None
            ))

    for cap in caps.values():
        cap.release()
    tracker.close()

    mean = statistics.mean(times)
    print(
        f"  {label:<44} mean {mean:6.1f} ms -> {1000/mean:5.1f} fps   "
        f"detector on {100*detector_frames/len(times):5.1f}% of frames   "
        f"tracked {statistics.median(locked):.0f}/5"
    )
    return mean, detector_frames, len(times)


def main() -> None:
    print(f"\n5 cameras, rtmw-x-l_256x192, {N_FRAMES - WARMUP} measured frames\n")
    a, _, _ = run_case("A  current (within_bbox_ratio 0.5)",
                       [KeypointsWithinBBoxRatioConfig(threshold=0.5)])
    b, _, _ = run_case("B  no fitness checks", [])
    c, _, _ = run_case("C  bbox_area_collapse",
                       [BBoxAreaCollapseConfig(min_area_ratio=0.25, expansion_ratio=0.05,
                                               min_visibility=0.0)])
    d, _, _ = run_case("D  corrected containment check (FIX)",
                       [KeypointsWithinBBoxRatioConfig(threshold=0.5)],
                       override=CorrectedContainmentCheck(threshold=0.5, min_points=4))

    print("\n--- speedup vs current ---")
    print(f"  B {a/b:.2f}x     C {a/c:.2f}x     D {a/d:.2f}x")
    print("\n  detector call costs ~101 ms/frame here (82 ms ORT + numpy letterbox/NMS)")


if __name__ == "__main__":
    main()


# --- ablation: does "body keypoints only" alone fix it, without the window fix? ---
@dataclass
class BodyOnlyVsSmoothBBox:
    """User's proposal: same comparison box, but body keypoints only."""

    threshold: float = 0.5
    _body: object = None

    def fails(self, frame_number: int, stage_state) -> bool:
        kpts = stage_state.last_keypoints
        bbox = stage_state.bbox_state.smooth_bbox
        if kpts is None or bbox is None:
            return False
        if self._body is None:
            self._body = np.array(
                [not any(t in n.lower() for t in _FACE_HAND) for n in kpts.names]
            )
        mask = kpts.valid_mask & self._body
        if not mask.any():
            return False
        xy = kpts.xy[mask]
        inside = (
            (xy[:, 0] >= bbox.x1) & (xy[:, 0] <= bbox.x2)
            & (xy[:, 1] >= bbox.y1) & (xy[:, 1] <= bbox.y2)
        )
        return float(inside.mean()) < self.threshold


if __name__ == "__main__" and True:
    pass
