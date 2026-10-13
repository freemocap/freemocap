import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from freemocap.tools.datasets.rotation_comparison import euler_errors_radians, quaternion_errors_radians


def test_quaternion_sign_and_known_angular_error():
    identity = np.array([[1., 0., 0., 0.]])
    np.testing.assert_allclose(quaternion_errors_radians(identity, -identity), 0, atol=1e-15)
    changed = Rotation.from_rotvec([[0., 0., 0.01]]).as_quat(scalar_first=True)
    np.testing.assert_allclose(quaternion_errors_radians(identity, changed), 0.01, atol=1e-15)


@pytest.mark.parametrize('bad', [[0., 0., 0., 0.], [2., 0., 0., 0.], [np.nan, 0., 0., 0.], [np.inf, 0., 0., 0.]])
def test_invalid_quaternions_are_not_normalized_away(bad):
    with pytest.raises(ValueError):
        quaternion_errors_radians(np.array([bad]), np.array([bad]))


def test_missing_masks_and_sample_shapes():
    missing = np.full((2, 4), np.nan)
    assert np.isnan(quaternion_errors_radians(missing, missing)).all()
    with pytest.raises(ValueError):
        quaternion_errors_radians(missing, np.tile([1., 0., 0., 0.], (2, 1)))
    with pytest.raises(ValueError):
        quaternion_errors_radians(missing, missing[:1])


@pytest.mark.parametrize('sequence', ['xyz', 'xzy', 'yxz', 'yzx', 'zxy', 'zyx', 'xyx', 'xzx', 'yxy', 'yzy', 'zxz', 'zyz'])
def test_euler_wraps_and_singularities(sequence):
    middle = np.pi / 2 if sequence[0] != sequence[-1] else 0.
    before = np.array([[-np.pi, .3, np.pi], [.2, middle, .7]])
    after = before.copy()
    after[:, 0] += 2 * np.pi
    after[:, 2] -= 2 * np.pi
    np.testing.assert_allclose(euler_errors_radians(before, after, sequence=sequence), 0, atol=2e-15)
    after[0, 1] += .01
    assert euler_errors_radians(before, after, sequence=sequence)[0] > .009
