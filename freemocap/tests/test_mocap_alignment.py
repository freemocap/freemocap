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
from freemocap.core.tasks.calibration.shared.calibration_transform import CalibrationTransformType
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
        filtered_points=evidence.positions.copy(),
        triangulation=RecordingTriangulation(sources=sources, keypoint_names=evidence.keypoint_names, diagnostic_point_names=evidence.keypoint_names,
            reconstruction=TriangulationResult(points_3d=evidence.positions, diagnostics=None,
                reprojection_error=np.zeros((2,count,points)), per_camera_weights=np.full((count,points,2), .5))),
        camera_geometry=geometry, bundle=evidence.bundle, definition=evidence.definition,
        timestamps_seconds=evidence.timestamps_seconds, preserve_reference_frame=False, config=MocapAlignmentConfig(),
    )


def test_body_alignment_preserves_projection_and_roundtrips_description() -> None:
    request = alignment_request()
    result = align_mocap_recording(request=request)
    assert result.alignment.outcome is ReferenceAlignmentOutcome.BODY_REFERENCE
    assert tuple(entry.operation for entry in result.transformations) == (
        CalibrationTransformType.PERSON,
    )
    basis = RECONSTRUCTION_TO_CALIBRATION.matrix
    original = request.triangulation.reconstruction.points_3d @ basis.T
    aligned = result.triangulation.reconstruction.points_3d @ basis.T
    for source, camera in request.camera_geometry.items():
        transformed = result.camera_geometry[source]
        np.testing.assert_allclose(original @ camera.extrinsics.rotation_matrix.T + camera.extrinsics.translation,
            aligned @ transformed.extrinsics.rotation_matrix.T + transformed.extrinsics.translation, atol=1e-8)
    descriptor = ReferenceAlignmentDescriptor.from_result(result=result.alignment)
    assert ReferenceAlignmentDescriptor.model_validate_json(descriptor.model_dump_json()) == descriptor


@pytest.mark.parametrize("preserve", [False, True])
def test_disabled_or_preserved_reference_keeps_objects(preserve: bool) -> None:
    request = replace(alignment_request(), preserve_reference_frame=preserve, config=MocapAlignmentConfig(enabled=preserve))
    result = align_mocap_recording(request=request)
    assert result.camera_geometry is request.camera_geometry
    assert result.triangulation is request.triangulation
    assert result.transformations == ()
    assert result.alignment.outcome is (
        ReferenceAlignmentOutcome.PRESERVED_REFERENCE
        if preserve else ReferenceAlignmentOutcome.DISABLED
    )
    assert result.alignment.body_evidence is None
    assert result.alignment.ground_evidence is None
    descriptor = ReferenceAlignmentDescriptor.from_result(result=result.alignment)
    assert ReferenceAlignmentDescriptor.model_validate_json(descriptor.model_dump_json()) == descriptor


def test_alignment_uses_filtered_positions_but_preserves_raw_camera_evidence(monkeypatch):
    from freemocap.core.reconstruction.alignment_evidence import AlignmentEvidence
    request = alignment_request()
    offset = np.array([12., -7., 4.])
    request = replace(request, filtered_points=request.filtered_points + offset)
    raw = request.triangulation.reconstruction.points_3d.copy()
    collect = AlignmentEvidence.collect
    captured = []
    def capture(*, request):
        captured.append(request.positions.copy())
        return collect(request=request)
    monkeypatch.setattr(AlignmentEvidence, 'collect', capture)
    result = align_mocap_recording(request=request)
    np.testing.assert_array_equal(captured[0], request.filtered_points)
    np.testing.assert_array_equal(request.triangulation.reconstruction.points_3d, raw)
    rotation = result.alignment.transform.rotation.to_rotation_matrix()
    np.testing.assert_allclose(
        result.filtered_points - result.triangulation.reconstruction.points_3d,
        np.broadcast_to(rotation @ offset, raw.shape), atol=1e-8,
    )
    assert result.triangulation.reconstruction.reprojection_error is request.triangulation.reconstruction.reprojection_error


