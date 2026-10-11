"""Real geometry/solver/store tests, including late failure after eager computation."""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import numpy as np
from skellycam.core.timestamps.recording_timing_reader import RecordingTiming, TimingMethod
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellytracker.core.data_primitives.observation import Observation, StageObservation
from skellytracker.core.data_primitives.keypoints import Keypoints

from freemocap.core.pipeline.dataflow.camera_join import CameraFrameKey, ProducerOutcome
from freemocap.core.pipeline.dataflow.video_sources import CameraVideoSource, RecordingVideoSources, VideoSourceFinished
from freemocap.core.pipeline.dataflow.tracker_adapter import TrackedCameraFrame
from freemocap.core.pipeline.dataflow.scientific_recording import FrameTriangulation, process_scientific_recording, process_resolved_scientific_recording, observation_buffers
from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata
from freemocap.core.tasks.calibration.shared.camera_model import CameraModel
from freemocap.core.tasks.calibration.shared.camera_intrinsics import CameraIntrinsics
from freemocap.core.tasks.calibration.shared.camera_extrinsics import CameraExtrinsics
from freemocap.core.tasks.calibration.camera_matching.matching_models import CameraMatchingConfig, CameraMatchingStatus, CameraMatchingResult, MatchingFailurePolicy
from freemocap.core.tasks.triangulation.triangulator import Triangulator
from freemocap.core.tasks.triangulation.helpers.triangulation_config import TriangulationConfig
from freemocap.core.reconstruction.posthoc_reconstruction import triangulate_observation_buffers
from freemocap.core.reconstruction.posthoc_timing import PosthocTimingReport
from freemocap.core.recording.result_processing.observation_inputs import TrackerRecordingDefinition
from freemocap.core.recording.result_processing.saved_reconstruction import read_saved_channel
from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
from freemocap.core.types.channel_kind import ChannelKind
from freemocap.system.recording_structure.recording_structure import RecordingStructure


class ScientificRecordingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.cameras = tuple(CameraModel(id=f"camera{i}", index=i, image_size=(1280, 720),
            intrinsics=CameraIntrinsics(fx=900., fy=920., cx=640., cy=360., k1=-0.05),
            extrinsics=CameraExtrinsics(quaternion_wxyz=[1., 0., 0., 0.], translation=translation))
            for i, translation in enumerate(([0., 0., 0.], [-700., 100., 0.], [200., -600., 100.])))
        timeline = RecordingTiming(tuple(frame / 30 for frame in range(12)), TimingMethod.INFERRED_FROM_FPS)
        self.sources = RecordingVideoSources(self.root, "cameras", tuple(CameraVideoSource(camera.id,
            VideoMetadata(file_path=self.root / f"{camera.id}.mp4", width=1280, height=720, fps=30.,
                          frame_count=12, fourcc="mp4v", duration_seconds=0.4, end_frame=12), timeline)
            for camera in self.cameras), timeline)
        world = np.random.default_rng(17).uniform([-500., -300., 2500.], [500., 300., 3500.], (12, 10, 3))
        pixels = Triangulator(cameras=list(self.cameras)).project(world.reshape(-1, 3)).reshape(3, 12, 10, 2)
        pixels[1, 3, 2] += 80  # Exercise existing outlier-rejection semantics.
        pixels[2, 5, 1] = np.nan  # A valid missing detection is not a failed camera.
        self.frames = []
        self.events = []
        for frame in range(12):
            observations = {}
            for index, camera in enumerate(self.cameras):
                xy = pixels[index, frame]
                observation = Observation(frame_number=frame, image_size=(720, 1280), stages={"body": StageObservation(
                    name="body", keypoints=Keypoints(names=tuple(f"point{i}" for i in range(10)),
                        xyz=np.column_stack((xy, np.zeros(10))), visibility=np.isfinite(xy).all(axis=1).astype(float)))})
                observations[camera.id] = observation
                self.events.append(TrackedCameraFrame(CameraFrameKey("run", "cameras", camera.id, frame), frame / 30, observation))
            self.frames.append(observations)
        self.outcomes = [VideoSourceFinished("run", "cameras", camera.id, ProducerOutcome.SUCCEEDED, 12, None) for camera in self.cameras]
        self.names = self.events[0].observation.to_keypoints().names

    def operation(self, config=None):
        return FrameTriangulation(sources=self.sources, execution_id="run", camera_geometry={c.id: c for c in self.cameras},
                                  point_names=self.names, triangulation_config=config or TriangulationConfig())

    def test_frame_ready_before_source_completion_and_batch_parity(self):
        for reject in (False, True):
            config = TriangulationConfig(use_outlier_rejection=reject)
            operation = self.operation(config)
            self.assertIsNone(operation.accept(self.events[1]))
            self.assertIsNone(operation.accept(self.events[0]))
            self.assertIsNotNone(operation.accept(self.events[2]))
            self.assertFalse(operation.observations.join.complete)
            for event in self.events[3:] + self.outcomes:
                operation.accept(event)
            actual = operation.completed_result()
            expected = triangulate_observation_buffers(observation_buffers=observation_buffers(self.frames, tuple(c.id for c in self.cameras)),
                camera_geometry={c.id: c for c in self.cameras}, triangulation_config=config,
                max_reprojection_error_px=None, timing=PosthocTimingReport())
            for field in ("points_3d", "per_camera_weights", "reprojection_error"):
                np.testing.assert_allclose(getattr(actual.reconstruction, field), getattr(expected.reconstruction, field), atol=1e-8, rtol=1e-10)
            for field in ("errors", "observed", "reconstructed", "weights"):
                np.testing.assert_allclose(getattr(actual.reconstruction.diagnostics, field), getattr(expected.reconstruction.diagnostics, field), atol=1e-8, rtol=1e-10)

    def test_late_camera_failure_invalidates_scientific_completion(self):
        operation = self.operation()
        for event in self.events + self.outcomes[:2]:
            operation.accept(event)
        self.assertEqual(len(operation.results), 12)
        operation.accept(replace(self.outcomes[2], outcome=ProducerOutcome.FAILED, error_message="late read failure"))
        with self.assertRaisesRegex(ValueError, "every declared camera"):
            operation.completed_result()

    def test_complete_recording_batches_once_and_preserves_streaming_results(self):
        from freemocap.core.pipeline.dataflow import scientific_recording
        for reject in (False, True):
            config = TriangulationConfig(use_outlier_rejection=reject)
            streamed = self.operation(config)
            for event in self.events + self.outcomes:
                streamed.accept(event)
            expected = streamed.completed_result()
            with patch.object(scientific_recording, "triangulate_observation_buffers",
                              wraps=triangulate_observation_buffers) as solver:
                actual = process_scientific_recording(events=self.events + self.outcomes,
                    sources=self.sources, execution_id="run", calibration_cameras=self.cameras,
                    matching_config=CameraMatchingConfig(), triangulation_config=config)
                self.assertEqual(solver.call_count, 1)
            self.assertEqual(actual.triangulation.sources, expected.sources)
            self.assertEqual(actual.triangulation.diagnostic_point_names, expected.diagnostic_point_names)
            for name in ("points_3d", "per_camera_weights", "reprojection_error"):
                left, right = getattr(actual.triangulation.reconstruction, name), getattr(expected.reconstruction, name)
                np.testing.assert_array_equal(np.isnan(left), np.isnan(right))
                np.testing.assert_allclose(left, right, atol=1e-8, rtol=1e-10)
            for name in ("errors", "observed", "reconstructed", "weights"):
                np.testing.assert_allclose(getattr(actual.triangulation.reconstruction.diagnostics, name),
                    getattr(expected.reconstruction.diagnostics, name), atol=1e-8, rtol=1e-10)
            self.assertIn("camera_assignment", {stage.name for stage in actual.execution_timing.stages})
            self.assertIn("scientific_payload_snapshot", {stage.name for stage in actual.execution_timing.stages})

    def test_batch_metric_triangulation_rejects_single_camera(self):
        sources = replace(self.sources, camera_sources=self.sources.camera_sources[:1])
        events = [event for event in self.events if event.frame_key.camera == self.cameras[0].id]
        with self.assertRaisesRegex(ValueError, "at least two"):
            process_scientific_recording(events=events + self.outcomes[:1], sources=sources,
                execution_id="run", calibration_cameras=self.cameras[:1],
                matching_config=CameraMatchingConfig(), triangulation_config=TriangulationConfig())

    def test_batch_metric_triangulation_rejects_duplicate_geometry(self):
        with patch("freemocap.core.pipeline.dataflow.scientific_recording.PosthocMatchingRequest.resolve",
                   return_value={camera.id: self.cameras[0] for camera in self.cameras}):
            with self.assertRaisesRegex(ValueError, "unique resolved geometry"):
                process_scientific_recording(events=self.events + self.outcomes, sources=self.sources,
                    execution_id="run", calibration_cameras=self.cameras,
                    matching_config=CameraMatchingConfig(), triangulation_config=TriangulationConfig())

    def test_corrupt_identity_and_duplicate_delivery_rejected(self):
        for event in (replace(self.events[0], timestamp_s=1.),
                      replace(self.events[0], frame_key=CameraFrameKey("foreign", "cameras", "camera0", 0))):
            with self.assertRaises(ValueError):
                self.operation().accept(event)
        operation = self.operation()
        operation.accept(self.events[0])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            operation.accept(self.events[0])

    def test_real_matching_and_canonical_save_round_trip(self):
        completed = process_scientific_recording(events=iter(self.events + self.outcomes), sources=self.sources,
            execution_id="run", calibration_cameras=self.cameras, matching_config=CameraMatchingConfig(),
            triangulation_config=TriangulationConfig())
        self.assertIn(completed.matching_result.status, (CameraMatchingStatus.INITIAL_ACCEPTED, CameraMatchingStatus.MATCHED))
        metadata = completed.save(recording_info=RecordingInfo(recording_name="result", recording_directory=str(self.root)),
            tracker_definition=TrackerRecordingDefinition(name="keypoint_model:synthetic", point_names=self.names, configuration={}))
        raw = next(channel for channel in metadata.runs[0].channels if channel.kind == ChannelKind.RAW_KEYPOINTS_3D)
        saved = read_saved_channel(structure=RecordingStructure(base_directory=self.root, recording_name="result"),
                                  run_id=0, metadata=metadata, channel=raw)
        np.testing.assert_array_equal(saved.values, completed.triangulation.reconstruction.points_3d)
        self.assertFalse(any(channel.kind == ChannelKind.KEYPOINTS_3D for channel in metadata.runs[0].channels))

    def test_failed_camera_still_drains_healthy_sources(self):
        consumed = []
        def events():
            yield replace(self.outcomes[0], outcome=ProducerOutcome.FAILED, loaded_frames=0)
            for event in self.events:
                if event.frame_key.camera != "camera0":
                    consumed.append(event)
                    yield event
            yield from self.outcomes[1:]
        with self.assertRaisesRegex(ValueError, "every declared camera"):
            process_scientific_recording(events=events(), sources=self.sources, execution_id="run",
                calibration_cameras=self.cameras, matching_config=CameraMatchingConfig(), triangulation_config=TriangulationConfig())
        self.assertEqual(len(consumed), 24)

    def test_resolved_assignment_triangulates_before_iterator_completion(self):
        from freemocap.core.pipeline.dataflow import scientific_recording
        original = scientific_recording.triangulate_observation_buffers
        with patch.object(scientific_recording, "triangulate_observation_buffers", wraps=original) as solver:
            def events():
                yield from self.events[:3]
                self.assertEqual(solver.call_count, 1)
                yield from self.events[3:] + self.outcomes
            result = process_resolved_scientific_recording(events=events(), sources=self.sources,
                execution_id="run", calibration_cameras=self.cameras,
                matching_result=CameraMatchingResult(CameraMatchingStatus.INITIAL_ACCEPTED, (0, 1, 2), None, None),
                matching_config=CameraMatchingConfig(), point_names=self.names, triangulation_config=TriangulationConfig())
            self.assertEqual(result.triangulation.reconstruction.points_3d.shape, (12, 10, 3))

    def test_poor_fitness_respects_existing_continue_policy_when_saving(self):
        result = process_resolved_scientific_recording(events=self.events + self.outcomes, sources=self.sources,
            execution_id="run", calibration_cameras=self.cameras,
            matching_result=CameraMatchingResult(CameraMatchingStatus.POOR, (0, 1, 2), None, None),
            matching_config=CameraMatchingConfig(), point_names=self.names, triangulation_config=TriangulationConfig())
        metadata = result.save(recording_info=RecordingInfo(recording_name="continued", recording_directory=str(self.root)),
            tracker_definition=TrackerRecordingDefinition(name="keypoint_model:synthetic", point_names=self.names, configuration={}))
        self.assertTrue(any(channel.kind == ChannelKind.RAW_KEYPOINTS_3D for channel in metadata.runs[0].channels))
        assignment = metadata.runs[0].sources["keypoint_model:synthetic"].definition["camera_assignment"]
        self.assertEqual(assignment["status"], "poor")
        self.assertEqual(assignment["source_to_calibration"], {camera.id: camera.id for camera in self.cameras})
        stored = read_metadata(path=RecordingStructure(base_directory=self.root, recording_name="continued").data_parquet_path)
        self.assertEqual(stored.runs[0].sources["keypoint_model:synthetic"].definition["camera_assignment"], assignment)
        strict = replace(result, matching_config=CameraMatchingConfig(failure_policy=MatchingFailurePolicy.STOP))
        with self.assertRaisesRegex(ValueError, "failure policy"):
            strict.save(recording_info=RecordingInfo(recording_name="strict", recording_directory=str(self.root)),
                tracker_definition=TrackerRecordingDefinition(name="keypoint_model:synthetic", point_names=self.names, configuration={}))
        self.assertFalse((self.root / "strict").exists())

    def test_continue_policy_cannot_invent_missing_assignment(self):
        with self.assertRaisesRegex(ValueError, "No camera assignment"):
            process_resolved_scientific_recording(events=self.events + self.outcomes, sources=self.sources,
                execution_id="run", calibration_cameras=self.cameras,
                matching_result=CameraMatchingResult(CameraMatchingStatus.INSUFFICIENT, None, None, None),
                matching_config=CameraMatchingConfig(), point_names=self.names, triangulation_config=TriangulationConfig())

    def test_poor_fitness_still_respects_stop_policy(self):
        with self.assertRaisesRegex(ValueError, "failure policy"):
            process_resolved_scientific_recording(events=self.events + self.outcomes, sources=self.sources,
                execution_id="run", calibration_cameras=self.cameras,
                matching_result=CameraMatchingResult(CameraMatchingStatus.POOR, (0, 1, 2), None, None),
                matching_config=CameraMatchingConfig(failure_policy=MatchingFailurePolicy.STOP),
                point_names=self.names, triangulation_config=TriangulationConfig())

    def test_mutated_scientific_payload_cannot_be_saved(self):
        result = process_resolved_scientific_recording(events=self.events + self.outcomes, sources=self.sources,
            execution_id="run", calibration_cameras=self.cameras,
            matching_result=CameraMatchingResult(CameraMatchingStatus.INITIAL_ACCEPTED, (0, 1, 2), None, None),
            matching_config=CameraMatchingConfig(), point_names=self.names, triangulation_config=TriangulationConfig())
        result.triangulation.reconstruction.points_3d[0, 0, 0] += 1
        with self.assertRaisesRegex(ValueError, "changed after computation"):
            result.save(recording_info=RecordingInfo(recording_name="mutated", recording_directory=str(self.root)),
                tracker_definition=TrackerRecordingDefinition(name="keypoint_model:synthetic", point_names=self.names, configuration={}))
        self.assertFalse((self.root / "mutated").exists())
