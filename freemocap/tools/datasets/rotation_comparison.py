"""Rotation-aware numerical checks for optimization experiments, not runtime state.

Quaternions are wxyz; Euler sequences are explicitly intrinsic, as in Forge.
See [@scipyRotationQuaternion; @scipyRotationEuler; @scipyRotationMagnitude].
"""

import numpy as np
from scipy.spatial.transform import Rotation


def quaternion_errors_radians(expected: np.ndarray, actual: np.ndarray) -> np.ndarray:
    """Shortest relative rotation angles; missing samples remain NaN.

Reject invalid/nonunit inputs before SciPy's automatic normalization can hide
them. Equivalent q/-q values are accepted. No broadcasting of sample identity.
"""
    first, second = np.asarray(expected, dtype=float), np.asarray(actual, dtype=float)
    if first.shape != second.shape or first.ndim < 1 or first.shape[-1] != 4:
        raise ValueError("Expected matching (..., 4) wxyz arrays")
    missing = np.isnan(first).all(axis=-1)
    if not np.array_equal(np.isnan(first), np.isnan(second)):
        raise ValueError("Quaternion missing-data masks differ")
    for values in (first, second):
        present = values[~missing]
        if not np.isfinite(present).all():
            raise ValueError("Quaternion samples must be finite or entirely missing")
        if not np.allclose(np.linalg.norm(present, axis=-1), 1, atol=1e-8, rtol=0):
            raise ValueError("Quaternion samples must have unit norm")
    errors = np.full(first.shape[:-1], np.nan)
    if (~missing).any():
        before = Rotation.from_quat(first[~missing], scalar_first=True)
        after = Rotation.from_quat(second[~missing], scalar_first=True)
        errors[~missing] = (before.inv() * after).magnitude()
    return errors


def euler_errors_radians(expected: np.ndarray, actual: np.ndarray, *, sequence: str) -> np.ndarray:
    """Compare rotations represented by Forge intrinsic Euler triples.

This checks rotation equivalence, not equality of clinical angle conventions.
The caller must also verify matching joint definitions and angle conventions.
"""
    first, second = np.asarray(expected, dtype=float), np.asarray(actual, dtype=float)
    if first.shape != second.shape or first.ndim < 1 or first.shape[-1] != 3:
        raise ValueError("Expected matching (..., 3) Euler arrays")
    if len(sequence) != 3 or any(axis not in 'xyz' for axis in sequence):
        raise ValueError("Declare a three-axis lowercase intrinsic Forge sequence")
    if not np.array_equal(np.isnan(first), np.isnan(second)):
        raise ValueError("Euler missing-data masks differ")
    missing = np.isnan(first).all(axis=-1)
    if not np.isfinite(first[~missing]).all() or not np.isfinite(second[~missing]).all():
        raise ValueError("Euler samples must be finite or entirely missing")
    errors = np.full(first.shape[:-1], np.nan)
    if (~missing).any():
        before = Rotation.from_euler(sequence.upper(), first[~missing])
        after = Rotation.from_euler(sequence.upper(), second[~missing])
        errors[~missing] = (before.inv() * after).magnitude()
    return errors