def test_bad_reprojection_cannot_anchor_the_scene() -> None:
    request = alignment_request()
    request.triangulation.reconstruction.reprojection_error[:] = 1000.0
    result = align_mocap_recording(request=request)
    assert result.alignment.outcome is ReferenceAlignmentOutcome.INSUFFICIENT_EVIDENCE
    assert result.transformations == ()


def test_posthoc_api_alignment_option_roundtrip() -> None:
    config = PosthocMocapPipelineConfig.model_validate({"bodyAlignment": {"enabled": False}})
    assert not config.body_alignment.enabled
    restored = PosthocMocapPipelineConfig.model_validate_json(config.model_dump_json(by_alias=True, round_trip=True))
    assert restored.body_alignment == config.body_alignment


@pytest.mark.parametrize('mode,aligned,preserve', [
    ('auto', True, True), ('auto', False, False),
    ('calibration', True, True), ('calibration', False, True),
    ('person', True, False), ('person', False, False),
])
def test_alignment_policy(mode, aligned, preserve):
    config = MocapAlignmentConfig(mode=mode)
    request = replace(alignment_request(), config=config,
        preserve_reference_frame=config.preserve_reference_frame(calibration_aligned=aligned))
    result = align_mocap_recording(request=request)
    assert result.alignment.outcome is (ReferenceAlignmentOutcome.PRESERVED_REFERENCE
        if preserve else ReferenceAlignmentOutcome.BODY_REFERENCE)
    assert bool(result.transformations) is not preserve


def test_default_and_legacy_alignment_configuration():
    assert MocapAlignmentConfig().mode == 'auto'
    for enabled, mode in ((True, 'person'), (False, 'calibration')):
        config = MocapAlignmentConfig(enabled=enabled)
        assert config.mode == mode
        assert 'enabled' not in config.model_dump()
        assert MocapAlignmentConfig.model_validate_json(config.model_dump_json()) == config
        with pytest.raises(ValidationError, match='not both'):
            MocapAlignmentConfig(mode=mode, enabled=enabled)


@pytest.mark.parametrize('aligned', [False, True])
@pytest.mark.parametrize('saved', [False, True])
def test_posthoc_uses_loaded_calibration_alignment(tmp_path, monkeypatch, aligned, saved):
    """Full processing and saved detections both consult the actual TOML metadata."""
    from types import SimpleNamespace
    from unittest.mock import Mock
    from skellycam.core.recorders.videos.recording_info import RecordingInfo
    from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition
    from freemocap.core.tasks.calibration.shared.calibration_result import CalibrationResult
    from freemocap.core.tasks.mocap import posthoc_mocap_task as task
    from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata

    request = alignment_request()
    calibration_path = tmp_path / 'calibration.toml'
    CalibrationResult(cameras=list(request.camera_geometry.values()),
        board=CharucoBoardDefinition(squares_x=5, squares_y=3, square_length_mm=50),
        reprojection_error_px=0., initial_cost=0., final_cost=0., n_iterations=0,
        solver_time_seconds=0., n_observations_used=0, n_observations_rejected=0,
        aligned=aligned).save_toml(calibration_path)
    info = RecordingInfo(recording_name='recording', recording_directory=str(tmp_path))
    (tmp_path / 'recording').mkdir(parents=True)
    monkeypatch.setattr(task, 'ObservationRecordingRequest', Mock())
    monkeypatch.setattr(task, 'ObservationGroup', Mock())
    monkeypatch.setattr(task, 'TrackerRecordingDefinition', Mock())
    monkeypatch.setattr(task, 'publish_posthoc_observations', Mock())
    monkeypatch.setattr(task, 'PosthocMatchingRequest', Mock(return_value=Mock(
        resolve=Mock(return_value=request.camera_geometry))))
    monkeypatch.setattr(task, 'triangulate_observation_buffers', Mock(return_value=request.triangulation))
    timing = Mock(spec=task.RecordingGroupTiming,
        synchronized=SimpleNamespace(timestamps_s=request.timestamps_seconds))
    monkeypatch.setattr(task.RecordingGroupTiming, 'resolve', Mock(return_value=timing))
    monkeypatch.setattr(task, 'prepare_recording_points', Mock(return_value=SimpleNamespace(
        points=request.filtered_points, report=SimpleNamespace(gap_filling=Mock(
            measured_support=Mock(return_value=np.isfinite(request.filtered_points).all(axis=-1)))))))
    captured = []
    def capture(*, request):
        captured.append(request)
        raise RuntimeError('alignment reached')
    monkeypatch.setattr(task, 'align_mocap_recording', capture)
    with pytest.raises(RuntimeError, match='alignment reached'):
        task.run_posthoc_mocap_task(frame_observations=[], recording_info=info,
            video_metadata={source: Mock(spec=VideoMetadata) for source in request.camera_geometry},
            task_config=PosthocMocapPipelineConfig(calibration_toml_path=str(calibration_path),
                detector_type='mediapipe'), selected_board=None, saved_timing=timing if saved else None)
    assert captured[0].preserve_reference_frame is aligned


