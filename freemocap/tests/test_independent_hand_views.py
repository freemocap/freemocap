import numpy as np
from skellyforge.core.math.geometry.spatial_vectors import Point
from skellytracker.core.data_primitives.keypoints import Keypoints
from skellytracker.core.data_primitives.observation import Observation, StageObservation
from skellytracker.core.data_primitives.tracked_hand import TrackedHand
from skellytracker.core.io.tracker_profiles import mediapipe_hand_names

from freemocap.core.pipeline.realtime.hand_observations import HandAssociation
from freemocap.core.reconstruction.coordinate_conventions import CALIBRATION_TO_RECONSTRUCTION
from freemocap.core.tasks.triangulation.helpers.triangulation_config import TriangulationConfig
from freemocap.tests.calibration.test_calibration_state_latch import build_loaded_tracker, FITTING_CAMERAS


def test_two_right_hands_reconstruct_separately_with_reversed_local_ids():
    calibration = build_loaded_tracker()
    calibration.bind_live_cameras(live_camera_indices=FITTING_CAMERAS)
    template = np.random.default_rng(17).uniform(0, 80, (21, 3))
    world = [template + [50, 100, 2400], template + [-300, -150, 2000]]
    projected = [calibration.triangulator.project(points) for points in world]
    names = tuple(n.removeprefix("right_hand_") for n in mediapipe_hand_names("right"))
    observations = {}
    for camera, view in FITTING_CAMERAS.items():
        hands = []
        for index in (0, 1):
            image = np.column_stack((projected[index][view], np.zeros(21)))
            hands.append(TrackedHand(index ^ (view % 2), "right", Keypoints(names, image, np.ones(21))))
        observations[camera] = Observation(0, (720, 1280), {"hands": StageObservation("hands", hands=tuple(hands))})
    matcher = HandAssociation()
    for _ in range(2):
        output = matcher.update(observations, calibration, TriangulationConfig(), 5.0, True)
        assert len(output) == 2
        for hand in output:
            assert len(hand.views) == 3 and hand.handedness == "right"
            index = hand.views["cam0"].track_id
            assert hand.track_id == index
            expected = CALIBRATION_TO_RECONSTRUCTION.convert_point(point=Point.from_prevalidated_array(array=world[index]))
            np.testing.assert_allclose(hand.xyz, expected.array, atol=1e-7)
