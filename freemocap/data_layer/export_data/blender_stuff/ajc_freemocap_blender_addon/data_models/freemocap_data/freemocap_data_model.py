import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union, Literal

import numpy as np

from ajc_freemocap_blender_addon.data_models.freemocap_data.helpers.freemocap_component_data import FreemocapComponentData
from ajc_freemocap_blender_addon.data_models.freemocap_data.helpers.freemocap_data_paths import FreemocapDataPaths
from ajc_freemocap_blender_addon.data_models.freemocap_data.helpers.freemocap_data_stats import FreemocapDataStats
from ajc_freemocap_blender_addon.data_models.mediapipe_names.mediapipe_trajectory_names import MediapipeTrajectoryNames, \
    HumanTrajectoryNames

logger = logging.getLogger(__name__)

FREEMOCAP_DATA_COMPONENT_TYPES = Literal["body", "right_hand", "left_hand", "face", "other"]


@dataclass
class FreemocapData:
    body: FreemocapComponentData
    hands: Dict[str, FreemocapComponentData]
    face: FreemocapComponentData
    other: Optional[Dict[str, FreemocapComponentData]]
    metadata: Optional[Dict[Any, Any]]

    @classmethod
    def from_data(cls,
                  body_frame_name_xyz: np.ndarray,
                  right_hand_frame_name_xyz: np.ndarray,
                  left_hand_frame_name_xyz: np.ndarray,
                  face_frame_name_xyz: np.ndarray,
                  error: np.ndarray,
                  data_source: str = "mediapipe",
                  error_type: str = "mean_reprojection_error",
                  other: Optional[Dict[str, Union[FreemocapComponentData, Dict[str, Any]]]] = None,
                  metadata: Dict[Any, Any] = None) -> "FreemocapData":

        if not data_source == "mediapipe":
            raise NotImplementedError(
                f"Data source `{data_source}` not recognized - create the equivalent of `MediapipeTrajectoryNames` for this data source")
        else:
            trajectory_names = MediapipeTrajectoryNames()
        if metadata is None:
            metadata = {}

        if other is None:
            other = {}

        cls._convert_to_component(other=other)

        (body_error,
         face_error,
         left_hand_error,
         right_hand_error) = cls._split_up_reprojection_error(error=error,
                                                              trajectory_names=trajectory_names)

        return cls(
            body=FreemocapComponentData(name="body",
                                        data=body_frame_name_xyz,
                                        data_source=data_source,
                                        trajectory_names=trajectory_names.body,
                                        error=body_error,
                                        error_type=error_type),

            hands={"right": FreemocapComponentData(name="right_hand",
                                                   data=right_hand_frame_name_xyz,
                                                   data_source=data_source,
                                                   trajectory_names=trajectory_names.right_hand,
                                                   error=right_hand_error,
                                                   error_type=error_type),
                   "left": FreemocapComponentData(name="left_hand",
                                                  data=left_hand_frame_name_xyz,
                                                  data_source=data_source,
                                                  trajectory_names=trajectory_names.left_hand,
                                                  error=left_hand_error,
                                                  error_type=error_type)},
            face=FreemocapComponentData(name="face",
                                        data=face_frame_name_xyz,
                                        data_source=data_source,
                                        trajectory_names=trajectory_names.face,
                                        error=face_error,
                                        error_type=error_type),
            other=other,
            metadata=metadata,
        )

    @classmethod
    def _convert_to_component(cls, other: Dict[str, Union[FreemocapComponentData, Dict[str, Any]]]):
        for name, component in other.items():
            if isinstance(component, FreemocapComponentData):
                pass
            elif isinstance(component, dict):
                if not "component_name" in component.keys():
                    component["component_name"] = name
                    try:
                        other[name] = FreemocapComponentData(**component)
                    except TypeError as e:
                        logger.error(f"Error creating FreemocapComponentData from dict {component}")
                        raise e
            else:
                raise ValueError(f"Component: {name} type not recognized (type: {type(component)}")
        return other

    @classmethod
    def _split_up_reprojection_error(cls,
                                     error: np.ndarray,
                                     trajectory_names: HumanTrajectoryNames):
        body_names = trajectory_names.body
        right_hand_names = trajectory_names.right_hand
        left_hand_names = trajectory_names.left_hand
        face_names = trajectory_names.face

        body_start = 0
        right_hand_start = len(body_names)
        left_hand_start = right_hand_start + len(right_hand_names)
        face_start = left_hand_start + len(left_hand_names)
        body_error = error[:, body_start:len(body_names)]
        right_hand_error = error[:, right_hand_start:right_hand_start + len(right_hand_names)]
        left_hand_error = error[:, left_hand_start:left_hand_start + len(left_hand_names)]
        face_error = error[:, face_start:face_start + len(face_names)]

        cls._validate_sliced_error(all_error=error,
                                   trajectory_names=trajectory_names,
                                   body_error=body_error,
                                   face_error=face_error,
                                   left_hand_error=left_hand_error,
                                   right_hand_error=right_hand_error)

        return body_error, face_error, left_hand_error, right_hand_error

    @classmethod
    def _validate_sliced_error(cls,
                               all_error: np.ndarray,
                               trajectory_names: HumanTrajectoryNames,
                               body_error: np.ndarray,
                               face_error: np.ndarray,
                               left_hand_error: np.ndarray,
                               right_hand_error: np.ndarray):

        body_names = trajectory_names.body
        right_hand_names = trajectory_names.right_hand
        left_hand_names = trajectory_names.left_hand
        face_names = trajectory_names.face

        if not body_error.shape[1] == len(body_names):
            raise ValueError(
                f"Body frame shape {body_error.shape} does not match trajectory names length {len(body_names)}")
        if not right_hand_error.shape[1] == len(right_hand_names):
            raise ValueError(
                f"Right hand frame shape {right_hand_error.shape} does not match trajectory names length {len(right_hand_names)}")
        if not left_hand_error.shape[1] == len(left_hand_names):
            raise ValueError(
                f"Left hand frame shape {left_hand_error.shape} does not match trajectory names length {len(left_hand_names)}")
        if not face_error.shape[1] == len(face_names):
            raise ValueError(
                f"Face frame shape {face_error.shape} does not match trajectory names length {len(face_names)}")
        if not body_error.shape[1] + right_hand_error.shape[1] + left_hand_error.shape[1] + face_error.shape[1] == \
               all_error.shape[1]:
            raise ValueError(
                f"Error frame shape {all_error.shape} does not match trajectory names length {len(body_names) + len(right_hand_names) + len(left_hand_names) + len(face_names)}")

    @classmethod
    def from_data_paths(cls,
                        data_paths: FreemocapDataPaths,
                        scale: float = 1000,
                        **kwargs):
        if "metadata" in kwargs.keys():
            metadata = kwargs["metadata"]
        else:
            metadata = {}

        return cls.from_data(
            body_frame_name_xyz=np.load(data_paths.body_npy) / scale,
            right_hand_frame_name_xyz=np.load(data_paths.right_hand_npy) / scale,
            left_hand_frame_name_xyz=np.load(data_paths.left_hand_npy) / scale,
            face_frame_name_xyz=np.load(data_paths.face_npy) / scale,
            error=np.load(data_paths.reprojection_error_npy),

            other={"center_of_mass": FreemocapComponentData(name="center_of_mass",
                                                            data=np.load(
                                                                data_paths.center_of_mass_npy) / scale,
                                                            data_source="freemocap",
                                                            trajectory_names=["center_of_mass"])},
            metadata=metadata,
        )

    @classmethod
    def from_recording_path(cls,
                            recording_path: str,
                            **kwargs):
        data_paths = FreemocapDataPaths.from_recording_folder(recording_path)
        metadata = {"recording_path": recording_path,
                    "data_paths": data_paths.__dict__}
        logger.info(f"Loading data from paths {data_paths}")
        return cls.from_data_paths(data_paths=data_paths, metadata=metadata, **kwargs)

    def __str__(self):
        return str(FreemocapDataStats.from_freemocap_data(self))


if __name__ == "__main__":
    from ajc_freemocap_blender_addon.core_functions.setup_scene.get_path_to_sample_data import get_path_to_sample_data

    recording_path_in = get_path_to_sample_data()
    freemocap_data = FreemocapData.from_recording_path(recording_path=recording_path_in,
                                                       type="original")
    print(str(freemocap_data))
