"""Real process/codec checks at the recording annotation boundary."""
from concurrent.futures import CancelledError
from dataclasses import replace
import multiprocessing
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import cv2
import numpy as np
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellytracker.core.data_primitives.observation import Observation, StageObservation
from skellytracker.core.data_primitives.keypoints import Keypoints

from freemocap.core.pipeline.dataflow.annotation_workers import (
    CameraAnnotationJob, RecordingAnnotationWorkers, write_camera_annotation,
)
from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig


class AnnotationWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        video = root / "source.mp4"
        writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 30., (160, 120))
        self.assertTrue(writer.isOpened())
        for i in range(8):
            writer.write(np.full((120, 160, 3), 40 + i, dtype=np.uint8))
        writer.release()
        observations = tuple(Observation(frame_number=i, image_size=(120, 160), stages={
            "body": StageObservation(name="body", keypoints=Keypoints(names=("nose", "left_eye"),
                xyz=np.array([[70., 60., 0.], [80., 65., 0.]]), visibility=np.ones(2)))}) for i in range(8))
        self.job = CameraAnnotationJob(recording_path=root, execution_id="first", camera_id="camera",
            video=VideoMetadata(file_path=video, width=160, height=120, fps=30., frame_count=8,
                fourcc="mp4v", duration_seconds=8 / 30, end_frame=8),
            tracker_config=PosthocMocapPipelineConfig(charuco_tracking_enabled=False).tracker_config,
            observations=observations)

    def read_frames(self, path):
        reader = cv2.VideoCapture(str(path))
        frames = []
        try:
            while True:
                ok, image = reader.read()
                if not ok:
                    break
                frames.append(image)
        finally:
            reader.release()
        self.assertEqual(len(frames), 8)
        return np.stack(frames)

    def test_process_parity_failed_job_recovery_and_cleanup(self):
        expected = self.read_frames(write_camera_annotation(self.job, cancelled=lambda: False))
        with RecordingAnnotationWorkers(count=1) as service:
            broken = replace(self.job, video=self.job.video.model_copy(update={"file_path": self.job.recording_path / "missing.mp4"}))
            with self.assertRaisesRegex(RuntimeError, "Cannot open"):
                service.run_job(broken, cancelled=lambda: False)
            actual = self.read_frames(service.run_job(self.job, cancelled=lambda: False))
            np.testing.assert_array_equal(actual, expected)
            self.assertEqual(len(service.workers), 1)
            with self.assertRaisesRegex(ValueError, "different recording execution"):
                service.run_job(replace(self.job, execution_id="second"), cancelled=lambda: False)
        self.assertTrue(all(not worker.is_alive() for worker in service.workers))
        self.assertFalse(list(self.job.recording_path.rglob("*.partial.mp4")))

    def test_dead_worker_does_not_cancel_other_worker_or_owner(self):
        global_flag = multiprocessing.Value("b", False)
        registry = WorkerRegistry(global_kill_flag=global_flag, worker_mode=WorkerMode.PROCESS)
        with RecordingAnnotationWorkers(count=2, registry=registry) as service:
            service.workers[0].kill()
            service.workers[0].join(timeout=5.0)
            with self.assertRaises((RuntimeError, OSError)):
                service.run_job(self.job, cancelled=lambda: False)
            self.read_frames(service.run_job(self.job, cancelled=lambda: False))
            self.assertFalse(global_flag.value)
        self.assertFalse(global_flag.value)
        self.assertTrue(all(not worker.is_alive() for worker in service.workers))

    def test_cancel_before_dispatch_does_not_publish(self):
        with RecordingAnnotationWorkers(count=1) as service:
            with self.assertRaises(CancelledError):
                service.run_job(self.job, cancelled=lambda: True)
        self.assertFalse((self.job.recording_path / "annotated_videos").exists())

    def test_cancel_after_first_frame_removes_incomplete_output(self):
        from freemocap.core.pipeline.performance_report import PerformanceReport
        performance = PerformanceReport()
        def cancelled():
            return bool(performance.snapshot())
        with self.assertRaises(CancelledError):
            write_camera_annotation(self.job, cancelled=cancelled, performance=performance)
        self.assertEqual(performance.snapshot()["camera.camera.encode_write"]["count"], 1)
        self.assertFalse(list((self.job.recording_path / "annotated_videos").glob("*.mp4")))


if __name__ == "__main__":
    unittest.main()
