"""Adapter functions between shared Pydantic models and anipose-specific types.

These let the anipose solver keep its internal AniposeCameraGroup/AniposeCamera
classes while the rest of the system speaks CameraModel/CalibrationResult.
"""
import numpy as np
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation

from freemocap.core.tasks.calibration.anipose_calibration.helpers.anipose_camera import AniposeCamera
from freemocap.core.tasks.calibration.anipose_calibration.helpers.anipose_camera_group import AniposeCameraGroup
from freemocap.core.tasks.calibration.anipose_calibration.helpers.anipose_charuco_board import AniposeCharucoBoard
from freemocap.core.tasks.calibration.shared.calibration_models import (
    CharucoBoardDefinition,
    CameraModel,
    CameraIntrinsics,
    CameraExtrinsics,
    CharucoCornersObservation,
    CornerObservation,
)


def charuco_observation_to_corners_observation(
    obs: CharucoObservation,
    camera_name: str,
) -> CharucoCornersObservation:
    """Convert a skellytracker CharucoObservation to the shared CharucoCornersObservation."""
    if obs.charuco_empty or obs.detected_charuco_corner_ids is None:
        return CharucoCornersObservation(camera_name=camera_name, frame_index=obs.frame_number, corners=[])

    corners = []
    for cid, xy in zip(
        obs.detected_charuco_corner_ids.ravel(),
        obs.detected_charuco_corners_image_coordinates,
    ):
        corners.append(CornerObservation(corner_id=int(cid), pixel_xy=xy.ravel()[:2]))

    return CharucoCornersObservation(camera_name=camera_name, frame_index=obs.frame_number, corners=corners)


def charuco_corners_observation_to_anipose_row(
    obs: CharucoCornersObservation,
    n_corners: int,
) -> dict:
    """Convert a CharucoCornersObservation to the anipose row dict format expected by calibrate_rows()."""
    filled = np.full((n_corners, 1, 2), np.nan, dtype=np.float64)
    for corner in obs.corners:
        filled[corner.corner_id, 0, :] = corner.pixel_xy

    if obs.corners:
        corners = np.array([c.pixel_xy for c in obs.corners], dtype=np.float64).reshape(-1, 1, 2)
        ids = np.array([c.corner_id for c in obs.corners], dtype=np.int32).reshape(-1, 1)
    else:
        corners = np.empty((0, 1, 2), dtype=np.float64)
        ids = np.empty((0, 1), dtype=np.int32)

    return {"framenum": (0, obs.frame_index), "corners": corners, "ids": ids, "filled": filled}


def calibrate_rows_from_board_definition(
    camera_group: AniposeCameraGroup,
    all_rows: list,
    board: CharucoBoardDefinition,
    init_intrinsics: bool = True,
    init_extrinsics: bool = True,
    verbose: bool = True,
) -> tuple:
    """Run calibrate_rows using a CharucoBoardDefinition. Creates AniposeCharucoBoard internally."""
    anipose_board = create_anipose_board(board)
    return camera_group.calibrate_rows(
        all_rows,
        anipose_board,
        init_intrinsics=init_intrinsics,
        init_extrinsics=init_extrinsics,
        verbose=verbose,
    )


def create_anipose_board(board: CharucoBoardDefinition) -> AniposeCharucoBoard:
    """Create an AniposeCharucoBoard from the shared board definition.

    The anipose solver needs AniposeCharucoBoard because it inherits
    detect_image / estimate_pose_rows / get_all_calibration_points
    from aniposelib.boards.CharucoBoard.
    """
    return AniposeCharucoBoard(
        squaresX=board.squares_x,
        squaresY=board.squares_y,
        square_length=board.square_length_mm,
        marker_length=board.aruco_marker_length_mm,
        marker_bits=board.marker_bits,
        dict_size=board.dict_size,
    )


def camera_models_to_anipose_group(cameras: list[CameraModel]) -> AniposeCameraGroup:
    """Build an AniposeCameraGroup from unified CameraModel objects.

    Used when downstream code (e.g. triangulation) requires the anipose API.
    """
    anipose_cameras: list[AniposeCamera] = []
    for cam in cameras:
        ac = AniposeCamera(
            matrix=cam.intrinsics.to_camera_matrix(),
            dist=cam.intrinsics.to_dist_coeffs_5(),
            size=cam.image_size,
            rvec=cam.extrinsics.rodrigues_vector,
            tvec=cam.extrinsics.translation,
            name=cam.name,
            world_orientation=cam.extrinsics.world_orientation,
            world_position=cam.extrinsics.world_position,
        )
        anipose_cameras.append(ac)

    return AniposeCameraGroup(cameras=anipose_cameras)


def anipose_group_to_camera_models(group: AniposeCameraGroup) -> list[CameraModel]:
    """Extract a list of CameraModel from an AniposeCameraGroup.

    Used after anipose calibration completes to produce a CalibrationResult.
    """
    cameras: list[CameraModel] = []
    for ac in group.cameras:
        intrinsics = CameraIntrinsics.from_camera_matrix_and_dist(
            camera_matrix=ac.camera_matrix,
            dist_coeffs=ac.distortion_coefficients,
        )

        extrinsics = CameraExtrinsics.from_rodrigues(
            rvec=ac.rotation_vector,
            tvec=ac.translation_vector,
        )

        size = ac.size
        if size is None:
            raise ValueError(f"AniposeCamera '{ac.id}' has no image size set")

        cameras.append(
            CameraModel(
                id=ac.id,
                image_size=(int(size[0]), int(size[1])),
                intrinsics=intrinsics,
                extrinsics=extrinsics,
            )
        )

    return cameras
