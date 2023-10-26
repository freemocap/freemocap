import logging
from typing import List, Union
from typing import TYPE_CHECKING

import numpy as np

from ajc_freemocap_blender_addon.data_models.freemocap_data.freemocap_data_model import FREEMOCAP_DATA_COMPONENT_TYPES

logger = logging.getLogger(__name__)

# this allows us to import the `FreemocapDataHandler` class for type hinting without causing a circular import
if TYPE_CHECKING:
    from ajc_freemocap_blender_addon.core_functions.freemocap_data_handler.handler import \
        FreemocapDataHandler


class FreemocapDataTransformer:
    def __init__(self, handler: "FreemocapDataHandler"):
        self.handler = handler

    def apply_rotations(self,
                        rotation_matricies: List[np.ndarray],
                        component_name: str = None):
        if not len(rotation_matricies) == self.handler.number_of_frames:
            raise ValueError(
                f"Number of rotation matricies ({len(rotation_matricies)})"
                f" does not match number of frames ({self.handler.number_of_frames}).")

        for rotation_matrix in rotation_matricies:
            self.apply_rotation(rotation_matrix=rotation_matrix,
                                component_name=component_name)

    def apply_rotation(self,
                       rotation_matrix: Union[np.ndarray, List[List[float]]],
                       component_name: str = None):

        if isinstance(rotation_matrix, list) or isinstance(rotation_matrix, tuple):
            rotation_matrix = np.array(rotation_matrix)

        if rotation_matrix.shape != (3, 3):
            raise ValueError(f"Rotation matrix must be a 3x3 matrix. Got {rotation_matrix.shape} instead.")

        logger.info(f"Applying rotation matrix {rotation_matrix}")
        if component_name == "body" or component_name is None:
            self.handler.body_frame_name_xyz = self._rotate_component(self.handler.body_frame_name_xyz, rotation_matrix)

        if component_name == "right_hand" or component_name is None:
            self.handler.right_hand_frame_name_xyz = self._rotate_component(self.handler.right_hand_frame_name_xyz,
                                                                            rotation_matrix)

        if component_name == "left_hand" or component_name is None:
            self.handler.left_hand_frame_name_xyz = self._rotate_component(self.handler.left_hand_frame_name_xyz,
                                                                           rotation_matrix)

        if component_name == "face" or component_name is None:
            self.handler.face_frame_name_xyz = self._rotate_component(self.handler.face_frame_name_xyz, rotation_matrix)

        if component_name == "other" or component_name is None:
            for name, other_component in self.handler.freemocap_data.other.items():
                other_component.data = self._rotate_component(other_component.data, rotation_matrix)

    def _rotate_component(self,
                          data_frame_name_xyz: Union[np.ndarray, List[float]],
                          rotation_matrix: Union[np.ndarray, List[List[float]]]) -> np.ndarray:
        if isinstance(data_frame_name_xyz, list):
            data_frame_name_xyz = np.array(data_frame_name_xyz)
        if isinstance(rotation_matrix, list):
            rotation_matrix = np.array(rotation_matrix)

        if rotation_matrix.shape != (3, 3):
            raise ValueError(f"Rotation matrix must be a 3x3 matrix. Got {rotation_matrix.shape} instead.")

        if data_frame_name_xyz.shape[-1] == 2:
            logger.info(f"2D data detected. Adding a third dimension with zeros.")
            data_frame_name_xyz = np.concatenate(
                [data_frame_name_xyz, np.zeros((data_frame_name_xyz.shape[0], data_frame_name_xyz.shape[1], 1))],
                axis=2)

        rotated_data_frame_name_xyz = np.zeros(data_frame_name_xyz.shape)
        for frame_number in range(data_frame_name_xyz.shape[0]):
            if len(data_frame_name_xyz.shape) == 2:
                rotated_data_frame_name_xyz[frame_number, :] = rotation_matrix @ data_frame_name_xyz[frame_number, :]
            elif len(data_frame_name_xyz.shape) == 3:
                for trajectory_number in range(data_frame_name_xyz.shape[1]):
                    rotated_data_frame_name_xyz[frame_number, trajectory_number,
                    :] = rotation_matrix @ data_frame_name_xyz[
                                           frame_number,
                                           trajectory_number,
                                           :]
        return rotated_data_frame_name_xyz

    def apply_translations(self,
                           vectors: Union[List[np.ndarray], List[List[float]]],
                           component_name: str = None):
        if not len(vectors) == self.handler.number_of_frames:
            raise ValueError(
                f"Number of vectors ({len(vectors)}) does not match number of frames ({self.handler.number_of_frames}).")
        for frame_number, vector in enumerate(vectors):
            self.apply_translation(vector=vector,
                                   component_name=component_name,
                                   frame_number=frame_number)

    def apply_translation(self,
                          vector: Union[np.ndarray, List[float]],
                          component_name: FREEMOCAP_DATA_COMPONENT_TYPES = None,
                          frame_number: int = None):

        logger.info(f"Translating by vector {vector}")
        if isinstance(vector, list):
            vector = np.array(vector)
        if vector.shape != (3,):
            raise ValueError(f"Vector must be a 3D vector. Got {vector.shape} instead.")

        if component_name == "body" or component_name is None:
            self.handler.body_frame_name_xyz = self._translate_component_data(data=self.handler.body_frame_name_xyz,
                                                                              translation=vector,
                                                                              frame_number=frame_number)
        if component_name == "right_hand" or component_name is None:
            self.handler.right_hand_frame_name_xyz = self._translate_component_data(
                data=self.handler.right_hand_frame_name_xyz,
                translation=vector,
                frame_number=frame_number)

        if component_name == "left_hand" or component_name is None:
            self.handler.left_hand_frame_name_xyz = self._translate_component_data(
                data=self.handler.left_hand_frame_name_xyz,
                translation=vector,
                frame_number=frame_number)

        if component_name == "face" or component_name is None:
            self.handler.face_frame_name_xyz = self._translate_component_data(data=self.handler.face_frame_name_xyz,
                                                                              translation=vector,
                                                                              frame_number=frame_number
                                                                              )
        if component_name == "other" or component_name is None:
            for name, other_component in self.handler.freemocap_data.other.items():
                self._translate_component_data(data=other_component.data,
                                               translation=vector,
                                               frame_number=frame_number
                                               )

    def _translate_component_data(self,
                                  data: np.ndarray,
                                  translation: np.ndarray,
                                  frame_number: int = None) -> np.ndarray:
        if not len(data.shape) in [2, 3]:
            raise ValueError(f"Component data must have 2 or 3 dimensions. Got {data.shape[2]} instead.")
        if not translation.shape == (3,):
            raise ValueError(f"Translation vector must be a 3D vector. Got {translation.shape} instead.")

        if frame_number is None:
            # translate all frames
            if len(data.shape) == 2:
                data[:, 0] += translation[0]
                data[:, 1] += translation[1]
                data[:, 2] += translation[2]
            elif len(data.shape) == 3:
                data[:, :, 0] += translation[0]
                data[:, :, 1] += translation[1]
                data[:, :, 2] += translation[2]
        else:
            # translate specified frame only
            if len(data.shape) == 2:
                data[frame_number, 0] += translation[0]
                data[frame_number, 1] += translation[1]
                data[frame_number, 2] += translation[2]
            elif len(data.shape) == 3:
                data[frame_number, :, 0] += translation[0]
                data[frame_number, :, 1] += translation[1]
                data[frame_number, :, 2] += translation[2]

        return data

    def apply_scale(self,
                    scale: float,
                    component_name: FREEMOCAP_DATA_COMPONENT_TYPES = None):
        logger.info(f"Applying scale {scale}")
        if component_name == "body" or component_name is None:
            self.handler.body_frame_name_xyz *= scale
        if component_name == "right_hand" or component_name is None:
            self.handler.right_hand_frame_name_xyz *= scale
        if component_name == "left_hand" or component_name is None:
            self.handler.left_hand_frame_name_xyz *= scale
        if component_name == "face" or component_name is None:
            self.handler.face_frame_name_xyz *= scale
        if component_name == "other" or component_name is None:
            for other_component in self.handler.freemocap_data.other:
                other_component.data_frame_name_xyz *= scale
