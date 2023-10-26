import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Union

logger = logging.getLogger(__name__)


@dataclass
class FreemocapDataPaths:
    body_npy: str
    right_hand_npy: str
    left_hand_npy: str
    face_npy: str
    center_of_mass_npy: str
    segment_centers_of_mass_npy: str
    reprojection_error_npy: str

    @classmethod
    def from_recording_folder(cls, path: str):
        recording_path = Path(path)
        output_data_path = recording_path / "output_data"
        return cls(
            body_npy=str(output_data_path / "mediapipe_body_3d_xyz.npy"),
            right_hand_npy=str(output_data_path / "mediapipe_right_hand_3d_xyz.npy"),
            left_hand_npy=str(output_data_path / "mediapipe_left_hand_3d_xyz.npy"),
            face_npy=str(output_data_path / "mediapipe_face_3d_xyz.npy"),

            center_of_mass_npy=str(output_data_path / "center_of_mass" / "total_body_center_of_mass_xyz.npy"),
            segment_centers_of_mass_npy=str(output_data_path / "center_of_mass" / "segmentCOM_frame_joint_xyz.npy"),

            reprojection_error_npy=str(
                output_data_path / "raw_data" / "mediapipe3dData_numFrames_numTrackedPoints_reprojectionError.npy"),
        )

    @staticmethod
    def _validate_recording_path(recording_path: Union[str, Path]):
        if recording_path == "":
            logger.error("No recording path specified")
            raise FileNotFoundError("No recording path specified")

        if not Path(recording_path).exists():
            logger.error(f"Recording path {recording_path} does not exist")
            raise FileNotFoundError(f"Recording path {recording_path} does not exist")

    def __post_init__(self):
        for path in self.__dict__.values():
            if not Path(path).exists():
                logger.error(f"Path {path} does not exist")
                raise FileNotFoundError(f"Path {path} does not exist")
