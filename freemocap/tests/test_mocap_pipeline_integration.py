from concurrent.futures import CancelledError
from queue import Queue
from freemocap.core.pipeline.inference_service import InferenceService
from skellytracker.core.sessions.shared_sessions import TrackerLease
import asyncio
import json
import multiprocessing
import tempfile
import time
import unittest
from pathlib import Path
from queue import Empty
from unittest.mock import Mock, patch

import av
import cv2
import numpy as np
from numpy.typing import NDArray
from skellycam.core.recorders.videos.pyav_video_writer import PyavVideoWriter
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.ipc.process_management.managed_worker import ManagedWorker, WorkerMode
from skellytracker.core import Tracker
from skellytracker.core.data_primitives.observation import Observation
from skellytracker.core.tracker.tracker_state import TrackerState
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition

from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.app.freemocap_application import FreemocapApplication
from freemocap.core.pipeline.posthoc.mocap_pipeline import MocapPipeline, MocapWorkerRequest, run_mocap_pipeline
from freemocap.core.pipeline.posthoc.pipeline_phases import AggregatorPhase
from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
from freemocap.core.recording.result_processing.saved_reconstruction import SavedPointPolicy, SavedReconstructionRequest, read_saved_reconstruction
from freemocap.core.skeletons.charuco_board_skeleton import CHARUCO_BOARD_MODEL_ID
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.system.recording_structure.recording_structure import RecordingStructure
from freemocap.tests.test_mocap_group_detection import body_batch


