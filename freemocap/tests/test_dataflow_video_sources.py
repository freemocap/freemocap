"""Real video decoding plus deterministic overlap/failure tests for source workers."""
import multiprocessing
from dataclasses import replace
from pathlib import Path
import tempfile
from threading import Barrier
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry

from freemocap.core.pipeline.dataflow.video_sources import (
    ConcurrentVideoSources, LoadedVideoFrame, RecordingVideoSources, VideoSourceFinished,
)
from freemocap.core.pipeline.dataflow.camera_join import ProducerOutcome


class VideoSourceTests(unittest.TestCase):
    def setUp(self):
        # External temporary directory; test videos are never repository artifacts.
        self.temp = tempfile.TemporaryDirectory(prefix="dataflow-video-test-")
        self.addCleanup(self.temp.cleanup)
        self.recording = Path(self.temp.name)
        folder = self.recording / "synchronized_videos"
        folder.mkdir()
        for camera in range(3):
            writer = cv2.VideoWriter(str(folder / f"camera{camera}.avi"),
                                     cv2.VideoWriter_fourcc(*"MJPG"), 30.0, (32, 24))
            if not writer.isOpened():
                self.fail("MJPG test video writer unavailable")
            try:
                for frame in range(8):
                    writer.write(np.full((24, 32, 3), 20 * camera + frame, dtype=np.uint8))
            finally:
                writer.release()
        self.sources = RecordingVideoSources.resolve(self.recording)
        self.shutdown = multiprocessing.Value("b", False)
        self.registry = WorkerRegistry(global_kill_flag=self.shutdown, worker_mode=WorkerMode.THREAD)

    def reader(self):
        return ConcurrentVideoSources(sources=self.sources, execution_id="test", registry=self.registry,
                                      shutdown_flag=self.shutdown, queued_frames_per_camera=2)

    def test_mismatched_video_counts_are_rejected_before_execution(self):
        path = self.recording / "synchronized_videos" / "camera2.avi"
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 30.0, (32, 24))
        self.assertTrue(writer.isOpened())
        try:
            writer.write(np.zeros((24, 32, 3), dtype=np.uint8))
        finally:
            writer.release()
        with self.assertRaises(ValueError):
            RecordingVideoSources.resolve(self.recording)

    def test_partial_ranges_cannot_silently_load_the_wrong_frames(self):
        source = self.sources.camera_sources[0]
        partial = replace(source, video_metadata=source.video_metadata.model_copy(update={"start_frame": 1}))
        with self.assertRaisesRegex(ValueError, "full-video"):
            replace(self.sources, camera_sources=(partial, *self.sources.camera_sources[1:]))

    def test_real_videos_preserve_coverage_timing_and_pixels(self):
        frames = {source.camera_id: [] for source in self.sources.camera_sources}
        outcomes = []
        with self.reader() as reader:
            for event in reader.events():
                if isinstance(event, LoadedVideoFrame):
                    camera = event.frame_key.camera
                    frames[camera].append(event.frame_key.frame)
                    self.assertAlmostEqual(event.timestamp_s, event.frame_key.frame / 30)
                    expected = 20 * int(camera[6]) + event.frame_key.frame
                    self.assertLessEqual(abs(float(event.image_bgr.mean()) - expected), 2)
                    self.assertFalse(event.image_bgr.flags.writeable)
                else:
                    outcomes.append(event)
        self.assertTrue(all(values == list(range(8)) for values in frames.values()))
        self.assertEqual(len(outcomes), 3)
        self.assertTrue(all(item.outcome == ProducerOutcome.SUCCEEDED and item.loaded_frames == 8 for item in outcomes))
        self.assertFalse(self.registry.alive_workers)

    def test_camera_reads_overlap_and_one_failure_does_not_cancel_others(self):
        from freemocap.core.pipeline.dataflow import video_sources
        original = video_sources.SequentialVideoReader
        overlap = Barrier(3, timeout=5)

        class InstrumentedReader:
            def __init__(self, *, path):
                self.path = path
                self.reader = original(path=path)

            def read_bgr(self, *, frame_number):
                if frame_number == 0:
                    overlap.wait()  # Serial dispatch cannot pass this barrier.
                if self.path.name == "camera1.avi" and frame_number == 3:
                    raise IndexError("Injected early EOF")
                return self.reader.read_bgr(frame_number=frame_number)

            def close(self):
                self.reader.close()

        outcomes = {}
        with patch.object(video_sources, "SequentialVideoReader", InstrumentedReader):
            with self.reader() as reader:
                for event in reader.events():
                    if isinstance(event, VideoSourceFinished):
                        outcomes[event.camera_id] = event
        self.assertEqual(outcomes["camera1.avi"].outcome, ProducerOutcome.FAILED)
        self.assertEqual(outcomes["camera1.avi"].loaded_frames, 3)
        self.assertIn("early EOF", outcomes["camera1.avi"].error_message)
        for camera in ("camera0.avi", "camera2.avi"):
            self.assertEqual(outcomes[camera].outcome, ProducerOutcome.SUCCEEDED)
            self.assertEqual(outcomes[camera].loaded_frames, 8)

    def test_early_consumer_exit_stops_readers_with_bounded_queue(self):
        with self.reader() as reader:
            next(reader.events())
        self.assertFalse(self.registry.alive_workers)
        self.assertEqual(self.registry.workers, [])

    def test_failed_thread_start_is_reaped_from_registry(self):
        from skellycam.core.ipc.process_management.managed_worker import ManagedThread
        original = ManagedThread.start
        calls = 0

        def start_or_fail(worker):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("Injected thread startup failure")
            original(worker)

        with patch.object(ManagedThread, "start", start_or_fail):
            with self.assertRaisesRegex(RuntimeError, "startup failure"):
                with self.reader():
                    self.fail("Startup should fail")
        self.assertEqual(self.registry.workers, [])

    def test_repeated_execution_does_not_retain_registered_readers(self):
        for _ in range(2):
            with self.reader() as reader:
                for event in reader.events():
                    pass
            self.assertEqual(self.registry.workers, [])

    def test_shared_registry_is_rejected_without_reaping_unrelated_worker(self):
        worker = self.registry.create_worker(shutdown_flag=self.shutdown, worker_mode=WorkerMode.THREAD,
                                             target=lambda: None, name="unrelated-unstarted")
        try:
            with self.assertRaisesRegex(ValueError, "dedicated"):
                with self.reader():
                    pass
            self.assertIn(worker, self.registry.workers)
        finally:
            self.registry.remove_dead()

    def test_read_failure_and_cleanup_failure_are_both_preserved(self):
        from freemocap.core.pipeline.dataflow import video_sources

        class BrokenReader:
            def __init__(self, *, path):
                pass

            def read_bgr(self, *, frame_number):
                raise ValueError("corrupt pixels")

            def close(self):
                raise RuntimeError("cleanup failed")

        with patch.object(video_sources, "SequentialVideoReader", BrokenReader):
            with self.reader() as reader:
                outcomes = list(reader.events())
        self.assertEqual(len(outcomes), 3)
        for outcome in outcomes:
            self.assertIn("corrupt pixels", outcome.error_message)
            self.assertIn("cleanup failed", outcome.error_message)


if __name__ == "__main__":
    unittest.main()
