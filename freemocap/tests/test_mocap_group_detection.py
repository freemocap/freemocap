import multiprocessing
import time
from threading import Event
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.tracking.board_selection import CharucoBoardMode
from concurrent.futures import CancelledError
from queue import Queue
from freemocap.core.pipeline.inference_service import InferenceService
from skellytracker.core.sessions.shared_sessions import TrackerLease
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

import cv2
import numpy as np
from numpy.typing import NDArray
from skellycam.core.recorders.videos.pyav_video_writer import PyavVideoWriter
from skellycam.core.recorders.videos.sequential_video_reader import SequentialVideoReader
from skellytracker.core import Tracker, TrackerConfig
from skellytracker.core.data_primitives.keypoints import Keypoints
from skellytracker.core.data_primitives.observation import Observation, StageObservation
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition
from skellytracker.core.tracker.tracker_state import TrackerState

from freemocap.core.pipeline.posthoc.mocap_detection import MocapDetectionRequest, detect_mocap_recording
from freemocap.core.tracking.observation_buffer import ObservationBuffer


def body_batch(
    *, images: dict[str, NDArray[np.uint8]], frame_number: int, states: dict[str, TrackerState],
) -> tuple[dict[str, Observation], dict[str, TrackerState]]:
    return {
        camera: Observation(frame_number=frame_number, image_size=image.shape[:2], stages={
            "body": StageObservation(name="body", keypoints=Keypoints(
                names=("test_point",), xyz=np.array([[10., 20., 0.]]), visibility=np.ones(1),
            )),
        }) for camera, image in images.items()
    }, states


