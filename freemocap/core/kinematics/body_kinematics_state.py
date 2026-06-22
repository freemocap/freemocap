"""Per-frame centroidal-kinematics bundle streamed to the frontend.

Phase 1 carries the point-mass inertia ellipsoid (as a basis + semi-axes; a
quaternion form arrives with the ontology port in Phase 3) and the ground
references. H_G / omega are added in Phase 2.
"""
from __future__ import annotations

import msgspec
from skellyforge.data_models.trajectory_3d import Point3d


class BodyKinematicsState(msgspec.Struct):
    center_of_mass: Point3d
    com_velocity: Point3d | None = None

    # ground references
    center_of_pressure: Point3d | None = None  # estimated (no force plate)
    xcom: Point3d | None = None                # = instantaneous capture point
    cmp: Point3d | None = None

    # reaction-mass ellipsoid (point-mass, Phase 1)
    ellipsoid_semi_axes: Point3d | None = None
    ellipsoid_axis_x: Point3d | None = None
    ellipsoid_axis_y: Point3d | None = None
    ellipsoid_axis_z: Point3d | None = None

    cop_is_estimated: bool = True
