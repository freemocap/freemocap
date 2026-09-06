import multiprocessing
import tempfile
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
import unittest
from unittest.mock import Mock, patch

import cv2
from pathlib import Path
import numpy as np
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition

from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.posthoc.calibration_pipeline import CalibrationPipeline
from freemocap.core.pipeline.posthoc.pipeline_phases import AggregatorPhase
from freemocap.core.tasks.calibration.calibration_task_config import CalibrationBoardMode, PosthocCalibrationPipelineConfig


class CalibrationPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.ipc = Mock(spec=PipelineIPC)
        self.ipc.should_continue = True
        self.ipc.pipeline_shutdown_flag = multiprocessing.Value('b', False)
        self.ipc.global_kill_flag = multiprocessing.Value('b', False)
        self.ipc.ws_queue = None
        self.preparation = CalibrationPipeline(
            id="selection", recording_info=RecordingInfo(recording_name="board", recording_directory=self.directory.name),
            config=PosthocCalibrationPipelineConfig(), ipc=self.ipc, worker_registry=Mock(spec=WorkerRegistry),
        )

    def test_selection_configures_all_detectors_and_solver_once(self) -> None:
        measured_square_length_mm = 37.5
        self.preparation.config.charuco_board.square_length_mm = measured_square_length_mm
        for board in (CharucoBoardDefinition.create_letter_size_5x3(), CharucoBoardDefinition.create_test_data_7x5()):
            with self.subTest(board=board):
                image = board.cv2_board.generateImage((840, 600), marginSize=30)
                first_camera = Mock()
                first_camera.read_frame_number.return_value = np.full_like(image, 255)
                second_camera = Mock()
                second_camera.read_frame_number.return_value = image
                group = Mock(frame_count=100, videos={"first": first_camera, "second": second_camera})
                with patch("freemocap.core.pipeline.posthoc.calibration_pipeline.VideoGroupHelper.from_recording_path", return_value=group), patch("freemocap.core.pipeline.posthoc.calibration_pipeline.PosthocPipeline.create") as create:
                    self.preparation._prepare_calibration()
                    create.assert_called_once()
                    args = create.call_args.kwargs
                    resolved = args["aggregation_task_fn"].keywords["task_config"]
                    self.assertEqual(resolved.charuco_board, board.model_copy(update={"square_length_mm": measured_square_length_mm}))
                    self.assertEqual(resolved.board_mode, CalibrationBoardMode.EXPLICIT)
                    self.assertEqual(args["detector_config"], resolved.detector_config)
                    self.assertEqual(args["pipeline_id"], self.preparation.id)
                    first_camera.read_frame_number.assert_called_once_with(frame_number=0)
                    second_camera.read_frame_number.assert_called_once_with(frame_number=0)
                    group.close.assert_called_once()
                    create.return_value.start.assert_called_once()

    def test_no_board_reports_failure_without_starting_processing(self) -> None:
        video = Mock()
        video.read_frame_number.return_value = np.full((240, 320), 255, dtype=np.uint8)
        group = Mock(frame_count=2, videos={"camera": video})
        with patch("freemocap.core.pipeline.posthoc.calibration_pipeline.VideoGroupHelper.from_recording_path", return_value=group), patch("freemocap.core.pipeline.posthoc.calibration_pipeline.PosthocPipeline.create") as create:
            self.preparation._prepare_calibration()
            create.assert_not_called()
        self.assertEqual(self.preparation.progress.phase, AggregatorPhase.FAILED)
        self.assertIn("could not detect", self.preparation.progress.detail)
        group.close.assert_called_once()

    def test_cancelled_selection_closes_readers_without_starting_processing(self) -> None:
        self.ipc.should_continue = False
        group = Mock(frame_count=2, videos={"camera": Mock()})
        with patch("freemocap.core.pipeline.posthoc.calibration_pipeline.VideoGroupHelper.from_recording_path", return_value=group), patch("freemocap.core.pipeline.posthoc.calibration_pipeline.PosthocPipeline.create") as create:
            self.preparation._prepare_calibration()
            create.assert_not_called()
        group.close.assert_called_once()

    def test_explicit_board_does_not_scan_videos(self) -> None:
        self.preparation.config = PosthocCalibrationPipelineConfig(board_mode=CalibrationBoardMode.EXPLICIT)
        with patch("freemocap.core.pipeline.posthoc.calibration_pipeline.VideoGroupHelper.from_recording_path") as scan, patch("freemocap.core.pipeline.posthoc.calibration_pipeline.PosthocPipeline.create") as create:
            self.preparation._prepare_calibration()
            scan.assert_not_called()
            create.return_value.start.assert_called_once()

    def test_managed_thread_prepares_and_starts_pipeline(self) -> None:
        registry = WorkerRegistry(global_kill_flag=self.ipc.global_kill_flag, worker_mode=WorkerMode.PROCESS)
        preparation = CalibrationPipeline(
            id="thread-selection", recording_info=self.preparation.recording_info,
            config=PosthocCalibrationPipelineConfig(board_mode=CalibrationBoardMode.EXPLICIT),
            ipc=self.ipc, worker_registry=registry,
        )
        with patch("freemocap.core.pipeline.posthoc.calibration_pipeline.PosthocPipeline.create") as create:
            preparation.start()
            preparation.worker.join(timeout=5.0)
            self.assertFalse(preparation.worker.is_alive())
            self.assertEqual(preparation.worker.exitcode, 0)
            create.return_value.start.assert_called_once()
            preparation.shutdown()
            create.return_value.shutdown.assert_called_once()


    def test_auto_reads_encoded_video_through_recording_loader(self) -> None:
        board = CharucoBoardDefinition.create_letter_size_5x3()
        image = cv2.cvtColor(board.cv2_board.generateImage((600, 360), marginSize=30), cv2.COLOR_GRAY2BGR)
        folder = Path(self.preparation.recording_info.full_recording_path) / "synchronized_videos"
        folder.mkdir()
        filename = "2026-09-06_10-51-40_GMT-4.id-0001.idx-0.avi"
        writer = cv2.VideoWriter(str(folder / filename), cv2.VideoWriter_fourcc(*"MJPG"), 30.0, (600, 360))
        self.assertTrue(writer.isOpened())
        try:
            writer.write(np.full_like(image, 255))
            writer.write(image)
        finally:
            writer.release()
        for manifest in ({}, {"0001": filename}):
            with self.subTest(manifest=bool(manifest)), patch("freemocap.core.pipeline.posthoc.video_group_helper._load_manifest_videos", return_value=manifest), patch("freemocap.core.pipeline.posthoc.calibration_pipeline.PosthocPipeline.create") as create:
                self.preparation._prepare_calibration()
                create.assert_called_once()
                resolved = create.call_args.kwargs["aggregation_task_fn"].keywords["task_config"]
                self.assertEqual(resolved.charuco_board.squares_x, 5)
                self.assertEqual(resolved.charuco_board.squares_y, 3)
                create.return_value.start.assert_called_once()
