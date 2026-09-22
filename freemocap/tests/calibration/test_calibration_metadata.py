"""Calibration metadata survives disk and JSON serialization."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
import tomllib

import numpy as np
import cv2
import tomli_w
from pydantic import ValidationError
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition

from freemocap.core.tasks.calibration.calibration_task_config import CalibrationSolverMethod
from freemocap.core.tasks.calibration.shared.calibration_metadata import CalibrationMetadata
from freemocap.core.tasks.calibration.shared.calibration_toml import (
    CalibrationToml,
)
from freemocap.core.tasks.calibration.shared.calibration_result import CalibrationResult
from freemocap.core.tasks.calibration.shared.camera_model import CameraModel
from freemocap.core.tasks.calibration.shared.camera_intrinsics import CameraIntrinsics
from freemocap.core.tasks.calibration.shared.camera_extrinsics import CameraExtrinsics
from freemocap.core.tasks.calibration.shared.groundplane_alignment import (
    CalibrationAlignmentMethod,
    GroundPlaneResult,
)


class CalibrationMetadataTests(TestCase):
    def test_transform_history_round_trip_and_inverse(self) -> None:
        from skellyforge.core.math.geometry.rotation_quaternion import RotationQuaternion
        from skellyforge.core.math.geometry.spatial_vectors import Displacement, Point
        from skellyforge.core.math.geometry.transform_math import Transform

        from freemocap.core.tasks.calibration.shared.calibration_transform import (
            CalibrationTransform, CalibrationTransformType,
        )

        transforms = [
            Transform(
                rotation=RotationQuaternion.identity(),
                translation=Displacement.from_xyz(x=10., y=20., z=30.),
            ),
            Transform(
                rotation=RotationQuaternion(w=0., x=0., y=0., z=1.),
                translation=Displacement.from_xyz(x=5., y=0., z=0.),
            ),
        ]
        source = self.make_result()
        source.aligned = True
        source.transformation_history = [
            CalibrationTransform.from_transform(operation=operation, transform=transform)
            for operation, transform in zip(
                (CalibrationTransformType.PERSON, CalibrationTransformType.MANUAL),
                transforms,
            )
        ]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "calibration.toml"
            source.save_toml(path)
            loaded = CalibrationResult.load_toml(path)
        self.assertEqual(loaded.transformation_history, source.transformation_history)
        original = Point.from_prevalidated_array(array=np.array([1., 2., 3.]))
        point = original
        for entry in loaded.transformation_history:
            point = entry.to_transform().apply(points=point)
        np.testing.assert_allclose(point.array, [-6., -22., 33.])
        for entry in reversed(loaded.transformation_history):
            point = entry.to_transform().inverse().apply(points=point)
        np.testing.assert_allclose(point.array, original.array)

    def test_invalid_history_and_alignment_metadata_are_rejected(self) -> None:
        from freemocap.core.tasks.calibration.shared.calibration_transform import (
            CalibrationTransform, CalibrationTransformType,
        )
        from skellyforge.core.math.geometry.transform_math import Transform

        for quaternion in ((0., 0., 0., 0.), (2., 0., 0., 0.)):
            with self.subTest(quaternion=quaternion), self.assertRaises(ValidationError):
                CalibrationTransform(
                    operation=CalibrationTransformType.MANUAL,
                    quaternion_wxyz=quaternion,
                    translation_mm=(0., 0., 0.),
                )
        source = self.make_result()
        source.transformation_history = [
            CalibrationTransform.from_transform(
                operation=CalibrationTransformType.MANUAL,
                transform=Transform.identity(),
            ),
        ]
        with self.assertRaises(ValidationError):
            source.to_metadata()

    def test_runtime_transform_preserves_source_alignment_metadata(self) -> None:
        from freemocap.core.reconstruction.reference_transform import ReferenceTransform
        from freemocap.core.tasks.calibration.shared.calibration_state import CalibrationStateTracker

        source = self.make_result()
        source.aligned = True
        source.alignment_method = CalibrationAlignmentMethod.CHARUCO
        tracker = CalibrationStateTracker()
        tracker.set_reference_transform(reference_transform=ReferenceTransform(
            matrix=(1., 0., 0., 10., 0., 1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1.),
        ))
        transformed = tracker._transform_source(calibration=source)
        self.assertEqual(transformed.to_metadata(), source.to_metadata())
        self.assertEqual(transformed.transformation_history, [])

    def test_http_loading_uses_shared_content_and_reports_file_errors(self) -> None:
        from unittest.mock import patch

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from freemocap.api.http.calibration import calibration_router as calibration_api
        from freemocap.api.http.playback.playback_router import playback_router
        from freemocap.core.recording.recording_access import RecordingAccess
        from freemocap.core.tasks.calibration.shared.calibration_paths import create_camera_calibration_file_name
        from freemocap.core.tasks.calibration.shared.loaded_calibration import LoadedCalibration

        app = FastAPI()
        app.state.recording_access = RecordingAccess()
        app.include_router(calibration_api.calibration_router)
        app.include_router(playback_router)
        with TemporaryDirectory() as directory:
            recording = Path(directory) / "sample"
            recording.mkdir()
            path = recording / create_camera_calibration_file_name(recording.name)
            source = self.make_result()
            source.aligned = True
            source.save_toml(path)
            expected = LoadedCalibration.from_path(path).model_dump(mode="json", by_alias=True)

            with patch.object(calibration_api, "get_last_successful_calibration_toml_path", return_value=path):
                with TestClient(app) as client:
                    requests = [
                        ("/calibration/most-recent", {}),
                        ("/calibration/content", {"path": str(path)}),
                        ("/playback/sample/calibration", {"recording_parent_directory": directory}),
                    ]
                    for endpoint, params in requests:
                        with self.subTest(endpoint=endpoint):
                            response = client.get(endpoint, params=params)
                            self.assertEqual(response.status_code, 200, response.text)
                            self.assertEqual(response.json(), expected)
                            self.assertTrue(response.json()["metadata"]["aligned"])
                            self.assertIsNone(response.json()["metadata"]["alignment_method"])
                            self.assertEqual(len(response.json()["cameras"]), 1)

                    for invalid_content in (b"invalid = [", b"\xff"):
                        path.write_bytes(invalid_content)
                        for endpoint, params in requests:
                            with self.subTest(endpoint=endpoint, invalid_content=invalid_content):
                                response = client.get(endpoint, params=params)
                                self.assertEqual(response.status_code, 422, response.text)

                    path.unlink()
                    response = client.get("/calibration/most-recent")
                    self.assertEqual(response.status_code, 200)
                    self.assertIsNone(response.json())
                    for endpoint, params in requests[1:]:
                        with self.subTest(missing=endpoint):
                            response = client.get(endpoint, params=params)
                            self.assertEqual(response.status_code, 404, response.text)

    def make_result(self) -> CalibrationResult:
        return CalibrationResult(
            cameras=[CameraModel(
                id="camera", index=0, image_size=(1280, 720),
                intrinsics=CameraIntrinsics.from_image_size(width=1280, height=720),
                extrinsics=CameraExtrinsics.identity(),
            )],
            board=CharucoBoardDefinition(
                squares_x=5, squares_y=3, square_length_mm=50,
                marker_length_ratio=0.65,
            ),
            reprojection_error_px=0.4,
            initial_cost=12.0, final_cost=3.0, n_iterations=7,
            time_seconds=2.5, n_observations_used=100,
            n_observations_rejected=4,
        )

    def test_provenance_and_numerical_metadata_round_trip(self) -> None:
        source = self.make_result()
        source.solver_method = CalibrationSolverMethod.ANIPOSE
        source.recording_info = RecordingInfo(
            recording_name="calibration", recording_directory="recordings",
        )
        source.aligned = True
        source.alignment_method = CalibrationAlignmentMethod.CHARUCO
        source.alignment_recording_id = source.recording_info.recording_name
        source.alignment_result = GroundPlaneResult(
            origin=np.array([1.0, 2.0, 3.0]),
            rotation_matrix=np.eye(3),
            method=CalibrationAlignmentMethod.CHARUCO,
        )
        with TemporaryDirectory() as directory:
            path = Path(directory) / "calibration.toml"
            source.save_toml(path)
            loaded = CalibrationResult.load_toml(path)
        self.assertEqual(source.to_metadata(), loaded.to_metadata())
        self.assertEqual(source.cameras, loaded.cameras)
        metadata = loaded.to_metadata()
        self.assertEqual(
            CalibrationMetadata.model_validate_json(metadata.model_dump_json(round_trip=True)),
            metadata,
        )
        CalibrationMetadata.model_json_schema()

    def test_legacy_marker_size_and_unknown_provenance(self) -> None:
        source = self.make_result()
        source.aligned = True
        with TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.toml"
            source.save_toml(path)
            document = tomllib.loads(path.read_text(encoding="utf-8"))
            document["metadata"]["groundplane_applied"] = document["metadata"].pop("aligned")
            document["metadata"].pop("transformation_history")
            board = document["metadata"]["board"]
            board["marker_length_mm"] = board.pop("marker_length_ratio") * board["square_length_mm"]
            path.write_text(tomli_w.dumps(document), encoding="utf-8")
            loaded = CalibrationResult.load_toml(path)
        self.assertAlmostEqual(loaded.board.marker_length_ratio, 0.65)
        self.assertTrue(loaded.aligned)
        self.assertIsNone(loaded.alignment_method)
        self.assertEqual(loaded.transformation_history, [])
        self.assertIsNone(loaded.solver_method)
        self.assertIsNone(loaded.recording_info)

    def test_invalid_groundplane_geometry_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            GroundPlaneResult(
                origin=[float("nan"), 0.0, 0.0],
                rotation_matrix=np.eye(3),
                method=CalibrationAlignmentMethod.CHARUCO,
            )

    def test_legacy_dictionary_and_camera_fields(self) -> None:
        source = self.make_result()
        document = CalibrationToml.from_calibration(
            cameras=source.cameras, metadata=source.to_metadata(),
        ).model_dump(mode="json", by_alias=True, exclude_none=True, round_trip=True)
        document["metadata"]["board"].pop("aruco_dictionary_enum")
        document["metadata"]["board"]["marker_bits"] = 5
        document["metadata"]["board"]["dict_size"] = 100
        camera = document["camera"]
        camera["image_size"] = camera.pop("size")
        camera.pop("id")
        camera.pop("index")
        camera.pop("world_position")
        camera.pop("world_orientation")
        camera["translation"] = [10.0, 20.0, 30.0]
        parsed = CalibrationToml.model_validate(document)
        loaded = parsed.to_cameras()[0]
        self.assertEqual(parsed.metadata.board.aruco_dictionary_enum, cv2.aruco.DICT_5X5_100)
        self.assertEqual(loaded.id, "camera")
        self.assertEqual(loaded.index, 0)
        np.testing.assert_allclose(loaded.world_position, [-10.0, -20.0, -30.0])
        np.testing.assert_allclose(loaded.world_orientation, np.eye(3))

    def test_file_without_metadata_retains_legacy_defaults(self) -> None:
        source = self.make_result()
        document = CalibrationToml.from_calibration(
            cameras=source.cameras, metadata=source.to_metadata(),
        ).model_dump(mode="json", by_alias=True, exclude_none=True, round_trip=True)
        document.pop("metadata")
        parsed = CalibrationToml.model_validate(document)
        self.assertIs(type(parsed.metadata), CalibrationMetadata)
        self.assertIs(type(parsed.metadata.board), CharucoBoardDefinition)
        self.assertEqual(parsed.metadata.board.squares_x, 7)
        self.assertEqual(parsed.metadata.board.squares_y, 5)
        self.assertEqual(parsed.metadata.board.square_length_mm, 1.0)
        self.assertIsNone(parsed.metadata.alignment_method)
        self.assertFalse(parsed.metadata.aligned)

    def test_malformed_camera_table_is_rejected(self) -> None:
        source = self.make_result()
        document = CalibrationToml.from_calibration(
            cameras=source.cameras, metadata=source.to_metadata(),
        ).model_dump(mode="json", by_alias=True, exclude_none=True, round_trip=True)
        document["camera"]["matrix"] = [[1.0, 0.0]]
        with self.assertRaises(ValidationError):
            CalibrationToml.model_validate(document)

    def test_duplicate_camera_ids_are_rejected_before_saving(self) -> None:
        source = self.make_result()
        with self.assertRaises(ValueError):
            CalibrationToml.from_calibration(
                cameras=source.cameras * 2, metadata=source.to_metadata(),
            )

    def test_configured_board_is_preserved(self) -> None:
        from freemocap.core.tasks.calibration.calibration_task_config import PosthocCalibrationPipelineConfig
        from freemocap.core.tasks.calibration.posthoc_calibration_task import _create_board

        board = CharucoBoardDefinition(
            squares_x=5, squares_y=3, square_length_mm=42,
            marker_length_ratio=0.65,
            aruco_dictionary_enum=cv2.aruco.DICT_5X5_100,
        )
        copied = _create_board(PosthocCalibrationPipelineConfig(charuco_board=board))
        self.assertEqual(copied, board)
        self.assertIsNot(copied, board)
