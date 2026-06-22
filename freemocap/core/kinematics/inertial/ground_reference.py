"""Ground-reference points: CoP (estimated), XCoM (= capture point), CMP.

All inputs/outputs are in millimeters; z is the vertical (up) axis and the ground
plane is z = 0, matching the realtime pipeline's calibrated coordinate frame.
"""
from __future__ import annotations

import numpy as np

GRAVITY_MM_S2: float = 9810.0  # 9.81 m/s^2 in mm units


def center_of_pressure_ground_projection(whole_body_com: np.ndarray) -> np.ndarray:
    """Estimated CoP: the vertical ground projection of the CoM.

    A markerless system has no force plate, so this is an estimate (good for quiet
    stance, increasingly approximate during dynamic motion). Callers should flag it
    as estimated.
    """
    return np.array([whole_body_com[0], whole_body_com[1], 0.0])


def extrapolated_center_of_mass(
    *, com: np.ndarray, com_velocity: np.ndarray, gravity: float = GRAVITY_MM_S2
) -> np.ndarray:
    """XCoM (Hof 2008) = instantaneous capture point: CoM_ground + v / omega0."""
    height = float(com[2])
    if height <= 0.0:
        raise ValueError(f"CoM height must be positive, got {height}")
    omega0 = np.sqrt(gravity / height)
    return np.array([
        com[0] + com_velocity[0] / omega0,
        com[1] + com_velocity[1] / omega0,
        0.0,
    ])


def centroidal_moment_pivot(
    *, com: np.ndarray, com_acceleration: np.ndarray, gravity: float = GRAVITY_MM_S2
) -> np.ndarray:
    """CMP from CoM kinematics.

    With only gravity and the ground acting, the ground reaction force is
    F = M (a - g_vec) with g_vec = (0, 0, -g), so F is proportional to
    (a_x, a_y, a_z + g) and the total mass cancels. The CMP is where the line
    through the CoM along F meets the ground.
    """
    f_vertical = float(com_acceleration[2]) + gravity
    if f_vertical <= 0.0:
        raise ValueError(
            f"vertical reaction force non-positive (a_z={com_acceleration[2]}); "
            f"CMP undefined on the ground plane"
        )
    z = float(com[2])
    return np.array([
        com[0] - (com_acceleration[0] / f_vertical) * z,
        com[1] - (com_acceleration[1] / f_vertical) * z,
        0.0,
    ])
