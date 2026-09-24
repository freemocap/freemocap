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
    frame = SimpleNamespace(landmarks={n:p.array*1700 for n,p in rest.landmark_positions.items()},
        segment_rotations_world={n:q.as_array() for n,q in rest.segment_orientations.items()})
    return bundle, fit, frame


class ConnectedRecordingReviewTests(unittest.TestCase):
    def test_connected_rest_and_source_arrays_are_preserved(self):
        bundle, fit, frame = evidence()
        originals = {n:p.copy() for n,p in frame.landmarks.items()}
        origins, rotations = connected_geometry(bundle,fit,frame)
        self.assertEqual(set(origins), set(bundle.skeleton.segments))
        for name, p in origins.items():
            np.testing.assert_allclose(p.array,bundle.rest_pose.segment_origins[name].array*1700,atol=1e-9)
            self.assertTrue(rotations[name].is_same_rotation(other=bundle.rest_pose.segment_orientations[name]))
        for name in originals:
            np.testing.assert_array_equal(frame.landmarks[name],originals[name])

    def test_missing_ancestor_excludes_all_descendants(self):
        for missing in ('pelvis','left_upper_arm'):
            with self.subTest(missing=missing):
                bundle, fit, frame = evidence()
                frame.segment_rotations_world.pop(missing)
                origins, _ = connected_geometry(bundle,fit,frame)
                self.assertNotIn(missing,origins)
                self.assertNotIn('left_lower_arm',origins)
                if missing != 'pelvis':
                    self.assertIn('right_lower_arm',origins)
                else:
                    self.assertFalse(origins)

    def test_nonfinite_evidence_is_not_filled(self):
        bundle, fit, frame = evidence()
        frame.segment_rotations_world['left_upper_arm'][:] = np.nan
        origins, _ = connected_geometry(bundle,fit,frame)
        self.assertNotIn('left_lower_arm',origins)
        self.assertEqual(connected_geometry(bundle,fit,None), ({},{}))
