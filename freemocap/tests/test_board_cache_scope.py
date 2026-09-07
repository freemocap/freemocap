import pickle
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import numpy as np
from skellytracker.core import DetectionStageConfig, TrackerConfig
from skellytracker.core.data_primitives.observation import Observation, StageObservation
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition, CharucoDetectorConfig
from skellytracker.core.detectors.keypoint_detectors.rtmpose import RTMPoseDetectorConfig
from skellytracker.core.tracker.tracker_state import TrackerState
from skellytracker.core.tracker.tracker import Tracker

from freemocap.core.pipeline.posthoc.video_node import CACHE_FILENAME, _get_observation, _load_cache_by_connection_frame


class BoardCacheScopeTests(unittest.TestCase):
    def test_board_cache_cannot_bypass_body_processing(self) -> None:
        board = CharucoBoardDefinition.create_letter_size_5x3()
        board_stage = DetectionStageConfig(name="charuco", keypoint_detectors=[CharucoDetectorConfig(board=board)])
        body_stage = DetectionStageConfig(name="body", keypoint_detectors=[RTMPoseDetectorConfig()])
        configurations = (
            TrackerConfig(stages=[body_stage, board_stage]),
            TrackerConfig(stages=[board_stage.model_copy(update={"children": [body_stage]})]),
            TrackerConfig(stages=[DetectionStageConfig(
                name="charuco", keypoint_detectors=[CharucoDetectorConfig(board=board), RTMPoseDetectorConfig()],
            )]),
        )
        cached = Observation(frame_number=0, image_size=(24, 32), stages={"charuco": StageObservation(name="charuco")})
        with tempfile.TemporaryDirectory() as directory:
            recording_path = Path(directory)
            cache_path = recording_path / "output_data" / CACHE_FILENAME
            cache_path.parent.mkdir()
            cache_path.write_bytes(pickle.dumps({"board_definition": board, "observations": {"camera": {0: cached}}}))
            for config in configurations:
                with self.subTest(config=config):
                    cache = _load_cache_by_connection_frame(
                        recording_path=recording_path, camera_id="camera", detector_config=config,
                    )
                    self.assertIsNone(cache)
                    detected = Observation(frame_number=0, image_size=(24, 32), stages={
                        "body": StageObservation(name="body"), "charuco": StageObservation(name="charuco"),
                    })
                    state = TrackerState()
                    tracker = Mock(spec=Tracker)
                    tracker.process_image.return_value = detected, state
                    result, _ = _get_observation(
                        frame_number=0, image=np.zeros((24, 32, 3), dtype=np.uint8),
                        tracker=tracker, state=state, cache=cache,
                    )
                    tracker.process_image.assert_called_once()
                    self.assertIs(result, detected)

    def test_board_only_cache_requires_matching_stage_structure(self) -> None:
        board = CharucoBoardDefinition.create_letter_size_5x3()
        config = TrackerConfig(stages=[DetectionStageConfig(
            name="charuco", keypoint_detectors=[CharucoDetectorConfig(board=board)],
        )])
        for stage_name in ("charuco", "another_board"):
            with self.subTest(stage_name=stage_name), tempfile.TemporaryDirectory() as directory:
                recording_path = Path(directory)
                cache_path = recording_path / "output_data" / CACHE_FILENAME
                cache_path.parent.mkdir()
                observation = Observation(frame_number=10, image_size=(24, 32), stages={
                    stage_name: StageObservation(name=stage_name),
                })
                cache_path.write_bytes(pickle.dumps({
                    "board_definition": board, "observations": {"camera": {10: observation}},
                }))
                cache = _load_cache_by_connection_frame(
                    recording_path=recording_path, camera_id="camera", detector_config=config,
                )
                if stage_name == "charuco":
                    self.assertEqual(cache, {10: observation})
                else:
                    self.assertIsNone(cache)
