import numpy as np
from freemocap.core.kinematics.inertial.composite_inertia import (
    composite_centroidal_inertia,
    principal_axes_and_moments,
    equimomental_semi_axes,
)


def test_point_mass_pair_on_x_axis():
    # Two unit masses at x = +/-1 about the origin.
    # A point mass m at r contributes m((r.r)I - r r^T).
    # On the x-axis that is diag(0, 1, 1); two of them -> diag(0, 2, 2).
    inertia = composite_centroidal_inertia(
        segment_masses={"a": 1.0, "b": 1.0},
        segment_coms={"a": np.array([1.0, 0.0, 0.0]), "b": np.array([-1.0, 0.0, 0.0])},
        whole_body_com=np.zeros(3),
    )
    assert np.allclose(np.diag(inertia), [0.0, 2.0, 2.0])
    assert np.allclose(inertia, inertia.T)  # symmetric
    assert np.allclose(inertia - np.diag(np.diag(inertia)), 0.0)  # no products


def test_principal_axes_and_moments_diagonal():
    inertia = np.diag([2.0, 5.0, 9.0])
    moments, axes = principal_axes_and_moments(inertia)
    assert np.allclose(moments, [2.0, 5.0, 9.0])      # ascending
    assert np.allclose(np.abs(axes), np.eye(3))        # axis-aligned (up to sign)


def test_equimomental_semi_axes_uniform_sphere():
    # A solid sphere of mass M, radius R has I = (2/5) M R^2 on every axis.
    # The equimomental ellipsoid of that inertia is the sphere: a = b = c = R.
    m, r = 3.0, 10.0
    iso = (2.0 / 5.0) * m * r**2
    semi = equimomental_semi_axes(moments=np.array([iso, iso, iso]), total_mass=m)
    assert np.allclose(semi, [r, r, r])
