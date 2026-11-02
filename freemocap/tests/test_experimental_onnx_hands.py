"""Exercise Tracker's opt-in experiment with Core's prepared recording/timing adapters."""

from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path

import cv2
import numpy as np
import pytest

from freemocap.tests.reference_paths import prepared_root
from freemocap.core.pipeline.posthoc.video_group_helper import VideoGroupHelper
from freemocap.core.reconstruction.recording_timing import RecordingGroupTiming
from skellytracker.core.detectors.keypoint_detectors.mediapipe_onnx.experimental_recipe import (
    experimental_tracker_config,
)
from skellytracker.core.io.tracker_profiles import tracker_profile
from skellytracker.core.tracker.tracker_factory import build_tracker
from skellytracker.core.tracker.tracker_presets import combined_tracker_config
from skellytracker.core.detectors.detection_context import DetectionContext
from skellytracker.core.io.tracker_profiles import mediapipe_hand_names


DATASETS = ("freemocap_test_data", "freemocap_sample_data")
CPU_OPTIONS = {"execution_provider": "cpu", "fp16": False, "intra_op_num_threads": 1}


def test_realtime_app_preset_resolves_tracker_and_crop_transport(monkeypatch, tmp_path):
    from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
    from freemocap.core.tracking.tracker_factory import tracker_session_requests
    from freemocap.core.streaming.channel_helpers import detector_crop_paths

    monkeypatch.setenv("SKELLYTRACKER_HAND_CANDIDATE_DIR", str(tmp_path))
    camera = CameraNodeConfig(detector_type="rtmw_onnx_hands")
    baseline = CameraNodeConfig(detector_type="rtmw_mediapipe_hands")
    assert camera.skeleton_tracker_config.keypoint_assembly == baseline.skeleton_tracker_config.keypoint_assembly
    assert detector_crop_paths(camera.detector_type) == detector_crop_paths(baseline.detector_type)
    restored = CameraNodeConfig.model_validate_json(camera.model_dump_json(round_trip=True))
    assert restored == camera
    requests = tracker_session_requests(config=camera.skeleton_tracker_config,
                                       batch_size=3, execution_provider="cuda")
    onnx, = (request.config for request in requests if request.config.backend == "onnx")
    assert len(onnx.models) == 4
    assert onnx.execution_provider == "cuda"
    assert all(request.config.backend != "mediapipe" for request in requests)


@pytest.mark.parametrize("dataset_name", DATASETS)
def test_reference_tensor_provenance_matches_current_forge(dataset_name, tmp_path):
    from freemocap.core.recording.exports.arrays import available_channels
    from freemocap.core.recording.exports.numpy_dataset import saved_channel_tensor
    from freemocap.core.recording.parquet_storage.recording_view import recording_view
    from skellyforge.core.data_tensors import DataProvenance, TimeSeries

    ready = prepared_root() / dataset_name / "ready.json"
    if not ready.is_file():
        pytest.skip("Prepared reference required")
    recording = Path(json.loads(ready.read_text(encoding="utf-8"))["recording"])
    parquet = recording / f"{dataset_name}_data.parquet"
    original_hash = file_hash(parquet)
    checked = 0
    with recording_view(parquet) as view:
        run_id = view.metadata.selected_run_id
        for item in available_channels(view.metadata.runs[run_id]):
            with saved_channel_tensor(
                view, run_id, item, source_hash=original_hash, scratch=tmp_path,
            ) as values:
                tensor = values.data_tensor if isinstance(values, TimeSeries) else values
                assert isinstance(tensor.data_provenance, DataProvenance)
                assert tensor.data_provenance.operation_id == f"saved_stage:{item[1].stage}"
                assert tensor.data_provenance.input_refs == (f"parquet_sha256:{original_hash}",)
                checked += 1
    assert checked > 0
    assert file_hash(parquet) == original_hash


def reference_inputs(dataset_name):
    ready = prepared_root() / dataset_name / "ready.json"
    candidate_directory = os.environ.get("SKELLYTRACKER_HAND_CANDIDATE_DIR")
    if not ready.is_file() or not candidate_directory:
        pytest.skip("Prepared references and pinned candidate directory required")
    recording = Path(json.loads(ready.read_text(encoding="utf-8"))["recording"])
    group = VideoGroupHelper.from_recording_path(recording_path=str(recording))
    try:
        videos = group.video_metadata_by_id
        timing = RecordingGroupTiming.resolve(
            recording_folder=recording,
            videos=videos,
            frame_numbers=tuple(range(group.frame_count)),
        )
    finally:
        group.close()
    source_seconds = np.asarray(timing.synchronized.timestamps_s)
    timestamps = np.rint((source_seconds - source_seconds[0]) * 1000).astype(np.int64)
    assert np.all(np.diff(timestamps) > 0)
    return videos, source_seconds, timestamps, Path(candidate_directory)


