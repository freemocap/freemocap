import cv2
import numpy as np
from numpydantic import NDArray, Shape
from pydantic import BaseModel

from freemocap.core.pipeline.tasks.calibration_task.calibration_helpers.calibration_numpy_types import \
    TransformationMatrixArray, TranslationVectorArray, RotationVectorArray


class Positional6DoF(BaseModel):
    translation: TranslationVectorArray= np.zeros(3)
    rotation: RotationVectorArray = np.zeros(3)

    @property
    def transformation_matrix(self) -> TransformationMatrixArray:
        return self.get_transformation_matrix()

    def get_transformation_matrix(self, return_jacobian:bool=False) -> TransformationMatrixArray | tuple[TransformationMatrixArray, NDArray[Shape['3, 9'], np.float32]]:
        """
        Returns the transformation matrix for this 6DoF pose in the form of a 4x4 matrix (homogeneous coordinates)
        the left upper 3x3 matrix is the rotation matrix, and the rightmost column is the translation vector.
        the bottom row is [0, 0, 0, 1] (where the 1 is the homogeneous coordinate, which makes the matrix invertible and provides the scale factor for the translation vector to put it in spatial coordinates)
        """

        transformation_matrix = np.zeros((4, 4))

        transformation_matrix[:3, :3], jacobian = cv2.Rodrigues(self.rotation)
        transformation_matrix[:3, 3] = self.translation.flatten()
        transformation_matrix[3, 3] = 1
        if return_jacobian:
            return transformation_matrix, jacobian
        return transformation_matrix


if __name__ == "__main__":
    positional_6dof = Positional6DoF()
    print(positional_6dof.transformation_matrix)
    print(positional_6dof.model_dump_json(indent=2))