class MocapGroupDetectionTests(unittest.TestCase):
    def test_next_frame_decodes_while_inference_is_running(self) -> None:
        self.write_recording(camera_count=1, board_at=None, frame_count=3)
        next_decoded = Event()
        original_read = SequentialVideoReader.read_bgr

        def read(reader: SequentialVideoReader, *, frame_number: int) -> NDArray[np.uint8]:
            image = original_read(reader, frame_number=frame_number)
            if frame_number == 1:
                next_decoded.set()
            return image

        def infer(*, images: dict[str, NDArray[np.uint8]], frame_number: int,
                  states: dict[str, TrackerState]) -> tuple[dict[str, Observation], dict[str, TrackerState]]:
            if frame_number == 0:
                self.assertTrue(next_decoded.wait(timeout=2.0), "Decode was blocked behind inference")
            return body_batch(images=images, frame_number=frame_number, states=states)

        self.body.process_batch.side_effect = infer
        with patch("freemocap.core.pipeline.posthoc.mocap_video_node.SequentialVideoReader.read_bgr", new=read):
            frames = list(detect_mocap_recording(self.request))
        self.assertEqual([frame.frame_number for frame in frames], [0, 1, 2])
        self.assertFalse(any(node.worker.is_alive() for node in self.request.video_nodes))

    def test_video_failure_stops_sibling_threads_and_preserves_service(self) -> None:
        self.write_recording(camera_count=3, board_at=None)
        with patch("freemocap.core.pipeline.posthoc.mocap_video_node.SequentialVideoReader.read_bgr",
                   side_effect=RuntimeError("video decoder failed")):
            with self.assertRaisesRegex(RuntimeError, "video decoder failed"):
                list(detect_mocap_recording(self.request))
        self.assertTrue(self.ipc.pipeline_shutdown_flag.value)
        self.assertFalse(self.ipc.global_kill_flag.value)
        self.assertTrue(self.service.worker.is_alive())
        self.assertFalse(any(node.worker.is_alive() for node in self.request.video_nodes))

    def setup_service(self) -> None:
        self.registry = WorkerRegistry(global_kill_flag=self.ipc.global_kill_flag, worker_mode=WorkerMode.THREAD)
        self.pool = Mock()
        lease = Mock(spec=TrackerLease)
        lease.tracker = self.body
        self.pool.create_tracker.return_value = lease
        pool_patch = patch("freemocap.core.pipeline.inference_service.SharedSessionPool", return_value=self.pool)
        pool_patch.start()
        self.addCleanup(pool_patch.stop)
        self.service = InferenceService(worker_registry=self.registry)
        self.service.start()
        self.addCleanup(self.service.close)

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.body = Mock(spec=Tracker)
        self.body.process_batch.side_effect = body_batch
        self.logs = multiprocessing.Queue()
        self.addCleanup(self.logs.close)
        self.ipc = PipelineIPC(pipeline_id="group-test", ws_queue=self.logs,
            global_kill_flag=multiprocessing.Value("b", False),
            heartbeat_timestamp=multiprocessing.Value("d", time.perf_counter()))
        self.config = PosthocMocapPipelineConfig(charucoBoard={"squares_x": 5, "squares_y": 3, "square_length_mm": 37.5})
        self.setup_service()
        self.request = MocapDetectionRequest(recording_path=self.folder, config=self.config,
            ipc=self.ipc, progress=Queue(), registry=self.registry, inference_service=self.service, video_nodes=[])

    def write_recording(self, *, camera_count: int, board_at: int | None, frame_count: int = 8) -> None:
        video_folder = self.folder / "synchronized_videos"
        video_folder.mkdir()
        filenames = {f"camera-{index}": f"arbitrary clip {index}.mp4" for index in range(camera_count)}
        board = CharucoBoardDefinition.create_test_data_7x5()
        board_image = cv2.cvtColor(board.cv2_board.generateImage((840, 600), marginSize=30), cv2.COLOR_GRAY2BGR)
        for index, filename in enumerate(filenames.values()):
            writer = PyavVideoWriter(path=str(video_folder / filename), fps=30.0, width=840, height=600)
            try:
                for frame in range(frame_count):
                    visible = index == camera_count - 1 and board_at is not None and frame >= board_at
                    writer.write(board_image if visible else np.full_like(board_image, 255))
            finally:
                writer.release()
        (self.folder / f"{self.folder.name}_recording_info.json").write_text(json.dumps({"videos": filenames}))

    def test_late_board_locks_across_group_without_skipping_body_frames(self) -> None:
        self.write_recording(camera_count=3, board_at=3)
        frames = list(detect_mocap_recording(self.request))
        self.assertEqual([call.kwargs["frame_number"] for call in self.body.process_batch.call_args_list], list(range(8)))
        self.assertTrue(all(frame.selected_board is None for frame in frames[:5]))
        selected = frames[5].selected_board
        self.assertIsNotNone(selected)
        self.assertEqual((selected.squares_x, selected.squares_y, selected.square_length_mm), (7, 5, 37.5))
        for frame in frames[5:]:
            self.assertIs(frame.selected_board, selected)
            self.assertEqual(set(frame.observations), {"camera-0", "camera-1", "camera-2"})
            for observation in frame.observations.values():
                self.assertEqual(set(observation.stages), {"body", "charuco"})
        buffer = ObservationBuffer()
        for frame in frames:
            buffer.add_observation(frame.observations["camera-2"])
        values = buffer.to_keypoints_array(names=buffer.keypoint_names)
        self.assertTrue(np.isnan(values[:5, 1:]).all())
        self.assertTrue(np.isfinite(values[5:, 1:, :2]).any())
        self.assertFalse(any(worker.is_alive() for worker in self.registry._workers if worker.name.startswith("MocapVideo-")))

    def test_no_board_is_a_complete_body_recording(self) -> None:
        self.write_recording(camera_count=1, board_at=None)
        frames = list(detect_mocap_recording(self.request))
        self.assertEqual(len(frames), 8)
        self.assertTrue(all(frame.selected_board is None for frame in frames))
        self.assertFalse(any(worker.is_alive() for worker in self.registry._workers if worker.name.startswith("MocapVideo-")))

    def test_closing_iteration_releases_resources(self) -> None:
        self.write_recording(camera_count=2, board_at=None)
        frames = detect_mocap_recording(self.request)
        next(frames)
        frames.close()
        self.assertFalse(any(worker.is_alive() for worker in self.registry._workers if worker.name.startswith("MocapVideo-")))

    def test_detection_failure_propagates_and_releases_resources(self) -> None:
        self.write_recording(camera_count=2, board_at=None)
        self.body.process_batch.side_effect = RuntimeError("detector failure")
        with self.assertRaisesRegex(RuntimeError, "detector failure"):
            list(detect_mocap_recording(self.request))
        self.assertFalse(any(worker.is_alive() for worker in self.registry._workers if worker.name.startswith("MocapVideo-")))

    def test_cancellation_between_frames_releases_resources(self) -> None:
        self.write_recording(camera_count=2, board_at=None)
        continuing = Mock(return_value=True)
        frames = detect_mocap_recording(self.request)
        next(frames)
        self.ipc.shutdown_pipeline()
        with self.assertRaises(CancelledError):
            list(frames)
        self.body.process_batch.assert_called_once()
        self.assertFalse(any(worker.is_alive() for worker in self.registry._workers if worker.name.startswith("MocapVideo-")))

    def test_disabled_board_tracking_does_not_construct_selector_or_detector(self) -> None:
        self.write_recording(camera_count=1, board_at=0)
        with patch("freemocap.core.pipeline.posthoc.mocap_detection.CharucoBoardSelector") as selector, \
                patch("freemocap.core.pipeline.posthoc.mocap_video_node.build_charuco_tracker") as board_tracker:
            frames = list(detect_mocap_recording(replace(self.request, config=self.config.model_copy(update={"charuco_tracking_enabled": False}))))
        selector.assert_not_called()
        board_tracker.assert_not_called()
        self.assertEqual(len(frames), 8)

    def test_explicit_board_skips_auto_selection_and_preserves_user_geometry(self) -> None:
        self.write_recording(camera_count=1, board_at=None)
        with patch("freemocap.core.pipeline.posthoc.mocap_detection.CharucoBoardSelector") as selector:
            frames = list(detect_mocap_recording(replace(self.request, config=self.config.model_copy(update={"board_mode": CharucoBoardMode.EXPLICIT}))))
        selector.assert_not_called()
        self.assertTrue(all(frame.selected_board is self.config.charuco_board for frame in frames))
