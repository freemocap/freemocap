"""Sparse board observations are normal; a camera with no usable frames is actionable."""

from typing import Any
from unittest import TestCase
from unittest.mock import patch

import numpy as np
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition

from freemocap.core.tasks.calibration.anipose_calibration.helpers import bundle_adjust
from freemocap.core.tasks.calibration.shared.camera_model import CameraModel
from freemocap.core.tasks.calibration.shared.camera_intrinsics import CameraIntrinsics
from freemocap.core.tasks.calibration.shared.camera_extrinsics import CameraExtrinsics


class CalibrationDiagnosticsTests(TestCase):
    def setUp(self) -> None:
        self.board = CharucoBoardDefinition(squares_x=5, squares_y=3, square_length_mm=50.0)
        self.camera = CameraModel(
            id="test-camera", index=0, image_size=(640, 480),
            intrinsics=CameraIntrinsics(fx=640.0, fy=640.0, cx=320.0, cy=240.0),
            extrinsics=CameraExtrinsics(quaternion_wxyz=[1.0, 0.0, 0.0, 0.0], translation=[0.0, 0.0, 0.0]),
        )

    @staticmethod
    def observation(corners: int) -> dict[str, Any]:
        return {
            "corners": np.zeros((corners, 1, 2), dtype=np.float32),
            "ids": np.arange(corners, dtype=np.int32).reshape(-1, 1),
        }

    def test_no_usable_frames_reports_camera_and_counts(self) -> None:
        with self.assertRaises(ValueError) as raised:
            bundle_adjust.calibrate_cameras_from_rows(
                cameras=[self.camera], board=self.board,
                all_rows=[[self.observation(corners=count) for count in (0, 3, 6)]],
            )
        message = str(raised.exception)
        for detail in ("test-camera", "0 of 3", "2 frames contain corners", "maximum corners in a frame: 6", "Playback"):
            self.assertIn(detail, message)

    def test_sparse_frames_do_not_prevent_intrinsic_initialization(self) -> None:
        with (
            patch.object(bundle_adjust.cv2, "initCameraMatrix2D", return_value=np.eye(3)) as initialize,
            patch.object(bundle_adjust.charuco_board_ops, "estimate_pose_rows", side_effect=RuntimeError("pose-stage reached")),
            self.assertRaisesRegex(RuntimeError, "pose-stage reached"),
        ):
            bundle_adjust.calibrate_cameras_from_rows(
                cameras=[self.camera], board=self.board,
                all_rows=[[self.observation(corners=count) for count in (0, 3, 7)]],
            )
        initialize.assert_called_once()
        self.assertEqual(len(initialize.call_args.args[0]), 1)
        self.assertEqual(len(initialize.call_args.args[0][0]), 7)
