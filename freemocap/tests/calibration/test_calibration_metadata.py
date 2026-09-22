"""Calibration metadata survives disk and JSON serialization."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
import tomllib

import numpy as np
import tomli_w
from pydantic import ValidationError
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition

from freemocap.core.tasks.calibration.calibration_task_config import CalibrationSolverMethod
from freemocap.core.tasks.calibration.shared.calibration_metadata import CalibrationMetadata
from freemocap.core.tasks.calibration.shared.calibration_result import CalibrationResult
from freemocap.core.tasks.calibration.shared.camera_model import CameraModel
from freemocap.core.tasks.calibration.shared.camera_intrinsics import CameraIntrinsics
from freemocap.core.tasks.calibration.shared.camera_extrinsics import CameraExtrinsics
from freemocap.core.tasks.calibration.shared.groundplane_alignment import (
    CalibrationAlignmentMethod,
    GroundPlaneResult,
)


class CalibrationMetadataTests(TestCase):
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
        source.groundplane_aligned = True
        source.groundplane_method = CalibrationAlignmentMethod.CHARUCO
        source.groundplane_recording_id = source.recording_info.recording_name
        source.groundplane_result = GroundPlaneResult(
            origin=np.array([1.0, 2.0, 3.0]),
            rotation_matrix=np.eye(3),
            method=CalibrationAlignmentMethod.CHARUCO,
        )
        with TemporaryDirectory() as directory:
            path = Path(directory) / "calibration.toml"
            source.dump_anipose_toml(path)
            loaded = CalibrationResult.load_anipose_toml(path)
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
        source.groundplane_aligned = True
        with TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.toml"
            source.dump_anipose_toml(path)
            document = tomllib.loads(path.read_text(encoding="utf-8"))
            board = document["metadata"]["board"]
            board["marker_length_mm"] = board.pop("marker_length_ratio") * board["square_length_mm"]
            path.write_text(tomli_w.dumps(document), encoding="utf-8")
            loaded = CalibrationResult.load_anipose_toml(path)
        self.assertAlmostEqual(loaded.board.marker_length_ratio, 0.65)
        self.assertTrue(loaded.groundplane_aligned)
        self.assertIsNone(loaded.groundplane_method)
        self.assertIsNone(loaded.solver_method)
        self.assertIsNone(loaded.recording_info)

    def test_invalid_groundplane_geometry_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            GroundPlaneResult(
                origin=[float("nan"), 0.0, 0.0],
                rotation_matrix=np.eye(3),
                method=CalibrationAlignmentMethod.CHARUCO,
            )
