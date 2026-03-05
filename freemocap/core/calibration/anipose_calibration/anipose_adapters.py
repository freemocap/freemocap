"""Adapter functions between shared Pydantic models and anipose-specific types.

These let the anipose solver keep its internal AniposeCameraGroup/AniposeCamera
classes while the rest of the system speaks CameraModel/CalibrationResult.
"""
from freemocap.core.calibration.anipose_calibration.helpers.freemocap_anipose import AniposeCharucoBoard, \
    AniposeCameraGroup, AniposeCamera
from freemocap.core.calibration.shared.calibration_models import CharucoBoardDefinition, CameraModel, CameraIntrinsics, \
    CameraExtrinsics


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
        marker_length=board.marker_length_mm,
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
            camera_matrix=ac.get_camera_matrix(),
            dist_coeffs=ac.get_distortions(),
        )

        extrinsics = CameraExtrinsics.from_rodrigues(
            rvec=ac.get_rotation(),
            tvec=ac.get_translation(),
        )

        size = ac.get_size()
        if size is None:
            raise ValueError(f"AniposeCamera '{ac.get_name()}' has no image size set")

        cameras.append(
            CameraModel(
                name=ac.get_name(),
                image_size=(int(size[0]), int(size[1])),
                intrinsics=intrinsics,
                extrinsics=extrinsics,
            )
        )

    return cameras
