"""Canonical reconstruction outputs; never applied to temporal solver state.

See rotation-output-contract.md for conventions and the endpoint error bound.
"""

import numpy as np

# Deliberate float64 endpoint rounding, not a scientific comparison tolerance.
ANGLE_ENDPOINT_TOLERANCE = 32 * np.finfo(np.float64).eps * np.pi


def canonical_quaternion_outputs(rotations: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Choose positive first nonzero wxyz component, without changing magnitude.

This is SciPy's positive-w policy including its exact half-turn tie break
[@scipyRotationQuaternion]. Arrays are newly owned; solver state is untouched.
"""
    if not rotations:
        return {}
    values = np.stack(tuple(rotations.values())).astype(np.float64, copy=True)
    if values.shape != (len(rotations), 4) or not np.isfinite(values).all():
        raise ValueError("Rotation outputs must be finite wxyz quaternions")
    if not np.allclose(np.linalg.norm(values, axis=1), 1, atol=1e-8, rtol=0):
        raise ValueError("Rotation outputs must be unit quaternions")
    first_nonzero = np.argmax(values != 0, axis=1)
    flip = values[np.arange(len(values)), first_nonzero] < 0
    values[flip] *= -1
    values[values == 0] = 0.0  # One representation of signed zero as well.
    return dict(zip(rotations, values, strict=True))


def canonical_joint_angles(
    angles: dict[str, tuple[float, float, float]],
) -> dict[str, tuple[float, float, float]]:
    """Canonicalize outer Euler angles only; preserve the middle-angle convention.

Outer angles use (-pi, pi], with endpoint roundoff snapped to +pi. This
does not remove Euler singularities or guarantee time-series continuity.
"""
    if not angles:
        return {}
    values = np.asarray(tuple(angles.values()), dtype=np.float64).copy()
    if values.shape != (len(angles), 3) or not np.isfinite(values).all():
        raise ValueError("Joint-angle outputs must be finite Euler triples")
    outer = values[:, (0, 2)].copy()
    outside = (outer <= -np.pi) | (outer > np.pi)
    outer[outside] = (outer[outside] + np.pi) % (2 * np.pi) - np.pi
    endpoint = np.abs(np.abs(outer) - np.pi) <= ANGLE_ENDPOINT_TOLERANCE
    outer[endpoint] = np.pi
    outer[outer == 0] = 0.0
    values[:, (0, 2)] = outer
    return {name: tuple(row) for name, row in zip(angles, values, strict=True)}
