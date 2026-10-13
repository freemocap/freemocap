"""Real board selection and bounded reader lifecycle checks for application AUTO mode."""
from concurrent.futures import CancelledError
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
import cv2
import numpy as np
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition
from freemocap.core.pipeline.dataflow.video_sources import RecordingVideoSources
from freemocap.core.pipeline.dataflow.application_pipeline import validate_application_graph
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.tracking.board_selection import CharucoBoardMode
from freemocap.core.tracking.recording_board_selection import resolve_recording_board

class RecordingBoardSelectionTests(TestCase):
    def test_auto_selects_real_video_board_preserves_scale_and_does_not_mutate_request(self):
        with TemporaryDirectory() as temp:
            root=Path(temp);video=root/'board.mp4';cal=root/'calibration.toml';cal.write_text('fixture')
            board=CharucoBoardDefinition.create_test_data_7x5()
            image=board.cv2_board.generateImage((700,500),marginSize=30)
            writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'mp4v'),30,(700,500))
            self.assertTrue(writer.isOpened())
            # Include initial misses so the search must advance beyond frame zero.
            for i in range(12):writer.write(cv2.cvtColor(image if i>=5 else np.full_like(image,255),cv2.COLOR_GRAY2BGR))
            writer.release()
            sources=Mock(spec=RecordingVideoSources,camera_sources=(SimpleNamespace(video_metadata=SimpleNamespace(file_path=video,frame_count=12)),))
            config=PosthocMocapPipelineConfig(calibration_toml_path=str(cal),charuco_tracking_enabled=True,board_mode=CharucoBoardMode.AUTO)
            validate_application_graph(config=config)
            resolved=resolve_recording_board(sources=sources,config=config,cancelled=lambda:False,report=lambda detail:None)
            self.assertEqual((resolved.charuco_board.squares_x,resolved.charuco_board.squares_y),(7,5))
            self.assertEqual(resolved.charuco_board.square_length_mm,config.charuco_board.square_length_mm)
            self.assertEqual(config.board_mode,CharucoBoardMode.AUTO)
            self.assertEqual(resolved.board_mode,CharucoBoardMode.EXPLICIT)
            # No open reader handle should prevent immediate file replacement on Windows.
            video.rename(root/'closed.mp4')

    def test_cancelled_search_does_not_open_videos(self):
        config=PosthocMocapPipelineConfig(charuco_tracking_enabled=True,board_mode=CharucoBoardMode.AUTO)
        sources=Mock(spec=RecordingVideoSources,camera_sources=(object(),))
        with self.assertRaises(CancelledError):
            resolve_recording_board(sources=sources,config=config,cancelled=lambda:True,report=lambda detail:None)

    def test_disabled_and_explicit_do_not_search(self):
        sources=Mock(spec=RecordingVideoSources,camera_sources=())
        for config in [PosthocMocapPipelineConfig(charuco_tracking_enabled=False),PosthocMocapPipelineConfig(board_mode=CharucoBoardMode.EXPLICIT)]:
            self.assertIs(resolve_recording_board(sources=sources,config=config,cancelled=lambda:False,report=lambda detail:None),config)

    def test_missing_board_reports_failure_and_closes_readers(self):
        config=PosthocMocapPipelineConfig(charuco_tracking_enabled=True,board_mode=CharucoBoardMode.AUTO)
        sources=Mock(spec=RecordingVideoSources,camera_sources=(SimpleNamespace(video_metadata=SimpleNamespace(file_path=Path('blank.mp4'),frame_count=4)),))
        reader=Mock();reader.read_bgr.return_value=np.full((200,200,3),255,dtype=np.uint8)
        with patch('freemocap.core.tracking.recording_board_selection.SequentialVideoReader',return_value=reader):
            with self.assertRaisesRegex(ValueError,'found no supported'):
                resolve_recording_board(sources=sources,config=config,cancelled=lambda:False,report=lambda detail:None)
        reader.close.assert_called_once()
