"""Coordinate changes preserve camera projections and reconstruction conventions."""

import numpy as np

from skellyforge.core.math.geometry.rotation_quaternion import RotationQuaternion
from skellyforge.core.math.geometry.spatial_vectors import Displacement, Point
from skellyforge.core.math.geometry.transform_math import Transform

from freemocap.core.reconstruction.coordinate_conventions import (
    CALIBRATION_TO_RECONSTRUCTION, RECONSTRUCTION_TO_CALIBRATION,
)
from freemocap.core.tasks.calibration.shared.camera_extrinsics import CameraExtrinsics
from freemocap.core.tasks.calibration.shared.camera_intrinsics import CameraIntrinsics
from freemocap.core.tasks.calibration.shared.camera_model import CameraModel


def test_camera_world_transform_preserves_projection_and_identity() -> None:
    camera = CameraModel(
        id="physical-camera", index=7, image_size=(640, 480),
        intrinsics=CameraIntrinsics(fx=800.0, fy=810.0, cx=320.0, cy=240.0, k1=0.1),
        extrinsics=CameraExtrinsics(
            quaternion_wxyz=RotationQuaternion.from_rotation_vector(rotation_vector=np.array([.1, -.3, .2])).as_array(),
            translation=np.array([100., 20., 500.]),
        ),
    )
    transform = Transform(
        rotation=RotationQuaternion.from_rotation_vector(rotation_vector=np.array([.3, .4, -.5])),
        translation=Displacement.from_xyz(x=10.0, y=-400.0, z=250.0),
    )
    points = Point.from_array(values=np.array([[10., 20., 30.], [-40., 70., 100.]]))
    transformed = camera.in_world_frame(transform=transform)
    projected = points.array @ camera.extrinsics.rotation_matrix.T + camera.extrinsics.translation
    actual = transform.apply(points=points).array @ transformed.extrinsics.rotation_matrix.T + transformed.extrinsics.translation
    np.testing.assert_allclose(actual, projected, atol=1e-10)
    assert transformed.id == camera.id and transformed.index == camera.index
    assert transformed.image_size == camera.image_size
    assert transformed.intrinsics == camera.intrinsics
    np.testing.assert_allclose(transformed.world_position, transformed.extrinsics.world_position)
    np.testing.assert_allclose(transformed.world_orientation, transformed.extrinsics.world_orientation)
    restored = transformed.in_world_frame(transform=transform.inverse())
    np.testing.assert_allclose(restored.projection_matrix, camera.projection_matrix, atol=1e-9)
    np.testing.assert_allclose(camera.extrinsics.translation, [100., 20., 500.])


def test_coordinate_binding_supports_batches_and_inverse() -> None:
    positions = np.array([[[1., 2., 3.], [-4., 5., 6.]]])
    converted = CALIBRATION_TO_RECONSTRUCTION.convert_point(point=Point.from_array(values=positions))
    np.testing.assert_array_equal(converted.array, [[[-2., 1., 3.], [-5., -4., 6.]]])
    np.testing.assert_array_equal(RECONSTRUCTION_TO_CALIBRATION.convert_point(point=converted).array, positions)
