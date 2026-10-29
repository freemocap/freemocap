"""Preserve point identity and missing-data decisions when checking an array at once."""
import unittest
import numpy as np
from freemocap.tests.recording_tensor_assertions import _finite_frame_points

class FiniteFramePointTests(unittest.TestCase):
    def test_matches_old_checks_with_missing_coordinates_and_strided_input(self):
        rng = np.random.default_rng(31)
        values = rng.normal(size=(100, 3))
        values[::7, 0] = np.nan
        values[::11, 2] = np.inf
        values[::13, 1] = -np.inf
        for frame in (values, values[::2], np.full((4, 3), np.nan), np.zeros((0, 3))):
            names = tuple(f'point{i}' for i in range(len(frame)))
            expected = {name: frame[i] for i, name in enumerate(names) if np.all(np.isfinite(frame[i]))}
            actual = _finite_frame_points(frame=frame, point_names=names)
            self.assertEqual(list(actual), list(expected))
            for name in expected:
                np.testing.assert_array_equal(actual[name], expected[name])
                self.assertTrue(np.shares_memory(actual[name], frame))

if __name__ == '__main__': unittest.main()