@pytest.mark.parametrize("enabled,preserve", [(True, False), (False, False), (True, True)])
def test_custom_offset_follows_alignment_and_preserves_camera_projection(enabled: bool, preserve: bool) -> None:
    request = replace(alignment_request(), preserve_reference_frame=preserve, config=MocapAlignmentConfig(enabled=enabled))
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
    expected_operations = (
        (CalibrationTransformType.PERSON, CalibrationTransformType.MANUAL)
        if enabled and not preserve else (CalibrationTransformType.MANUAL,)
    )
    assert tuple(entry.operation for entry in result.transformations) == expected_operations
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


def test_person_and_manual_operations_save_the_same_camera_geometry(tmp_path) -> None:
    from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition
    from freemocap.core.tasks.calibration.shared.calibration_result import CalibrationResult
    from freemocap.core.tasks.calibration.shared.calibration_update import CalibrationUpdateRequest
    from freemocap.core.tasks.calibration.shared.loaded_calibration import LoadedCalibration
    from freemocap.core.tasks.calibration.shared.groundplane_alignment import CalibrationAlignmentMethod

    request = alignment_request()
    request = replace(request, config=MocapAlignmentConfig(
        additional_transform=ReferenceTransform(
            matrix=(0., -1., 0., 125., 1., 0., 0., -80., 0., 0., 1., 42., 0., 0., 0., 1.),
        ),
    ))
    path = tmp_path / "calibration.toml"
    source = CalibrationResult(
        cameras=list(request.camera_geometry.values()),
        board=CharucoBoardDefinition(squares_x=5, squares_y=3, square_length_mm=50),
        reprojection_error_px=0., initial_cost=0., final_cost=0.,
        n_iterations=0, solver_time_seconds=0.,
        n_observations_used=0, n_observations_rejected=0,
    )
    source.save_toml(path)
    original = path.read_bytes()
    loaded = LoadedCalibration.from_path(path)
    aligned = align_mocap_recording(request=request)
    assert path.read_bytes() == original
    assert aligned.alignment.outcome is ReferenceAlignmentOutcome.BODY_REFERENCE

    saved = CalibrationUpdateRequest(
        path=path, expected_mtime_ms=loaded.mtime_ms,
        transformations=aligned.transformations,
        recording_id="person-alignment-test",
    ).save()
    assert saved.metadata.aligned
    assert saved.metadata.alignment_method is CalibrationAlignmentMethod.PERSON
    assert saved.metadata.alignment_recording_id == "person-alignment-test"
    assert saved.metadata.transformation_history == list(aligned.transformations)
    reloaded = CalibrationResult.load_toml(path)
    for camera in reloaded.cameras:
        expected = aligned.camera_geometry[camera.id]
        np.testing.assert_allclose(
            camera.extrinsics.rotation_matrix, expected.extrinsics.rotation_matrix, atol=1e-8,
        )
        np.testing.assert_allclose(
            camera.extrinsics.translation, expected.extrinsics.translation, atol=1e-8,
        )
