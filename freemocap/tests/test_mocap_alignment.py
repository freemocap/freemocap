"""Whole-recording alignment changes the scene without changing camera projections."""

from dataclasses import replace

import numpy as np
import pytest

from freemocap.core.reconstruction.alignment_config import MocapAlignmentConfig
from freemocap.core.reconstruction.reference_transform import ReferenceTransform
from freemocap.core.recording.sample_encoding.spatial_points import SpatialReference
from pydantic import ValidationError
from freemocap.core.reconstruction.coordinate_conventions import RECONSTRUCTION_TO_CALIBRATION
from freemocap.core.reconstruction.mocap_alignment import MocapAlignmentRequest, align_mocap_recording
from freemocap.core.reconstruction.posthoc_reconstruction import RecordingTriangulation
from freemocap.core.recording.sample_encoding.spatial_points import ReferenceAlignmentDescriptor
from freemocap.core.tasks.calibration.shared.camera_extrinsics import CameraExtrinsics
from freemocap.core.tasks.calibration.shared.camera_intrinsics import CameraIntrinsics
from freemocap.core.tasks.calibration.shared.camera_model import CameraModel
from freemocap.core.tasks.triangulation.helpers.triangulation_result import TriangulationResult
from freemocap.tests.test_alignment_evidence import head_request
from skellyforge.core.biomechanics.reference_alignment import ReferenceAlignmentOutcome
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig


def alignment_request() -> MocapAlignmentRequest:
    evidence = head_request()
    sources = ("first", "second")
    geometry = {name: CameraModel(
        id=name, index=index, image_size=(640, 480),
        intrinsics=CameraIntrinsics(fx=800.0, fy=800.0, cx=320.0, cy=240.0),
        extrinsics=CameraExtrinsics(quaternion_wxyz=np.array([1.,0.,0.,0.]), translation=np.array([float(index)*500,0.,3000.])),
    ) for index, name in enumerate(sources)}
    count, points, _ = evidence.positions.shape
    return MocapAlignmentRequest(
        triangulation=RecordingTriangulation(sources=sources, keypoint_names=evidence.keypoint_names, diagnostic_point_names=evidence.keypoint_names,
            reconstruction=TriangulationResult(points_3d=evidence.positions, diagnostics=None,
                reprojection_error=np.zeros((2,count,points)), per_camera_weights=np.full((count,points,2), .5))),
        camera_geometry=geometry, bundle=evidence.bundle, definition=evidence.definition,
        timestamps_seconds=evidence.timestamps_seconds, has_explicit_ground=False, config=MocapAlignmentConfig(),
    )


def test_body_alignment_preserves_projection_and_roundtrips_description() -> None:
    request = alignment_request()
    result = align_mocap_recording(request=request)
    assert result.alignment.outcome is ReferenceAlignmentOutcome.BODY_REFERENCE
    basis = RECONSTRUCTION_TO_CALIBRATION.matrix
    original = request.triangulation.reconstruction.points_3d @ basis.T
    aligned = result.triangulation.reconstruction.points_3d @ basis.T
    for source, camera in request.camera_geometry.items():
        transformed = result.camera_geometry[source]
        np.testing.assert_allclose(original @ camera.extrinsics.rotation_matrix.T + camera.extrinsics.translation,
            aligned @ transformed.extrinsics.rotation_matrix.T + transformed.extrinsics.translation, atol=1e-8)
    descriptor = ReferenceAlignmentDescriptor.from_result(result=result.alignment)
    assert ReferenceAlignmentDescriptor.model_validate_json(descriptor.model_dump_json()) == descriptor


@pytest.mark.parametrize("explicit", [False, True])
def test_disabled_or_explicit_ground_preserves_objects(explicit: bool) -> None:
    request = replace(alignment_request(), has_explicit_ground=explicit, config=MocapAlignmentConfig(enabled=explicit))
    result = align_mocap_recording(request=request)
    assert result.camera_geometry is request.camera_geometry
    assert result.triangulation is request.triangulation