def open_videos(videos, cleanup):
    captures = {}
    for camera, metadata in videos.items():
        capture = cv2.VideoCapture(str(metadata.file_path))
        cleanup.callback(capture.release)
        assert capture.isOpened()
        captures[camera] = capture
    return captures


def read_images(captures):
    images = {}
    for camera, capture in captures.items():
        success, image = capture.read()
        assert success
        images[camera] = image
    return images


@pytest.mark.parametrize("dataset_name", DATASETS)
def test_experimental_hybrid_constructs_on_reference_frames(dataset_name):
    from freemocap.core.pipeline.posthoc.annotation_style import build_observation_annotator

    videos, _, timestamps, candidate_directory = reference_inputs(dataset_name)
    config = experimental_tracker_config(
        model_directory=candidate_directory,
        video_fps=next(iter(videos.values())).fps,
    )
    profile = tracker_profile(config.preset_name)
    annotator = build_observation_annotator(config)
    body_indices = np.asarray(
        [
            index
            for index, name in enumerate(profile.keypoint_names)
            if not name.startswith(("right_hand_", "left_hand_"))
        ]
    )
    with ExitStack() as cleanup:
        tracker = build_tracker(
            config, batch_size=len(videos), onnx_overrides=CPU_OPTIONS
        )
        cleanup.callback(tracker.close)
        baseline = build_tracker(
            combined_tracker_config(video_fps=next(iter(videos.values())).fps),
            batch_size=len(videos),
            onnx_overrides=CPU_OPTIONS,
        )
        cleanup.callback(baseline.close)
        session = tracker.sessions["onnx"]
        assert len(session._sessions) == 4
        assert all(
            native.get_providers() == ["CPUExecutionProvider"]
            for native in session._sessions.values()
        )
        captures = open_videos(videos, cleanup)
        states = {}
        baseline_states = {}
        for frame_number, timestamp in enumerate(timestamps[:3]):
            images = read_images(captures)
            observations, states = tracker.process_batch(
                images,
                frame_number,
                states,
                timestamp_ms=int(timestamp),
            )
            baseline_observations, baseline_states = baseline.process_batch(
                images,
                frame_number,
                baseline_states,
                timestamp_ms=int(timestamp),
            )
            assert set(observations) == set(videos)
            for camera, observation in observations.items():
                points = observation.stages["body"].keypoints
                assert (
                    points.names
                    == tracker_profile("rtmw_mediapipe_hands").keypoint_names
                )
                assert points.n_valid > 0
                annotated = annotator.annotate(images[camera], observation)
                assert annotated.shape == images[camera].shape
                assert annotated.dtype == images[camera].dtype
                assert not np.shares_memory(annotated, images[camera])
                assert np.any(annotated != images[camera])
                baseline_body = baseline_observations[camera].stages["body"]
                np.testing.assert_array_equal(
                    points.xyz[body_indices], baseline_body.keypoints.xyz[body_indices]
                )
                np.testing.assert_array_equal(
                    points.visibility[body_indices],
                    baseline_body.keypoints.visibility[body_indices],
                )
                for side in ("right", "left"):
                    assert (
                        observation.stages["body"]
                        .children[f"{side}_hand"]
                        .bounding_boxes
                        == baseline_body.children[f"{side}_hand"].bounding_boxes
                    )
                assert (
                    states[camera].stage_states["body"].last_timestamp_ms == timestamp
                )


