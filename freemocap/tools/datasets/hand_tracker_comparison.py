"""Compare Tracker-owned presets on complete recordings without publishing results.

Times direct three-camera tracking calls, not capture, reconstruction or UI FPS.
Each run has fresh Tracker sessions. Repeats reverse order to expose order effects.
"""

import argparse
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np
from skellytracker.core.io.tracker_profiles import tracker_profile
from skellytracker.core.tracker.tracker_presets import human_tracker_config

from freemocap.core.pipeline.dataflow.tracker_adapter import recording_timestamps_ms
from freemocap.core.pipeline.dataflow.video_sources import RecordingVideoSources
from freemocap.core.tracking.tracker_factory import build_configured_tracker
from .preparation import software_identity


def video_digests(sources):
    result = {}
    for source in sources.camera_sources:
        with source.video_metadata.file_path.open("rb") as video:
            result[source.camera_id] = hashlib.file_digest(video, "sha256").hexdigest()
    return result


def run_preset(sources, preset, provider, output):
    camera_ids = tuple(source.camera_id for source in sources.camera_sources)
    timestamps = np.asarray(recording_timestamps_ms(sources), dtype=np.int64)
    profile = tracker_profile(preset)
    config = human_tracker_config(
        preset=preset, video_fps=sources.camera_sources[0].video_metadata.fps
    )
    timings = np.empty(len(timestamps), dtype=np.float64)
    decode_seconds = 0.0
    values = confidence = None
    start = perf_counter()
    with ExitStack() as cleanup:
        tracker = build_configured_tracker(
            config=config, batch_size=len(camera_ids), execution_provider=provider
        )
        cleanup.callback(tracker.close)
        setup_seconds = perf_counter() - start
        evidence = {
            name: session.get_providers()
            for name, session in tracker.sessions["onnx"]._sessions.items()
        }
        required = {"cpu": "CPUExecutionProvider", "cuda": "CUDAExecutionProvider"}[
            provider
        ]
        if any(providers[0] != required for providers in evidence.values()):
            raise RuntimeError(f"Unexpected execution providers: {evidence}")
        captures = []
        for source in sources.camera_sources:
            capture = cv2.VideoCapture(str(source.video_metadata.file_path))
            cleanup.callback(capture.release)
            if not capture.isOpened():
                raise RuntimeError(f"Cannot open {source.video_metadata.file_path}")
            captures.append(capture)
        states = {}
        images = dict.fromkeys(camera_ids)
        for frame_number, timestamp in enumerate(timestamps):
            start = perf_counter()
            for camera_id, capture in zip(camera_ids, captures):
                ok, frame = capture.read()
                if not ok:
                    raise RuntimeError(
                        f"Early end of video: {camera_id}, frame {frame_number}"
                    )
                images[camera_id] = frame
            decode_seconds += perf_counter() - start
            start = perf_counter()
            observations, states = tracker.process_batch(
                images, frame_number, states, timestamp_ms=int(timestamp)
            )
            timings[frame_number] = (perf_counter() - start) * 1000
            for camera_index, camera_id in enumerate(camera_ids):
                points = observations[camera_id].stages["body"].keypoints
                if points.names != profile.keypoint_names:
                    raise ValueError(
                        "Tracker output schema differs from its declared profile"
                    )
                if values is None:
                    values = np.empty(
                        (len(timestamps), len(camera_ids), *points.xyz.shape),
                        dtype=points.xyz.dtype,
                    )
                    confidence = np.empty(
                        values.shape[:-1], dtype=points.visibility.dtype
                    )
                values[frame_number, camera_index] = points.xyz
                confidence[frame_number, camera_index] = points.visibility
    if values is None:
        raise ValueError("Recording contains no frames")
    available = np.isfinite(values[..., :2]).all(axis=-1) & (confidence > 0)
    hand_results = {}
    for side in ("left", "right"):
        indices = np.asarray(
            [
                index
                for index, name in enumerate(profile.keypoint_names)
                if name.startswith(f"{side}_hand_")
            ]
        )
        if not len(indices):
            raise ValueError(f"No {side} hand schema")
        valid = np.take(available, indices, axis=-1)
        hand_results[side] = dict(
            keypoint_count=len(indices),
            available_keypoint_fraction=float(valid.mean()),
            complete_hand_frame_fraction=float(valid.all(axis=-1).mean()),
            per_camera_complete_hand_fraction=valid.all(axis=-1).mean(axis=0).tolist(),
        )
    np.savez_compressed(
        output,
        values=values,
        confidence=confidence,
        tracking_ms=timings,
        keypoint_names=np.asarray(profile.keypoint_names),
        camera_ids=np.asarray(camera_ids),
        timestamps_ms=timestamps,
    )
    report = dict(
        preset=preset,
        frames=len(timestamps),
        camera_ids=camera_ids,
        tracker_config=config.model_dump(mode="json", round_trip=True),
        provider_evidence=evidence,
        setup_seconds=setup_seconds,
        video_decode_seconds=decode_seconds,
        tracking_total_seconds=float(timings.sum() / 1000),
        tracking_mean_ms=float(timings.mean()),
        tracking_median_ms=float(np.median(timings)),
        tracking_p95_ms=float(np.percentile(timings, 95)),
        first_frame_ms=float(timings[0]),
        tracking_mean_after_first_ten_ms=float(timings[10:].mean())
        if len(timings) > 10
        else None,
        hand_availability=hand_results,
    )
    return report, values, confidence


