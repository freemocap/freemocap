"""Composite centroidal inertia (CCRBI) and its display ellipsoid.

Point-mass form for Phase 1: each segment contributes only the parallel-axis
("orbital") term m((d.d)I - d d^T). Segment self-inertia J_i is added in Phase 2.
"""
from __future__ import annotations

import numpy as np


def composite_centroidal_inertia(
    *,
    segment_masses: dict[str, float],
    segment_coms: dict[str, np.ndarray],
    whole_body_com: np.ndarray,
    segment_inertias: dict[str, np.ndarray] | None = None,
) -> np.ndarray:
    """Composite centroidal inertia tensor I_G (3x3, symmetric).

    Sums the parallel-axis contribution of every segment whose CoM is present.
    ``segment_inertias`` (per-segment J_i about its own CoM, world frame) is
    optional and unused in Phase 1.
    """
    inertia = np.zeros((3, 3), dtype=np.float64)
    for name, com in segment_coms.items():
        mass = segment_masses.get(name, 0.0)
        if mass <= 0.0:
            continue
        d = np.asarray(com, dtype=np.float64) - whole_body_com
        inertia += mass * (float(d @ d) * np.eye(3) - np.outer(d, d))
        if segment_inertias is not None and name in segment_inertias:
            inertia += segment_inertias[name]
    return inertia


def principal_axes_and_moments(inertia: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Eigendecomposition of a symmetric inertia tensor.

    Returns ``(moments, axes)``: ``moments`` ascending (3,); ``axes`` columns are
    the corresponding principal-axis unit vectors (3, 3).
    """
    moments, axes = np.linalg.eigh(inertia)
    return moments, axes


def equimomental_semi_axes(*, moments: np.ndarray, total_mass: float) -> np.ndarray:
    """Semi-axes of the uniform solid ellipsoid with the given principal moments.

    For a uniform solid ellipsoid (semi-axes a,b,c) of mass M:
        I_x = M (b^2 + c^2) / 5   (and cyclic),
    which inverts to  a^2 = (5 / (2 M)) (I_y + I_z - I_x).
    The bracket is non-negative for any physical inertia (triangle inequality of
    principal moments); tiny negative values from numeric noise are clamped to 0.
    """
    if total_mass <= 0.0:
        raise ValueError(f"total_mass must be positive, got {total_mass}")
    ix, iy, iz = float(moments[0]), float(moments[1]), float(moments[2])
    raw = np.array([iy + iz - ix, ix + iz - iy, ix + iy - iz], dtype=np.float64)
    if np.any(raw < -1e-6 * max(ix, iy, iz, 1.0)):
        raise ValueError(f"principal moments violate the triangle inequality: {moments}")
    return np.sqrt(np.clip(raw, 0.0, None) * (5.0 / (2.0 * total_mass)))
