"""Which branch of BBoxPolicy.should_redetect keeps firing?

Run:  .venv/Scripts/python.exe bench_redetect.py
"""

import collections
import logging
from pathlib import Path

import cv2

logging.basicConfig(level=logging.WARNING, format="%(message)s")

from skellytracker.core.temporal_processing.bbox_policy import BBoxPolicy

from freemocap.core.tracking.tracker_factory import (
    build_configured_tracker,
    skeleton_tracker_config,
)

RECORDING = Path(
    r"C:\Users\jonma\freemocap_data\recordings\2026-08-24_08-08-44_GMT-4_calibration"
)
N_FRAMES = 40
REASONS: collections.Counter = collections.Counter()
DETAIL: list[str] = []

_orig = BBoxPolicy.should_redetect


def traced(self, frame_number, stage_state):
    last = stage_state.bbox_state.last_detection_frame
    if last is None:
        REASONS["last_detection_frame is None"] += 1
        if len(DETAIL) < 10:
            DETAIL.append(
                f"  f{frame_number}: last=None  "
                f"smooth_bbox={stage_state.bbox_state.smooth_bbox is not None} "
                f"last_detected={stage_state.bbox_state.last_detected_bbox is not None} "
                f"kpts={stage_state.last_keypoints is not None}"
            )
        return True
    if (frame_number - last) >= self.redetect_interval:
        REASONS[f"interval elapsed (>= {self.redetect_interval})"] += 1
        return True
    for check in self.fitness_checks:
        if check.fails(frame_number, stage_state):
            REASONS[f"fitness check {type(check).__name__}"] += 1
            kpts = stage_state.last_keypoints
            bbox = stage_state.bbox_state.smooth_bbox
            if len(DETAIL) < 10 and kpts is not None and bbox is not None:
                xy = kpts.xy[kpts.valid_mask]
                inside = (
                    (xy[:, 0] >= bbox.x1) & (xy[:, 0] <= bbox.x2)
                    & (xy[:, 1] >= bbox.y1) & (xy[:, 1] <= bbox.y2)
                )
                DETAIL.append(
                    f"  f{frame_number}: {inside.mean():.2f} of {kpts.n_valid} valid kpts "
                    f"inside bbox {bbox.width:.0f}x{bbox.height:.0f} (need >= 0.50)"
                )
            return True
    REASONS["skipped (detector NOT run)"] += 1
    return False


BBoxPolicy.should_redetect = traced


def main() -> None:
    videos = sorted((RECORDING / "synchronized_videos").glob("*.mp4"))
    caps = {v.name.split(".id-")[1].split(".")[0]: cv2.VideoCapture(str(v)) for v in videos}

    config = skeleton_tracker_config(
        model_name="rtmw-x-l_256x192", confidence_threshold=0.0025,
        video_fps=30.0, keypoint_bbox_expansion=0.05,
    )
    tracker = build_configured_tracker(config=config, batch_size=len(caps))
    states: dict = {}

    for frame_number in range(N_FRAMES):
        images = {}
        for cam_id, cap in caps.items():
            ok, img = cap.read()
            if ok:
                images[cam_id] = img
        if len(images) != len(caps):
            break
        _, states = tracker.process_batch(
            images=images, frame_number=frame_number, states=states
        )

    for cap in caps.values():
        cap.release()

    total = sum(REASONS.values())
    print(f"\n=== should_redetect decisions ({total} stage-evaluations) ===")
    for reason, count in REASONS.most_common():
        print(f"  {count:5d}  ({100*count/total:5.1f}%)  {reason}")
    print("\nsamples:")
    for line in DETAIL:
        print(line)
    tracker.close()


if __name__ == "__main__":
    main()