def test_bad_reprojection_cannot_anchor_the_scene() -> None:
    request = alignment_request()
    request.triangulation.reconstruction.reprojection_error[:] = 1000.0
    assert align_mocap_recording(request=request).alignment.outcome is ReferenceAlignmentOutcome.INSUFFICIENT_EVIDENCE


def test_posthoc_api_alignment_option_roundtrip() -> None:
    config = PosthocMocapPipelineConfig.model_validate({"bodyAlignment": {"enabled": False}})
    assert not config.body_alignment.enabled
    restored = PosthocMocapPipelineConfig.model_validate_json(config.model_dump_json(by_alias=True, round_trip=True))
    assert restored.body_alignment == config.body_alignment


@pytest.mark.parametrize("enabled,explicit", [(True, False), (False, False), (True, True)])
def test_custom_offset_follows_alignment_and_preserves_camera_projection(enabled: bool, explicit: bool) -> None:
    request = replace(alignment_request(), has_explicit_ground=explicit, config=MocapAlignmentConfig(enabled=enabled))
    base = align_mocap_recording(request=request)
    offset = ReferenceTransform(matrix=(0., -1., 0., 125., 1., 0., 0., -80., 0., 0., 1., 42., 0., 0., 0., 1.))
    config = PosthocMocapPipelineConfig.model_validate({
        "bodyAlignment": {"enabled": enabled, "additional_transform": offset.model_dump(mode="json")},
    })
    restored = PosthocMocapPipelineConfig.model_validate_json(config.model_dump_json(by_alias=True, round_trip=True))
    result = align_mocap_recording(request=replace(request, config=restored.body_alignment))
    matrix = np.asarray(offset.matrix).reshape(4, 4)
    np.testing.assert_allclose(result.triangulation.reconstruction.points_3d,
        base.triangulation.reconstruction.points_3d @ matrix[:3, :3].T + matrix[:3, 3], atol=1e-8)
    assert result.alignment.outcome == base.alignment.outcome
    basis = RECONSTRUCTION_TO_CALIBRATION.matrix
    original = request.triangulation.reconstruction.points_3d @ basis.T
    transformed_points = result.triangulation.reconstruction.points_3d @ basis.T
    for source, camera in request.camera_geometry.items():
        transformed_camera = result.camera_geometry[source]
        np.testing.assert_allclose(
            original @ camera.extrinsics.rotation_matrix.T + camera.extrinsics.translation,
            transformed_points @ transformed_camera.extrinsics.rotation_matrix.T + transformed_camera.extrinsics.translation,
            atol=1e-8,
        )
        assert transformed_camera.id == camera.id
        assert transformed_camera.index == camera.index
        assert transformed_camera.intrinsics == camera.intrinsics
    reference = SpatialReference.for_camera_count(2).model_copy(update={
        "alignment": ReferenceAlignmentDescriptor.from_result(result=result.alignment),
        "additional_transform": restored.body_alignment.additional_transform,
    })
    assert SpatialReference.model_validate_json(reference.model_dump_json()) == reference


@pytest.mark.parametrize("index,value", [(0, 2.), (0, -1.), (1, .2), (12, 1.), (15, 0.), (3, float("nan")), (7, float("inf"))])
def test_invalid_custom_offset_is_rejected(index: int, value: float) -> None:
    matrix = np.eye(4).ravel().tolist()
    matrix[index] = value
    with pytest.raises(ValidationError):
        PosthocMocapPipelineConfig.model_validate({"bodyAlignment": {"additional_transform": {"matrix": matrix}}})


def test_custom_offset_requires_metric_geometry() -> None:
    request = alignment_request()
    config = MocapAlignmentConfig(additional_transform=ReferenceTransform(matrix=tuple(np.eye(4).ravel())))
    with pytest.raises(ValueError, match="single-camera output is in pixels"):
        align_mocap_recording(request=replace(request, config=config,
            triangulation=replace(request.triangulation, sources=("first",))))
