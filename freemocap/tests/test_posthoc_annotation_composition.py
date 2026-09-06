import unittest

import numpy as np
from skellytracker.core import DetectionStageConfig, TrackerConfig
from skellytracker.core.data_primitives.observation import Observation, StageObservation
from skellytracker.core.data_primitives.keypoints import Keypoints
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition, CharucoDetectorConfig

from freemocap.core.pipeline.posthoc.video_node import _build_annotator


class PosthocAnnotationCompositionTests(unittest.TestCase):
    def test_configured_board_and_body_are_both_rendered(self) -> None:
        board = CharucoBoardDefinition.create_letter_size_5x3()
        for nested in (False, True):
            with self.subTest(nested=nested):
                board_config = DetectionStageConfig(name="calibration_board", keypoint_detectors=[CharucoDetectorConfig(board=board)])
                body_config = DetectionStageConfig(name="body", children=[board_config] if nested else [])
                renderer = _build_annotator(TrackerConfig(stages=[body_config] if nested else [body_config, board_config]))
                board_observation = StageObservation(name="calibration_board", keypoints=Keypoints(
                    names=("CharucoCorner-0",), xyz=np.array([[180.0, 160.0, 0.0]]), visibility=np.ones(1),
                ))
                body_observation = StageObservation(name="body", keypoints=Keypoints(
                    names=("test_point",), xyz=np.array([[40.0, 70.0, 0.0]]), visibility=np.ones(1),
                ), children={"calibration_board": board_observation} if nested else {})
                stages = {"body": body_observation}
                if not nested:
                    stages["calibration_board"] = board_observation
                base = np.zeros((360, 600, 3), dtype=np.uint8)
                base[320:330, 20:30] = 255
                output = renderer.annotate(image=base, observation=Observation(frame_number=0, image_size=(360, 600), stages=stages))
                self.assertTrue(np.any(output[65:76, 35:46]))
                self.assertTrue(np.any(output[153:168, 173:188]))
                np.testing.assert_array_equal(output[320:330, 20:30], base[320:330, 20:30])
                self.assertFalse(np.any(base[:300]))
