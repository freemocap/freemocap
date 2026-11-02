"""CPU regression checks for artwork attachment fitting; run with Core Python -B."""
import json
from pathlib import Path
import runpy
import unittest

import numpy as np

fit = runpy.run_path(str(Path(__file__).with_name('prepare-skelly-asset.py')))['fit_torso_sockets']


class TorsoSocketFitTests(unittest.TestCase):
    def test_current_asset_socket_targets_are_reached(self):
        asset = json.loads((Path(__file__).parents[1] / 'src/components/viewport3d/renderers/skelly/skelly.json').read_text())
        anchors = asset['torsoSocketFit']
        np.testing.assert_allclose(fit(anchors['source'], anchors['source'], anchors['target']), anchors['target'], atol=1e-14)
        self.assertEqual(asset['artworkScales']['skull'], .9)

    def test_asymmetric_shoulders_preserve_spine_and_neck(self):
        source = np.array([[-.08, 0, .12], [.08, 0, .12]])
        target = np.array([[-.105, -.01, .135], [.095, -.02, .115]])
        centerline = np.array([[0, 0, 0], [0, 0, .12], [0, -.025, .07]])
        points = np.vstack((source, centerline))
        unchanged = points.copy()
        result = fit(points, source, target)
        np.testing.assert_allclose(result[:2], target, atol=1e-14)
        np.testing.assert_array_equal(result[2:], centerline)
        np.testing.assert_array_equal(points, unchanged)

    def test_nonuniform_subject_anchor_fixture_and_units(self):
        source = np.array([[-.08, 0, .12], [.08, 0, .12]])
        target = np.array([[-.08 * 1.15, -.015, .12 * .9], [.08 * .95, -.008, .12 * 1.1]])
        points = np.vstack((source, [[-.04, -.02, .05], [.04, -.02, .05], [0, 0, .12]]))
        for scale in (1360., 1700., 2040.):
            np.testing.assert_allclose(fit(points * scale, source * scale, target * scale),
                                       fit(points, source, target) * scale, atol=1e-12)

    def test_invalid_or_crossed_anchors_are_rejected(self):
        source = np.array([[-.08, 0, .12], [.08, 0, .12]])
        for invalid in (np.zeros((2, 3)), source[::-1], np.full((2, 3), np.nan)):
            with self.assertRaises(ValueError):
                fit(source, source, invalid)


if __name__ == '__main__':
    unittest.main()
