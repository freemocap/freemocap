import unittest

import numpy as np
from skellytracker.core.data_primitives.keypoints import Keypoints
from skellytracker.core.data_primitives.observation import Observation, StageObservation

from freemocap.core.reconstruction.posthoc_reconstruction import triangulate_observation_buffers
from freemocap.core.reconstruction.posthoc_timing import PosthocTimingReport
from freemocap.core.tracking.observation_buffer import ObservationBuffer


def observed_frame(*, frame_number: int, names: tuple[str, ...], visibility: tuple[float, ...]) -> Observation:
    return Observation(frame_number=frame_number, image_size=(100, 100), stages={
        "subjects": StageObservation(name="subjects", keypoints=Keypoints(
            names=names, xyz=np.array([[float(ord(name)), 10., 0.] for name in names]),
            visibility=np.array(visibility),
        )),
    })


class ObservationAlignmentTests(unittest.TestCase):
    def test_late_and_reordered_points_keep_their_identity(self) -> None:
        buffer = ObservationBuffer()
        buffer.add_observation(observed_frame(frame_number=0, names=("a",), visibility=(1.,)))
        buffer.add_observation(observed_frame(frame_number=1, names=("b", "a"), visibility=(1., 1.)))
        buffer.add_observation(observed_frame(frame_number=2, names=("a", "b"), visibility=(0., 1.)))
        self.assertEqual(buffer.keypoint_names, ("subjects.a", "subjects.b"))
        values = buffer.to_keypoints_array(names=buffer.keypoint_names)
        self.assertTrue(np.isnan(values[0, 1]).all())
        self.assertEqual(values[1, 0, 0], float(ord("a")))
        self.assertEqual(values[1, 1, 0], float(ord("b")))
        self.assertTrue(np.isnan(values[2, 0]).all())

    def test_camera_buffers_share_the_same_point_axis(self) -> None:
        first, second = ObservationBuffer(), ObservationBuffer()
        first.add_observation(observed_frame(frame_number=0, names=("a",), visibility=(1.,)))
        second.add_observation(observed_frame(frame_number=0, names=("b", "a"), visibility=(1., 1.)))
        names = tuple(dict.fromkeys((*first.keypoint_names, *second.keypoint_names)))
        first_values = first.to_keypoints_array(names=names)
        second_values = second.to_keypoints_array(names=names)
        np.testing.assert_array_equal(first_values[:, 0], second_values[:, 0])
        self.assertTrue(np.isnan(first_values[:, 1]).all())
        self.assertTrue(np.isfinite(second_values[:, 1]).all())

    def test_planar_reconstruction_includes_points_absent_from_frame_zero(self) -> None:
        buffer = ObservationBuffer()
        buffer.add_observation(observed_frame(frame_number=0, names=("a",), visibility=(1.,)))
        buffer.add_observation(observed_frame(frame_number=1, names=("b", "a"), visibility=(1., 1.)))
        values, names, _ = triangulate_observation_buffers(
            observation_buffers={"camera": buffer}, calibration=None, triangulation_config=None,
            max_reprojection_error_px=None, timing=PosthocTimingReport(),
        )
        self.assertEqual(names, ("a", "b"))
        self.assertEqual(values.shape, (2, 2, 3))
        self.assertTrue(np.isfinite(values[1]).all())
        self.assertFalse(np.isfinite(values[0, 1]).all())

    def test_incomplete_name_axis_fails_instead_of_dropping_measurements(self) -> None:
        buffer = ObservationBuffer()
        buffer.add_observation(observed_frame(frame_number=0, names=("a", "b"), visibility=(1., 1.)))
        with self.assertRaisesRegex(ValueError, "missing from"):
            buffer.to_keypoints_array(names=("subjects.a",))

    def test_camera_frame_mismatch_fails_before_triangulation(self) -> None:
        first, second = ObservationBuffer(), ObservationBuffer()
        first.add_observation(observed_frame(frame_number=0, names=("a",), visibility=(1.,)))
        second.add_observation(observed_frame(frame_number=1, names=("a",), visibility=(1.,)))
        with self.assertRaisesRegex(ValueError, "frame numbers must match"):
            triangulate_observation_buffers(
                observation_buffers={"first": first, "second": second}, calibration=None,
                triangulation_config=None, max_reprojection_error_px=None, timing=PosthocTimingReport(),
            )
