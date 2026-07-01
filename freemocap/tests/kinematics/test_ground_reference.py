import numpy as np
import pytest
from freemocap.core.kinematics.inertial.ground_reference import (
    GRAVITY_MM_S2,
    center_of_pressure_ground_projection,
    extrapolated_center_of_mass,
    centroidal_moment_pivot,
)


def test_cop_is_com_dropped_to_ground():
    cop = center_of_pressure_ground_projection(np.array([120.0, -45.0, 1000.0]))
    assert np.allclose(cop, [120.0, -45.0, 0.0])


def test_xcom_offset_scales_with_velocity():
    # omega0 = sqrt(g/l); with l = 1000 mm, omega0 = sqrt(9.81) ~= 3.1321.
    # v_x chosen so v_x/omega0 == 100 mm.
    l = 1000.0
    omega0 = np.sqrt(GRAVITY_MM_S2 / l)
    com = np.array([0.0, 0.0, l])
    vel = np.array([100.0 * omega0, 0.0, 0.0])
    xcom = extrapolated_center_of_mass(com=com, com_velocity=vel)
    assert np.allclose(xcom, [100.0, 0.0, 0.0])


def test_cmp_equals_cop_when_static():
    # Zero CoM acceleration -> ground reaction force is vertical -> CMP == CoP.
    com = np.array([30.0, 10.0, 900.0])
    cmp = centroidal_moment_pivot(com=com, com_acceleration=np.zeros(3))
    assert np.allclose(cmp, [30.0, 10.0, 0.0])


def test_xcom_requires_positive_height():
    with pytest.raises(ValueError):
        extrapolated_center_of_mass(
            com=np.array([0.0, 0.0, -5.0]), com_velocity=np.zeros(3)
        )