class MocapPipelineIntegrationTests(unittest.TestCase):
    def test_worker_exit_without_terminal_report_fails_pipeline(self) -> None:
        worker = Mock(spec=ManagedWorker)
        worker.is_alive.return_value = False
        worker.failure_exitcode = None
        worker.exitcode = 0
        pipeline = MocapPipeline(
            id=self.ipc.pipeline_id, recording_info=self.recording, ipc=self.ipc,
            worker=worker, progress_queue=self.progress, started=True,
        )
        messages = pipeline.get_progress_messages()
        self.assertEqual(messages[-1].phase, AggregatorPhase.FAILED)
        self.assertTrue(self.ipc.pipeline_shutdown_flag.value)
        self.assertFalse(self.ipc.global_kill_flag.value)

    def test_application_returns_mocap_pipeline_through_runtime_type_boundary(self) -> None:
        registry = WorkerRegistry(global_kill_flag=self.ipc.global_kill_flag, worker_mode=WorkerMode.PROCESS)
        with patch("freemocap.core.pipeline.posthoc.mocap_pipeline.PipelineIPC.create", return_value=self.ipc):
            pipeline = MocapPipeline.create(
                pipeline_id=self.ipc.pipeline_id, recording_info=self.recording,
                config=self.config, worker_registry=registry, global_kill_flag=self.ipc.global_kill_flag, inference_service=self.service,
            )
        application = FreemocapApplication.__new__(FreemocapApplication)
        application.posthoc_pipeline_manager = Mock()
        application.posthoc_pipeline_manager.create_mocap_pipeline.return_value = pipeline
        try:
            result = asyncio.run(application.create_posthoc_mocap_pipeline(
                recording_info=self.recording, mocap_config=self.config,
            ))
            self.assertIs(result, pipeline)
        finally:
            pipeline.shutdown()

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
        self.recording = RecordingInfo(recording_name="capture", recording_directory=temporary.name)
        self.folder = Path(self.recording.full_recording_path)
        self.progress = Queue()
        self.logs = multiprocessing.Queue()
        self.addCleanup(self.logs.close)
        self.ipc = PipelineIPC(pipeline_id="integration", ws_queue=self.logs,
            global_kill_flag=multiprocessing.Value('b', False),
            heartbeat_timestamp=multiprocessing.Value('d', time.perf_counter()))
        self.config = PosthocMocapPipelineConfig(charucoBoard={
            "squares_x": 5, "squares_y": 3, "square_length_mm": 37.5,
        })
        self.body = Mock(spec=Tracker)
        self.body.process_batch.side_effect = body_batch
        self.setup_service()
        self.request = MocapWorkerRequest(pipeline_id="integration", recording=self.recording,
            config=self.config, ipc=self.ipc, progress_queue=self.progress, registry=self.registry, inference_service=self.service, video_nodes=[])

    def write_video(self, *, board_visible: bool) -> None:
        folder = self.folder / "synchronized_videos"
        folder.mkdir(exist_ok=True)
        board = CharucoBoardDefinition.create_test_data_7x5()
        image = cv2.cvtColor(board.cv2_board.generateImage((840, 600), marginSize=30), cv2.COLOR_GRAY2BGR)
        writer = PyavVideoWriter(path=str(folder / "input.mp4"), fps=30.0, width=840, height=600)
        try:
            for frame in range(4):
                writer.write(image if board_visible and frame >= 1 else np.full_like(image, 255))
        finally:
            writer.release()
        (self.folder / "capture_recording_info.json").write_text(json.dumps({"videos": {"camera": "input.mp4"}}))

    def test_recording_produces_annotations_and_parquet_with_optional_board(self) -> None:
        self.write_video(board_visible=True)
        run_mocap_pipeline(request=self.request)
        self.assertFalse(self.ipc.pipeline_shutdown_flag.value)
        structure = RecordingStructure(base_directory=self.folder.parent, recording_name=self.folder.name)
        metadata = read_metadata(path=structure.data_parquet_path)
        self.assertIn(CHARUCO_BOARD_MODEL_ID, metadata.runs[0].models)
        self.assertEqual(len(metadata.runs[0].models), 2)
        saved = read_saved_reconstruction(SavedReconstructionRequest(
            structure=structure, run_id=0, sensor_group="mocap", point_source="mocap",
            model_id=CHARUCO_BOARD_MODEL_ID, point_policy=SavedPointPolicy.IDENTITY,
            compute_center_of_mass=True,
        ))
        self.assertEqual(saved.numerical_input.frame_count, 4)
        with av.open(str(self.folder / "annotated_videos" / "input.mp4.annotated.mp4")) as container:
            self.assertEqual(container.streams.video[0].codec_context.name, "h264")
            frames = list(container.decode(video=0))
            self.assertEqual(len(frames), 4)
        self.assertFalse(list(self.folder.rglob("*.partial*")))

    def test_thread_worker_failure_preserves_application_and_error_detail(self) -> None:
        registry = WorkerRegistry(global_kill_flag=self.ipc.global_kill_flag, worker_mode=WorkerMode.PROCESS)
        with patch("freemocap.core.pipeline.posthoc.mocap_pipeline.PipelineIPC.create", return_value=self.ipc):
            pipeline = MocapPipeline.create(pipeline_id=self.ipc.pipeline_id, recording_info=self.recording,
                config=self.config, worker_registry=registry, global_kill_flag=self.ipc.global_kill_flag, inference_service=self.service)
        try:
            pipeline.start()
            pipeline.worker.join(timeout=20.0)
            self.assertFalse(pipeline.alive)
            messages = pipeline.drain_and_get_messages()
            self.assertEqual(messages[-1].phase, AggregatorPhase.FAILED)
            self.assertIn("No video files", messages[-1].detail)
            self.assertFalse(self.ipc.global_kill_flag.value)
        finally:
            pipeline.shutdown()

    def test_cancellation_preserves_existing_annotations_and_discards_partial_output(self) -> None:
        self.write_video(board_visible=False)
        annotated = self.folder / "annotated_videos" / "input_annotated.mp4"
        annotated.parent.mkdir(exist_ok=True)
        annotated.write_bytes(b"previous completed output")

        def cancel_second_frame(
            *, images: dict[str, NDArray[np.uint8]], frame_number: int, states: dict[str, TrackerState],
        ) -> tuple[dict[str, Observation], dict[str, TrackerState]]:
            if frame_number == 1:
                self.ipc.shutdown_pipeline()
            return body_batch(images=images, frame_number=frame_number, states=states)

        self.body.process_batch.side_effect = cancel_second_frame
        run_mocap_pipeline(request=self.request)
        self.assertEqual(annotated.read_bytes(), b"previous completed output")
        self.assertFalse(list(self.folder.rglob("*.partial*")))
        self.assertFalse(self.ipc.global_kill_flag.value)
        self.assertFalse((self.folder / "output_data").exists())

    def test_no_board_still_publishes_mocap_results(self) -> None:
        self.write_video(board_visible=False)
        run_mocap_pipeline(request=self.request)
        structure = RecordingStructure(base_directory=self.folder.parent, recording_name=self.folder.name)
        metadata = read_metadata(path=structure.data_parquet_path)
        self.assertNotIn(CHARUCO_BOARD_MODEL_ID, metadata.runs[0].models)

    def test_worker_failure_reports_and_only_stops_its_pipeline(self) -> None:
        self.write_video(board_visible=False)
        self.body.process_batch.side_effect = RuntimeError("detector failed")
        with self.assertRaisesRegex(RuntimeError, "detector failed"):
            run_mocap_pipeline(request=self.request)
        messages = []
        while True:
            try:
                messages.append(self.progress.get(timeout=0.1))
            except Empty:
                break
        self.assertEqual(messages[-1].phase, AggregatorPhase.FAILED)
        self.assertIn("detector failed", messages[-1].detail)
        self.assertTrue(self.ipc.pipeline_shutdown_flag.value)
        self.assertFalse(self.ipc.global_kill_flag.value)
        self.assertFalse(list(self.folder.rglob("*.partial*")))
