"""Real readers and real inference scheduling, with controlled detector work."""
from collections import Counter
from contextlib import closing
from threading import Event, Lock
import unittest
from unittest.mock import Mock, patch

from skellytracker.core import TrackerConfig
from skellytracker.core.data_primitives.observation import Observation
from skellytracker.core.tracker.tracker_state import TrackerState

from freemocap.core.pipeline.dataflow.tracker_adapter import SkellyTrackerAdapter, TrackedCameraFrame
from freemocap.core.pipeline.dataflow.video_sources import VideoSourceFinished
from freemocap.core.pipeline.inference_service import InferenceService
from freemocap.core.pipeline.performance_report import PerformanceReport
from freemocap.tests import test_dataflow_video_sources as source_tests


class TrackerAdapterTests(unittest.TestCase):
    setUp = source_tests.VideoSourceTests.setUp

    def make_adapter(self, infer):
        pool = Mock()
        lease = Mock()
        lease.tracker.process_batch.side_effect = infer
        pool.create_tracker.return_value = lease
        pool_patch = patch("freemocap.core.pipeline.inference_service.SharedSessionPool", return_value=pool)
        pool_patch.start()
        self.addCleanup(pool_patch.stop)
        requests = patch("freemocap.core.pipeline.dataflow.tracker_adapter.tracker_session_requests", return_value=())
        requests.start()
        self.addCleanup(requests.stop)
        service = InferenceService(worker_registry=self.registry)
        service.start()
        self.addCleanup(service.close)
        report = PerformanceReport()
        return SkellyTrackerAdapter(inference_service=service,
                                    tracker_config=TrackerConfig(stages=[]), performance_report=report)

    @staticmethod
    def infer(*, images, frame_number, states, timestamp_ms=None):
        return ({camera: Observation(frame_number=frame_number, image_size=image.shape[:2], stages={})
                 for camera, image in images.items()}, {camera: TrackerState() for camera in images})

    def stream(self, adapter):
        return adapter.track_recording(sources=self.sources, execution_id="test-tracking",
                                       shutdown_flag=self.shutdown, queued_frames_per_camera=1)

    def test_inference_starts_early_and_loading_overlaps_with_bounded_read_ahead(self):
        from freemocap.core.pipeline.dataflow import video_sources
        original_reader = video_sources.SequentialVideoReader
        counts = Counter()
        lock = Lock()
        all_loaded_ahead = Event()

        class ObservedReader:
            def __init__(self, *, path):
                self.camera = path.name
                self.reader = original_reader(path=path)

            def read_bgr(self, *, frame_number):
                image = self.reader.read_bgr(frame_number=frame_number)
                with lock:
                    counts[self.camera] += 1
                    if len(counts) == 3 and min(counts.values()) >= 3:
                        all_loaded_ahead.set()
                return image

            def close(self):
                self.reader.close()

        calls = []

        def infer(**kwargs):
            frame = kwargs["frame_number"]
            self.assertEqual(kwargs["timestamp_ms"], round(frame * 1000 / 30))
            calls.append(frame)
            if frame == 0:
                self.assertTrue(all_loaded_ahead.wait(3), "Loading should overlap active inference")
                with lock:
                    self.assertEqual(dict(counts), {source.camera_id: 3 for source in self.sources.camera_sources})
                # At most active + one queued + one reader-local image per camera.
            if frame > 0:
                self.assertEqual(set(kwargs["states"]), set(kwargs["images"]))
            return self.infer(**kwargs)

        adapter = self.make_adapter(infer)
        with patch.object(video_sources, "SequentialVideoReader", ObservedReader):
            events = list(self.stream(adapter))
        self.assertEqual(calls, list(range(8)))
        self.assertEqual(sum(isinstance(event, TrackedCameraFrame) for event in events), 24)
        self.assertEqual(sum(isinstance(event, VideoSourceFinished) for event in events), 3)
        self.assertEqual(adapter.performance_report.images, 24)

    def test_report_counts_actual_detector_runs_separately_from_camera_images(self):
        from skellytracker.core.data_primitives.observation import StageObservation
        def infer(**kwargs):
            observations, states = self.infer(**kwargs)
            for observation in observations.values():
                observation.stages["body"] = StageObservation(name="body", detector_ran=kwargs["frame_number"] % 3 == 0)
            return observations, states
        adapter = self.make_adapter(infer)
        list(self.stream(adapter))
        self.assertEqual(adapter.performance_report.counts_snapshot(), {
            "tracking.body.camera_images": 24, "tracking.body.object_detector_runs": 9})

    def test_source_failure_keeps_healthy_camera_tracking(self):
        from freemocap.core.pipeline.dataflow import video_sources
        original_reader = video_sources.SequentialVideoReader

        class FailingReader:
            def __init__(self, *, path):
                self.path = path
                self.reader = original_reader(path=path)

            def read_bgr(self, *, frame_number):
                if self.path.name == "camera1.avi" and frame_number == 2:
                    raise IndexError("early EOF")
                return self.reader.read_bgr(frame_number=frame_number)

            def close(self):
                self.reader.close()

        adapter = self.make_adapter(self.infer)
        with patch.object(video_sources, "SequentialVideoReader", FailingReader):
            events = list(self.stream(adapter))
        counts = Counter(event.frame_key.camera for event in events if isinstance(event, TrackedCameraFrame))
        self.assertEqual(counts, {"camera0.avi": 8, "camera1.avi": 2, "camera2.avi": 8})
        self.assertFalse(self.shutdown.value)

    def test_inference_failure_does_not_cancel_graph_or_retry(self):
        infer = Mock(side_effect=ValueError("inference failed"))
        adapter = self.make_adapter(infer)
        with self.assertRaisesRegex(ValueError, "inference failed"):
            list(self.stream(adapter))
        self.assertEqual(infer.call_count, 1)
        self.assertFalse(self.shutdown.value)
        self.assertEqual(len(self.registry.alive_workers), 1)  # Shared inference service only.

    def test_closing_observation_stream_stops_readers(self):
        adapter = self.make_adapter(self.infer)
        with closing(self.stream(adapter)) as stream:
            self.assertIsInstance(next(stream), TrackedCameraFrame)
        self.assertEqual(len(self.registry.alive_workers), 1)

    def test_cancelled_graph_does_not_emit_finished_inference_results(self):
        from concurrent.futures import CancelledError

        def infer(**kwargs):
            self.shutdown.value = True
            return self.infer(**kwargs)

        adapter = self.make_adapter(infer)
        with self.assertRaises(CancelledError):
            next(self.stream(adapter))

    def test_timestamp_collision_is_rejected_before_inference(self):
        from dataclasses import replace
        from skellycam.core.timestamps.recording_timing_reader import RecordingTiming
        from freemocap.core.pipeline.dataflow.tracker_adapter import recording_timestamps_ms
        timing = RecordingTiming(timestamps_s=tuple(index * 0.0001 for index in range(8)),
                                 method=self.sources.group_timing.method)
        with self.assertRaisesRegex(ValueError, "millisecond"):
            recording_timestamps_ms(replace(self.sources, group_timing=timing))

    def test_installed_skellytracker_cpu_detector_runs_without_mocked_inference(self):
        from skellytracker.core import DetectionStageConfig
        from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoDetectorConfig
        service = InferenceService(worker_registry=self.registry)
        service.start()
        try:
            adapter = SkellyTrackerAdapter(
                inference_service=service,
                tracker_config=TrackerConfig(stages=[DetectionStageConfig(
                    name="board", keypoint_detectors=[CharucoDetectorConfig()],
                )]), performance_report=PerformanceReport(),
            )
            events = list(self.stream(adapter))
            tracked = [event for event in events if isinstance(event, TrackedCameraFrame)]
            self.assertEqual(len(tracked), 24)
            self.assertTrue(all("board" in event.observation.stages for event in tracked))
            self.assertEqual(adapter.performance_report.snapshot()["inference.process_batch.images=3"]["count"], 8)
        finally:
            service.close()


if __name__ == "__main__":
    unittest.main()
