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
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.body = Mock(spec=Tracker)
        self.body.process_batch.side_effect = body_batch
        self.request = MocapDetectionRequest(
            recording_path=self.folder, tracker_config=TrackerConfig(stages=[]), detect_board=True,
            auto_select_board=True, board=CharucoBoardDefinition.create_letter_size_5x3().model_copy(
                update={"square_length_mm": 37.5},
            ), should_continue=lambda: True,
        )

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
        with patch("freemocap.core.pipeline.posthoc.mocap_detection.build_configured_tracker", return_value=self.body):
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
        self.body.close.assert_called_once()

    def test_no_board_is_a_complete_body_recording(self) -> None:
        self.write_recording(camera_count=1, board_at=None)
        with patch("freemocap.core.pipeline.posthoc.mocap_detection.build_configured_tracker", return_value=self.body):
            frames = list(detect_mocap_recording(self.request))
        self.assertEqual(len(frames), 8)
        self.assertTrue(all(frame.selected_board is None for frame in frames))
        self.body.close.assert_called_once()

    def test_closing_iteration_releases_resources(self) -> None:
        self.write_recording(camera_count=2, board_at=None)
        with patch("freemocap.core.pipeline.posthoc.mocap_detection.build_configured_tracker", return_value=self.body):
            frames = detect_mocap_recording(self.request)
            next(frames)
            frames.close()
        self.body.close.assert_called_once()

    def test_detection_failure_propagates_and_releases_resources(self) -> None:
        self.write_recording(camera_count=2, board_at=None)
        self.body.process_batch.side_effect = RuntimeError("detector failure")
        with patch("freemocap.core.pipeline.posthoc.mocap_detection.build_configured_tracker", return_value=self.body):
            with self.assertRaisesRegex(RuntimeError, "detector failure"):
                list(detect_mocap_recording(self.request))
        self.body.close.assert_called_once()

    def test_cancellation_between_frames_releases_resources(self) -> None:
        self.write_recording(camera_count=2, board_at=None)
        continuing = Mock(return_value=True)
        with patch("freemocap.core.pipeline.posthoc.mocap_detection.build_configured_tracker", return_value=self.body):
            frames = detect_mocap_recording(replace(self.request, should_continue=continuing))
            next(frames)
            continuing.return_value = False
            self.assertEqual(list(frames), [])
        self.body.process_batch.assert_called_once()
        self.body.close.assert_called_once()

    def test_disabled_board_tracking_does_not_construct_selector_or_detector(self) -> None:
        self.write_recording(camera_count=1, board_at=0)
        with patch("freemocap.core.pipeline.posthoc.mocap_detection.build_configured_tracker", return_value=self.body), \
                patch("freemocap.core.pipeline.posthoc.mocap_detection.CharucoBoardSelector") as selector, \
                patch("freemocap.core.pipeline.posthoc.mocap_detection.build_charuco_tracker") as board_tracker:
            frames = list(detect_mocap_recording(replace(self.request, detect_board=False)))
        selector.assert_not_called()
        board_tracker.assert_not_called()
        self.assertEqual(len(frames), 8)

    def test_explicit_board_skips_auto_selection_and_preserves_user_geometry(self) -> None:
        self.write_recording(camera_count=1, board_at=None)
        with patch("freemocap.core.pipeline.posthoc.mocap_detection.build_configured_tracker", return_value=self.body), \
                patch("freemocap.core.pipeline.posthoc.mocap_detection.CharucoBoardSelector") as selector:
            frames = list(detect_mocap_recording(replace(self.request, auto_select_board=False)))
        selector.assert_not_called()
        self.assertTrue(all(frame.selected_board is self.request.board for frame in frames))
