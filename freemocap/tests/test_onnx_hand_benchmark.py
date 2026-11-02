"""Opt-in complete hybrid tracking benchmark using prepared reference recordings.

W4_BENCHMARK_PROVIDER enables execution (cpu/cuda). CUDA additionally requires
W4_GPU_SLOT_GRANTED=1, set only after the coordinator assigns an exclusive slot.
W4_BENCHMARK_FRAMES defaults to the complete recordings; CPU smoke can limit it.
Results exclude video decoding and report that cost separately. Provider traces
come from a separate, untimed run including factory warmup and recorded images.
"""

from collections import Counter
from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
import onnxruntime as ort
import pytest

from freemocap.tests.test_experimental_onnx_hands import (
    DATASETS,
    combined_tracker_config,
    experimental_tracker_config,
    file_hash,
    open_videos,
    read_images,
    reference_inputs,
    build_tracker,
    tracker_profile,
    mediapipe_hand_names,
)


@pytest.mark.parametrize("dataset", DATASETS)
def test_complete_hybrid_benchmark(dataset, monkeypatch):
    provider = os.environ.get("W4_BENCHMARK_PROVIDER")
    if provider is None:
        pytest.skip("Opt-in benchmark; no automatic device allocation")
    assert provider in ("cpu", "cuda")
    if provider == "cuda":
        assert os.environ.get("W4_GPU_SLOT_GRANTED") == "1", (
            "Exclusive GPU grant required"
        )
    output = Path(os.environ["W4_BENCHMARK_OUTPUT_DIR"])
    assert output.is_dir(), "Supply a precreated ignored evidence directory"
    phase = os.environ.get("W4_BENCHMARK_PHASE")
    if phase is None:
        # Each repetition gets fresh native-library state. A preceding sequential
        # prototype hit a MediaPipe invalid-handle failure during repeated task
        # creation; isolation does not claim to fix that lifecycle defect.
        deadline = time.monotonic() + 1200
        cases = [
            ("timing", method, repeat)
            for repeat, ordering in enumerate(
                (("baseline", "candidate"), ("candidate", "baseline"))
            )
            for method in ordering
        ]
        cases += [("profile", method, 0) for method in ("baseline", "candidate")]
        reports = []
        for case_phase, method, repeat in cases:
            stem = f"{dataset}-{provider}-{case_phase}-{method}-{repeat}"
            environment = dict(
                os.environ,
                W4_BENCHMARK_PHASE=case_phase,
                W4_BENCHMARK_METHOD=method,
                W4_BENCHMARK_REPEAT=str(repeat),
            )
            with (output / f"{stem}.log").open("wb") as log:
                result = subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        "-m",
                        "pytest",
                        f"{__file__}::test_complete_hybrid_benchmark[{dataset}]",
                        "-q",
                        # Keep native stdout/stderr handles stable on Windows.
                        # Live pytest logging suspends/resumes FD capture; a
                        # native library can retain a handle that capture closes.
                        # The subprocess log still retains all native output.
                        "-s",
                        "-p",
                        "no:cacheprovider",
                        f"--junitxml={output / (stem + '.xml')}",
                    ],
                    env=environment,
                    cwd=Path(__file__).resolve().parents[2],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=max(1, min(600, deadline - time.monotonic())),
                )
            assert result.returncode == 0, (
                f"Benchmark child failed; inspect {output / (stem + '.log')}"
            )
            reports.append(
                json.loads((output / f"{stem}.json").read_text(encoding="utf-8"))
            )
        assert all(
            report["source_hashes"] == reports[0]["source_hashes"] for report in reports
        )
        (output / f"{dataset}-{provider}-summary.json").write_text(
            json.dumps(
                dict(dataset=dataset, provider=provider, cases=reports), indent=2
            ),
            encoding="utf-8",
        )
        return
    assert phase in ("timing", "profile")
    selected_method = os.environ["W4_BENCHMARK_METHOD"]
    selected_repeat = int(os.environ["W4_BENCHMARK_REPEAT"])
    videos, source_seconds, timestamps, candidate_directory = reference_inputs(dataset)
    frame_limit = int(os.environ.get("W4_BENCHMARK_FRAMES", "0")) or len(timestamps)
    frame_limit = min(frame_limit, len(timestamps))
    assert frame_limit >= 3
    warmup_frames = min(30, frame_limit // 3)
    fps = next(iter(videos.values())).fps
    configs = {
        "baseline": combined_tracker_config(video_fps=fps),
        "candidate": experimental_tracker_config(
            model_directory=candidate_directory, video_fps=fps
        ),
    }
    options = dict(
        execution_provider=provider,
        fp16=False,
        intra_op_num_threads=1,
        device_id=0,
        gpu_mem_limit=1024**3,
    )
    expected_provider = (
        "CUDAExecutionProvider" if provider == "cuda" else "CPUExecutionProvider"
    )
    source_hashes = {
        camera: file_hash(metadata.file_path) for camera, metadata in videos.items()
    }
    measurements = []
    deadline = time.monotonic() + 1200
    keypoint_profile = tracker_profile("rtmw_mediapipe_hands")
    hand_sides = ("right", "left")
    hand_indices = np.asarray(
        [
            [
                keypoint_profile.keypoint_names.index(name)
                for name in mediapipe_hand_names(side)
            ]
            for side in hand_sides
        ]
    )

    def execute(method, count, profile=False):
        started = time.perf_counter()
        with ExitStack() as cleanup:
            tracker = build_tracker(
                configs[method], batch_size=len(videos), onnx_overrides=options
            )
            cleanup.callback(tracker.close)
            construction_seconds = time.perf_counter() - started
            native_sessions = tracker.sessions["onnx"]._sessions
            providers = {
                name: native.get_providers() for name, native in native_sessions.items()
            }
            provider_options = {
                name: native.get_provider_options()
                for name, native in native_sessions.items()
            }
            model_io_types = {
                name: {
                    "inputs": {item.name: item.type for item in native.get_inputs()},
                    "outputs": {item.name: item.type for item in native.get_outputs()},
                }
                for name, native in native_sessions.items()
            }
            assert all(value[0] == expected_provider for value in providers.values())
            captures = open_videos(videos, cleanup)
            states = {}
            elapsed_ms = np.empty((count, 2), dtype=np.float64)
            visible_counts = np.empty((count, len(videos)), dtype=np.int64)
            hand_values = np.empty(
                (count, len(videos), *hand_indices.shape, 3), dtype=np.float64
            )
            hand_scores = np.empty(hand_values.shape[:-1], dtype=np.float64)
            hand_corners = np.full((count, len(videos), len(hand_sides), 4), np.nan)
            for frame, timestamp in enumerate(timestamps[:count]):
                assert time.monotonic() < deadline, (
                    "Benchmark exceeded its 20-minute dataset bound"
                )
                before_read = time.perf_counter_ns()
                images = read_images(captures)
                before_tracking = time.perf_counter_ns()
                observations, states = tracker.process_batch(
                    images, frame, states, timestamp_ms=int(timestamp)
                )
                after_tracking = time.perf_counter_ns()
                elapsed_ms[frame] = (
                    (before_tracking - before_read) / 1e6,
                    (after_tracking - before_tracking) / 1e6,
                )
                assert observations.keys() == images.keys()
                visible_counts[frame] = [
                    observations[camera].stages["body"].keypoints.n_valid
                    for camera in videos
                ]
                for camera_index, camera in enumerate(videos):
                    body = observations[camera].stages["body"]
                    assert body.keypoints.names == keypoint_profile.keypoint_names
                    hand_values[frame, camera_index] = body.keypoints.xyz[hand_indices]
                    hand_scores[frame, camera_index] = body.keypoints.visibility[
                        hand_indices
                    ]
                    for side_index, side in enumerate(hand_sides):
                        child = body.children.get(f"{side}_hand")
                        if child is not None and child.bounding_boxes:
                            (box,) = child.bounding_boxes
                            hand_corners[frame, camera_index, side_index] = (
                                box.x1,
                                box.y1,
                                box.x2,
                                box.y2,
                            )
                if frame % 100 == 0:
                    print(f"{dataset} {method} {frame + 1}/{count}", flush=True)
            traces = {}
            if profile:
                for name, native in native_sessions.items():
                    path = Path(native.end_profiling())
                    events = json.loads(path.read_text(encoding="utf-8"))
                    counts = Counter(
                        event.get("args", {}).get("provider")
                        for event in events
                        if event.get("cat") == "Node"
                    )
                    counts.pop(None, None)
                    assert counts[expected_provider] > 0, (name, counts)
                    traces[name] = {
                        "path": str(path),
                        "node_events_by_provider": dict(counts),
                    }
            return (
                elapsed_ms,
                visible_counts,
                (hand_values, hand_scores, hand_corners),
                dict(
                    construction_seconds=construction_seconds,
                    providers=providers,
                    provider_options=provider_options,
                    model_io_types=model_io_types,
                    traces=traces,
                ),
            )

    # Alternate ordering; close the preceding tracker before allocating the next.
    for repeat, ordering in (
        [(selected_repeat, (selected_method,))] if phase == "timing" else []
    ):
        for method in ordering:
            elapsed, visible, hand_arrays, details = execute(method, frame_limit)
            stable = elapsed[warmup_frames:, 1]
            stem = f"{dataset}-{provider}-{method}-{repeat}"
            np.savez(
                output / f"{stem}.npz",
                read_tracking_ms=elapsed,
                visible_keypoint_counts=visible,
                source_seconds=source_seconds[:frame_limit],
                camera_ids=np.asarray(tuple(videos)),
                hand_values=hand_arrays[0],
                hand_scores=hand_arrays[1],
                hand_corners=hand_arrays[2],
                hand_sides=np.asarray(hand_sides),
                frame_numbers=np.arange(frame_limit),
                tracker_timestamps_ms=timestamps[:frame_limit],
            )
            record = dict(
                method=method,
                repeat=repeat,
                frames=frame_limit,
                excluded_initial_frames=warmup_frames,
                mean_tracking_ms=float(stable.mean()),
                p50_tracking_ms=float(np.median(stable)),
                p95_tracking_ms=float(np.percentile(stable, 95)),
                first_frame_tracking_ms=float(elapsed[0, 1]),
                mean_video_read_ms=float(elapsed[:, 0].mean()),
                **details,
            )
            measurements.append(record)
            (output / f"{stem}.json").write_text(
                json.dumps(record, indent=2), encoding="utf-8"
            )

    profile_reports = {}
    options_type = ort.SessionOptions
    profile_number = 0

    def profiling_options():
        nonlocal profile_number
        settings = options_type()
        settings.enable_profiling = True
        settings.profile_file_prefix = str(
            output / f"{dataset}-{provider}-profile-{profile_number}"
        )
        profile_number += 1
        return settings

    # Only this untimed diagnostic enables ORT profiling; runtime source unchanged.
    with monkeypatch.context() as patch:
        patch.setattr(ort, "SessionOptions", profiling_options)
        for method in [selected_method] if phase == "profile" else []:
            _, _, _, profile_reports[method] = execute(method, 3, profile=True)
    assert source_hashes == {
        camera: file_hash(metadata.file_path) for camera, metadata in videos.items()
    }
    report = dict(
        dataset=dataset,
        provider=provider,
        camera_count=len(videos),
        source_hashes=source_hashes,
        onnx_options=options,
        measurements=measurements,
        profile_reports=profile_reports,
        profiling_scope="Separate run: session warmup and three recorded frames; excluded from timings",
        timing_scope="Tracker.process_batch: detection, crops, hands, temporal filters and assembly; excludes video decode, mapping, reconstruction, transport and UI",
    )
    (
        output
        / f"{dataset}-{provider}-{phase}-{selected_method}-{selected_repeat}.json"
    ).write_text(json.dumps(report, indent=2), encoding="utf-8")
