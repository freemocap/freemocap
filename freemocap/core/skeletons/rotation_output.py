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
    values = canonical_quaternion_array(np.stack(tuple(rotations.values())))
    return dict(zip(rotations, values, strict=True))


def canonical_quaternion_array(rotations: np.ndarray) -> np.ndarray:
    """Apply the same output convention to any batch of declared wxyz values."""
    values = np.array(rotations, dtype=np.float64, copy=True)
    components = ("w", "x", "y", "z")
    if values.ndim < 1 or values.shape[-1] != len(components) or not np.isfinite(values).all():
        raise ValueError("Rotation outputs must be finite wxyz quaternions")
    if not np.allclose(np.linalg.norm(values, axis=-1), 1, atol=1e-8, rtol=0):
        raise ValueError("Rotation outputs must be unit quaternions")
    first_nonzero = np.argmax(values != 0, axis=-1)
    flip = np.take_along_axis(values, first_nonzero[..., None], axis=-1)[..., 0] < 0
    values[flip] *= -1
    values[values == 0] = 0.0  # One representation of signed zero as well.
    return values


def canonical_joint_angles(
    angles: dict[str, tuple[float, float, float]],
) -> dict[str, tuple[float, float, float]]:
    """Canonicalize outer Euler angles only; preserve the middle-angle convention.

Outer angles use (-pi, pi], with endpoint roundoff snapped to +pi. This
does not remove Euler singularities or guarantee time-series continuity.
"""
    if not angles:
        return {}
    values = canonical_joint_angle_array(np.asarray(tuple(angles.values()), dtype=np.float64))
    return {name: tuple(row) for name, row in zip(angles, values, strict=True)}


def canonical_joint_angle_array(angles: np.ndarray) -> np.ndarray:
    """Canonicalize batches of Euler triples with the scalar path's convention."""
    values = np.array(angles, dtype=np.float64, copy=True)
    euler_components = ("first_angle", "middle_angle", "last_angle")
    if values.ndim < 1 or values.shape[-1] != len(euler_components) or not np.isfinite(values).all():
        raise ValueError("Joint-angle outputs must be finite Euler triples")
    outer_indices = (0, len(euler_components) - 1)
    outer = values[..., outer_indices].copy()
    outside = (outer <= -np.pi) | (outer > np.pi)
    outer[outside] = (outer[outside] + np.pi) % (2 * np.pi) - np.pi
    endpoint = np.abs(np.abs(outer) - np.pi) <= ANGLE_ENDPOINT_TOLERANCE
    outer[endpoint] = np.pi
    outer[outer == 0] = 0.0
    values[..., outer_indices] = outer
    return values
