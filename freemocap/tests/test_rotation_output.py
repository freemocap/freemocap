import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from freemocap.core.skeletons.rotation_output import (
    ANGLE_ENDPOINT_TOLERANCE,
    canonical_joint_angles,
    canonical_quaternion_outputs,
)
from freemocap.tools.datasets.rotation_comparison import euler_errors_radians


def test_quaternion_policy_matches_scipy_and_preserves_input():
    random = Rotation.random(100, random_state=31).as_quat(scalar_first=True)
    half_turns = np.array([[0., -1., 0., 0.], [0., 0., -1., 0.], [0., 0., 0., -1.]])
    inputs = np.concatenate((random, half_turns))
    originals = inputs.copy()
    actual = np.stack(tuple(canonical_quaternion_outputs({str(i): q for i, q in enumerate(inputs)}).values()))
    expected = Rotation.from_quat(inputs, scalar_first=True).as_quat(canonical=True, scalar_first=True)
    np.testing.assert_allclose(actual, expected, atol=1e-15)
    negated = np.stack(tuple(canonical_quaternion_outputs({str(i): q for i, q in enumerate(-inputs)}).values()))
    np.testing.assert_array_equal(actual, negated)
    np.testing.assert_array_equal(inputs, originals)
    assert not np.shares_memory(actual, inputs)


def test_invalid_quaternion_is_not_silently_repaired():
    with pytest.raises(ValueError):
        canonical_quaternion_outputs({'bone': np.zeros(4)})


@pytest.mark.parametrize('sequence', ['xyz', 'xzy', 'yxz', 'yzx', 'zxy', 'zyx', 'xyx', 'xzx', 'yxy', 'yzy', 'zxz', 'zyz'])
def test_endpoint_rounding_is_bounded_and_idempotent(sequence):
    tolerance = ANGLE_ENDPOINT_TOLERANCE
    source = {'joint': (-np.pi + tolerance / 2, .37, np.pi - tolerance / 2)}
    result = canonical_joint_angles(source)
    assert result == {'joint': (np.pi, .37, np.pi)}
    assert canonical_joint_angles(result) == result
    error = euler_errors_radians(np.array(list(source.values())), np.array(list(result.values())), sequence=sequence)
    assert error.max() <= 2 * tolerance + 1e-15
    outside = {'joint': (-np.pi + 2 * tolerance, .37, np.pi - 2 * tolerance)}
    assert canonical_joint_angles(outside) == outside


def test_empty_outputs_and_middle_angle_are_preserved():
    assert canonical_joint_angles({}) == {}
    assert canonical_quaternion_outputs({}) == {}
    assert canonical_joint_angles({'joint': (-np.pi, -np.pi, np.pi)}) == {'joint': (np.pi, -np.pi, np.pi)}