def file_hash(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def available(points):
    return np.isfinite(points.xyz).all(axis=-1) & (points.visibility > 0)


def assert_missing(points):
    assert np.isnan(points.xyz).all()
    assert not points.visibility.any()


def check_recorded_reacquisition(detector, examples):
    """Exercise positive -> missing -> positive using actual recorded hand pixels."""
    retained = []
    for count in (1, len(examples), max(1, len(examples) - 1), 1):
        inputs = dict(list(reversed(list(examples.items())))[:count])
        batch = detector.detect_batch(inputs, DetectionContext(timestamp_ms=1000))
        assert batch.keys() == inputs.keys()
        for camera, crop in inputs.items():
            single = detector.detect(crop, DetectionContext(timestamp_ms=1000))
            assert available(single).any()
            np.testing.assert_allclose(
                batch[camera].xyz, single.xyz, rtol=1e-4, atol=1e-3, equal_nan=True
            )
            np.testing.assert_array_equal(batch[camera].visibility, single.visibility)
            retained.append(
                (
                    batch[camera],
                    batch[camera].xyz.copy(),
                    batch[camera].visibility.copy(),
                )
            )
        empty = detector.detect_batch(
            {camera: crop[:0, :0] for camera, crop in inputs.items()}
        )
        blank = detector.detect_batch(
            {camera: np.zeros_like(crop) for camera, crop in inputs.items()}
        )
        for camera in inputs:
            assert_missing(empty[camera])
            assert_missing(blank[camera])
        restored = detector.detect_batch(inputs, DetectionContext(timestamp_ms=1500))
        for camera in inputs:
            # A stateless detector must recover on the very first returning frame.
            np.testing.assert_array_equal(restored[camera].xyz, batch[camera].xyz)
            np.testing.assert_array_equal(
                restored[camera].visibility, batch[camera].visibility
            )
    detector.reset_temporal_state()
    for result, values, scores in retained:
        np.testing.assert_array_equal(result.xyz, values)
        np.testing.assert_array_equal(result.visibility, scores)


@pytest.mark.parametrize("dataset_name", DATASETS)
def test_paired_recorded_hand_coordinates(dataset_name):
    videos, source_seconds, timestamps, candidate_directory = reference_inputs(
        dataset_name
    )
    frame_limit = int(os.environ.get("W4_REFERENCE_FRAME_LIMIT", "0"))
    if frame_limit:
        timestamps = timestamps[:frame_limit]
        source_seconds = source_seconds[:frame_limit]
    camera_ids = tuple(videos)
    sides = ("right", "left")
    profile = tracker_profile("rtmw_mediapipe_hands")
    hand_indices = tuple(
        np.asarray(
            [profile.keypoint_names.index(name) for name in mediapipe_hand_names(side)]
        )
        for side in sides
    )
    point_count = len(hand_indices[0])
    # frame, camera, side, method, keypoint, component; no per-keypoint objects.
    values = np.full(
        (len(timestamps), len(videos), len(sides), 2, point_count, 3), np.nan
    )
    scores = np.zeros(values.shape[:-1])
    corners = np.full((len(timestamps), len(videos), len(sides), 4), np.nan)
    hashes_before = {
        camera: file_hash(video.file_path) for camera, video in videos.items()
    }
    positive_crops = {side: {} for side in sides}
    retained = []
    fps = next(iter(videos.values())).fps
    with ExitStack() as cleanup:
        baseline = build_tracker(
            combined_tracker_config(video_fps=fps),
            batch_size=len(videos),
            onnx_overrides=CPU_OPTIONS,
        )
        cleanup.callback(baseline.close)
        candidate = build_tracker(
            experimental_tracker_config(
                model_directory=candidate_directory, video_fps=fps
            ),
            batch_size=len(videos),
            onnx_overrides=CPU_OPTIONS,
        )
        cleanup.callback(candidate.close)
        for tracker in (baseline, candidate):
            assert all(
                native.get_providers() == ["CPUExecutionProvider"]
                for native in tracker.sessions["onnx"]._sessions.values()
            )
        detectors = {
            stage.name.removesuffix("_hand"): stage.keypoint_detectors[0]
            for stage in candidate.stages[0].children
        }
        captures = open_videos(videos, cleanup)
        states = {}
        for frame_number, timestamp in enumerate(timestamps):
            images = read_images(captures)
            observations, states = baseline.process_batch(
                images, frame_number, states, timestamp_ms=int(timestamp)
            )
            for side_index, side in enumerate(sides):
                crops = {}
                for camera_index, camera in enumerate(camera_ids):
                    body = observations[camera].stages["body"]
                    assert body.keypoints.names == profile.keypoint_names
                    values[frame_number, camera_index, side_index, 0] = (
                        body.keypoints.xyz[hand_indices[side_index]]
                    )
                    scores[frame_number, camera_index, side_index, 0] = (
                        body.keypoints.visibility[hand_indices[side_index]]
                    )
                    boxes = body.children[f"{side}_hand"].bounding_boxes
                    if boxes:
                        (box,) = boxes
                        crop = box.to_crop(images[camera])
                        assert crop.size
                        crops[camera] = crop
                        corners[frame_number, camera_index, side_index] = (
                            box.x1,
                            box.y1,
                            box.x2,
                            box.y2,
                        )
                crop_hashes = {
                    camera: hashlib.sha256(crop.tobytes()).digest()
                    for camera, crop in crops.items()
                }
                results = detectors[side].detect_batch(
                    crops,
                    DetectionContext(
                        frame_number=frame_number, timestamp_ms=int(timestamp)
                    ),
                )
                assert results.keys() == crops.keys()
                for camera_index, camera in enumerate(camera_ids):
                    if camera not in results:
                        continue
                    points = results[camera]
                    assert points.names == mediapipe_hand_names(side)
                    assert np.isnan(points.xyz[points.visibility == 0]).all()
                    assert np.isfinite(points.xyz[points.visibility > 0]).all()
                    # Compare both models in source-image coordinates. The candidate
                    # consumes the exact integer crop used by the baseline stage.
                    values[frame_number, camera_index, side_index, 1] = points.xyz
                    values[frame_number, camera_index, side_index, 1, :, :2] += corners[
                        frame_number, camera_index, side_index, :2
                    ]
                    scores[frame_number, camera_index, side_index, 1] = (
                        points.visibility
                    )
                    retained.append(
                        (points, points.xyz.copy(), points.visibility.copy())
                    )
                    baseline_present = np.any(
                        scores[frame_number, camera_index, side_index, 0] > 0
                    )
                    if (
                        available(points).any()
                        and baseline_present
                        and camera not in positive_crops[side]
                    ):
                        positive_crops[side][camera] = crops[camera].copy()
                assert crop_hashes == {
                    camera: hashlib.sha256(crop.tobytes()).digest()
                    for camera, crop in crops.items()
                }
            if frame_number % 100 == 0:
                print(
                    f"{dataset_name}: paired frame {frame_number + 1}/{len(timestamps)}",
                    flush=True,
                )
        for side in sides:
            assert set(positive_crops[side]) == set(camera_ids), (
                f"No positive {side} candidate crop for every camera"
            )
            check_recorded_reacquisition(detectors[side], positive_crops[side])
        candidate.reset_temporal_state()
        baseline.reset_temporal_state()
    for result, owned_values, visibility in retained:
        np.testing.assert_array_equal(result.xyz, owned_values)
        np.testing.assert_array_equal(result.visibility, visibility)
    assert hashes_before == {
        camera: file_hash(video.file_path) for camera, video in videos.items()
    }
    valid = np.isfinite(values).all(axis=-1) & (scores > 0)
    assert valid[..., 0, :].any() and valid[..., 1, :].any()
    output_root = os.environ.get("W4_REFERENCE_OUTPUT_DIR")
    if output_root:
        output = Path(output_root)
        assert output.is_dir(), "Caller must create and verify artifact ignore rules"
        np.savez_compressed(
            output / f"{dataset_name}-paired.npz",
            values=values,
            visibility=scores,
            crop_corners=corners,
            source_seconds=source_seconds,
            camera_ids=np.asarray(camera_ids),
            hand_sides=np.asarray(sides),
            methods=np.asarray(("mediapipe_video_cpu", "experimental_onnx_cpu")),
        )
        for side, examples in positive_crops.items():
            for camera, image in examples.items():
                assert cv2.imwrite(
                    str(output / f"{dataset_name}-{side}-{camera}.png"), image
                )
        matched = valid[..., 0, :] & valid[..., 1, :]
        disagreement = np.linalg.norm(
            values[..., 0, :, :2] - values[..., 1, :, :2], axis=-1
        )[matched]
        report = dict(
            dataset=dataset_name,
            source_frames=len(timestamps),
            camera_ids=camera_ids,
            method_names=("mediapipe_video_cpu", "experimental_onnx_cpu"),
            available_keypoints=valid.sum(axis=(0, 1, 2, 4)).tolist(),
            available_per_camera_side=valid.sum(axis=(0, 4)).tolist(),
            total_keypoints_per_method=int(valid[..., 0, :].size),
            mutually_available_keypoints=int(matched.sum()),
            median_disagreement_px=float(np.median(disagreement))
            if disagreement.size
            else None,
            p95_disagreement_px=float(np.percentile(disagreement, 95))
            if disagreement.size
            else None,
            video_sha256=hashes_before,
            interpretation="Paired identical crops; disagreement is not accuracy; no latency claim",
        )
        (output / f"{dataset_name}-paired.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
