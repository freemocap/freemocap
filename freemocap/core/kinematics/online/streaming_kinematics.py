"""Per-frame driver: turns a CoM result + segment data into a BodyKinematicsState.

Holds a short CoM history so velocity (>=2 samples) and acceleration (>=3 samples)
can be finite-differenced online, mirroring the aggregator's existing prev_com
pattern. Ellipsoid + CoP need no history and are always emitted.
"""
from __future__ import annotations

from collections import deque

import numpy as np
from skellyforge.data_models.trajectory_3d import Point3d

from freemocap.core.kinematics.body_kinematics_state import BodyKinematicsState
from freemocap.core.kinematics.inertial.composite_inertia import (
    composite_centroidal_inertia,
    principal_axes_and_moments,
    equimomental_semi_axes,
)
from freemocap.core.kinematics.inertial.ground_reference import (
    GRAVITY_MM_S2,
    center_of_pressure_ground_projection,
    extrapolated_center_of_mass,
    centroidal_moment_pivot,
)


def _p3(vec: np.ndarray) -> Point3d:
    return Point3d(x=float(vec[0]), y=float(vec[1]), z=float(vec[2]))


class StreamingKinematics:
    def __init__(self) -> None:
        self._history: deque[tuple[float, np.ndarray]] = deque(maxlen=3)

    def reset(self) -> None:
        self._history.clear()

    def update(
        self,
        *,
        t: float,
        whole_body_com: np.ndarray,
        segment_coms: dict[str, np.ndarray],
        segment_masses: dict[str, float],
    ) -> BodyKinematicsState:
        com = np.asarray(whole_body_com, dtype=np.float64)
        self._history.append((t, com.copy()))

        # --- ellipsoid (no history needed) ---
        inertia = composite_centroidal_inertia(
            segment_masses=segment_masses,
            segment_coms=segment_coms,
            whole_body_com=com,
        )
        total_mass = sum(segment_masses.get(name, 0.0) for name in segment_coms)
        moments, axes = principal_axes_and_moments(inertia)
        semi = equimomental_semi_axes(moments=moments, total_mass=total_mass)

        # --- derivatives from history ---
        velocity = self._velocity()
        acceleration = self._acceleration()

        xcom = None
        cmp = None
        velocity_p3 = None
        if velocity is not None:
            velocity_p3 = _p3(velocity)
            if com[2] > 0.0:
                xcom = _p3(extrapolated_center_of_mass(com=com, com_velocity=velocity))
        if acceleration is not None and (acceleration[2] + GRAVITY_MM_S2) > 0.0:
            cmp = _p3(centroidal_moment_pivot(com=com, com_acceleration=acceleration))

        return BodyKinematicsState(
            center_of_mass=_p3(com),
            com_velocity=velocity_p3,
            center_of_pressure=_p3(center_of_pressure_ground_projection(com)),
            xcom=xcom,
            cmp=cmp,
            ellipsoid_semi_axes=_p3(semi),
            ellipsoid_axis_x=_p3(axes[:, 0]),
            ellipsoid_axis_y=_p3(axes[:, 1]),
            ellipsoid_axis_z=_p3(axes[:, 2]),
            cop_is_estimated=True,
        )

    def _velocity(self) -> np.ndarray | None:
        if len(self._history) < 2:
            return None
        (t0, p0), (t1, p1) = self._history[-2], self._history[-1]
        dt = t1 - t0
        if dt <= 0.0:
            return None
        return (p1 - p0) / dt

    def _acceleration(self) -> np.ndarray | None:
        if len(self._history) < 3:
            return None
        (t0, p0), (t1, p1), (t2, p2) = self._history[-3], self._history[-2], self._history[-1]
        dt1, dt2 = t1 - t0, t2 - t1
        if dt1 <= 0.0 or dt2 <= 0.0:
            return None
        v01 = (p1 - p0) / dt1
        v12 = (p2 - p1) / dt2
        return (v12 - v01) / (0.5 * (dt1 + dt2))