def run_comparison(recording, output, provider, repeats):
    if repeats < 1:
        raise ValueError("Repeats must be positive")
    sources = RecordingVideoSources.resolve(recording)
    if sources.saved_frame_numbers is not None:
        raise ValueError("Comparison requires complete original video frame order")
    output.mkdir(parents=True, exist_ok=False)
    original_hashes = video_digests(sources)
    presets = ("rtmpose", "rtmw_mediapipe_hands")
    common_names = tuple(
        name
        for name in tracker_profile(presets[0]).keypoint_names
        if not name.startswith(("left_hand_", "right_hand_"))
    )
    common_indices = {
        preset: np.asarray(
            [
                tracker_profile(preset).keypoint_names.index(name)
                for name in common_names
            ]
        )
        for preset in presets
    }
    report = dict(
        recording=str(recording),
        provider=provider,
        repeats=repeats,
        meaning="Direct tracking-call cost; includes child detection and assembly; excludes video decoding, output copies, reconstruction and UI",
        availability_definition="Finite image-plane coordinates with positive emitted visibility; no accuracy or confidence-calibration claim",
        timestamp_method=sources.group_timing.method,
        video_sha256=original_hashes,
        software_identity=software_identity(),
        runs=[],
        retained_keypoint_comparisons=[],
    )
    for repeat in range(repeats):
        retained = {}
        for preset in presets if repeat % 2 == 0 else tuple(reversed(presets)):
            result, values, confidence = run_preset(
                sources, preset, provider, output / f"repeat-{repeat}-{preset}.npz"
            )
            result["repeat"] = repeat
            report["runs"].append(result)
            retained[preset] = (
                np.take(values, common_indices[preset], axis=-2),
                np.take(confidence, common_indices[preset], axis=-1),
            )
            print(
                json.dumps(
                    {
                        "repeat": repeat,
                        "preset": preset,
                        "mean_ms": result["tracking_mean_ms"],
                        "hands": result["hand_availability"],
                    }
                ),
                flush=True,
            )
        comparisons = [
            np.array_equal(left, right, equal_nan=True)
            for left, right in zip(retained[presets[0]], retained[presets[1]])
        ]
        report["retained_keypoint_comparisons"].append(
            dict(
                repeat=repeat,
                keypoint_count=len(common_names),
                values_exact=comparisons[0],
                visibility_exact=comparisons[1],
            )
        )
    if video_digests(sources) != original_hashes:
        raise RuntimeError("Source video bytes changed during comparison")
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if not all(
        item["values_exact"] and item["visibility_exact"]
        for item in report["retained_keypoint_comparisons"]
    ):
        raise AssertionError(
            "Retained RTMW keypoints changed; inspect comparison reports"
        )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recording", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--execution-provider", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args()
    run_comparison(args.recording, args.output, args.execution_provider, args.repeats)


if __name__ == "__main__":
    main()
