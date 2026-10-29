"""Core-to-Forge connected-pose boundary, including missing ancestor evidence."""
from types import SimpleNamespace

import numpy as np
import unittest
from skellyforge.core.skeleton.skeleton_definition import SkeletonDefinition
from skellyforge.core.skeleton.pose.rest_pose import RestPose
from skellyforge.core.skeleton.pose.model_scale_fitting import ModelScaleFit

from freemocap.tests.review_connected_recording import connected_geometry


def evidence():
    skeleton = SkeletonDefinition.from_default_yaml()
    rest = RestPose.from_default_yaml(skeleton=skeleton)
    bundle = SimpleNamespace(skeleton=skeleton, rest_pose=rest)
    fit = ModelScaleFit(fitted_scale=1700., segment_scales=dict.fromkeys(skeleton.segments,1700.),
        segment_lengths={n:s.length*1700 for n,s in skeleton.segments.items()},
        measured_segment_names=frozenset(), voting_segment_names=frozenset())
    segment_names = tuple(skeleton.segments)
    origins = np.asarray([[rest.landmark_positions[skeleton.segments[name].frame_definition.origin_point_name].array * 1700
                           for name in segment_names]])
    rotations = np.asarray([[rest.segment_orientations[name].as_array() for name in segment_names]])
    present = np.ones(rotations.shape[:-1], dtype=bool)
    return bundle, fit, origins, rotations, present


class ConnectedRecordingReviewTests(unittest.TestCase):
    def test_connected_rest_and_source_arrays_are_preserved(self):
        bundle, fit, origins, rotations, present = evidence()
        original_origins, original_rotations = origins.copy(), rotations.copy()
        connected = connected_geometry(bundle, fit, origins, rotations, present)
        self.assertTrue(connected.segment_present.all())
        expected = np.asarray([[bundle.rest_pose.segment_origins[name].array * 1700 for name in bundle.skeleton.segments]])
        np.testing.assert_allclose(connected.segment_origins, expected, atol=1e-9)
        np.testing.assert_array_equal(origins, original_origins)
        np.testing.assert_array_equal(rotations, original_rotations)

    def test_missing_ancestor_excludes_all_descendants(self):
        for missing in ('pelvis', 'left_upper_arm'):
            with self.subTest(missing=missing):
                bundle, fit, origins, rotations, present = evidence()
                names = tuple(bundle.skeleton.segments)
                present[:, names.index(missing)] = False
                connected = connected_geometry(bundle, fit, origins, rotations, present)
                self.assertFalse(connected.segment_present[0, names.index(missing)])
                self.assertFalse(connected.segment_present[0, names.index('left_lower_arm')])
                if missing != 'pelvis':
                    self.assertTrue(connected.segment_present[0, names.index('right_lower_arm')])
                else:
                    self.assertFalse(connected.segment_present.any())

    def test_nonfinite_evidence_is_not_filled(self):
        bundle, fit, origins, rotations, present = evidence()
        names = tuple(bundle.skeleton.segments)
        rotations[:, names.index('left_upper_arm')] = np.nan
        present &= np.isfinite(rotations).all(axis=-1)
        connected = connected_geometry(bundle, fit, origins, rotations, present)
        self.assertFalse(connected.segment_present[0, names.index('left_lower_arm')])
        connected = connected_geometry(bundle, fit, origins, rotations, np.zeros_like(present))
        self.assertFalse(connected.segment_present.any())
        self.assertTrue(np.isnan(connected.segment_origins).all())
