import cv2
import numpy as np
from numpydantic import NDArray, Shape
from pydantic import BaseModel, model_validator
from scipy.spatial.transform import Rotation as R

from freemocap.core.tasks.calibration_task.calibration_helpers.calibration_numpy_types import QuaternionArray, \
    RotationVectorArray, \
    RotationMatrixArray, TranslationVectorArray, CameraExtrinsicsMatrix, CameraDistortionCoefficientsArray, \
    CameraMatrixArray


def karcher_mean_quaternions(quaternions: list[QuaternionArray], tol=1e-9, max_iterations=100):
    # Normalize the quaternions to ensure they are unit quaternions

    quaternions = np.array([q / np.linalg.norm(q) for q in quaternions])

    # Start with an initial guess (the first quaternion)
    mean_quat = quaternions[0]

    for _ in range(max_iterations):
        # Compute the tangent vectors (logarithm map)
        errors = [R.from_quat(q).inv() * R.from_quat(mean_quat) for q in quaternions]
        errors = [e.as_rotvec() for e in errors]

        # Compute the average error vector
        mean_error = np.mean(errors, axis=0)

        # Check for convergence
        if np.linalg.norm(mean_error) < tol:
            break

        # Update the mean (exponential map)
        mean_rot = R.from_rotvec(mean_error) * R.from_quat(mean_quat)
        mean_quat = mean_rot.as_quat(canonical=False)

    return mean_quat


class RotationVector(BaseModel):
    vector: RotationVectorArray
    reference_frame: str

    @property
    def as_rotation_matrix(self) -> RotationMatrixArray:
        return cv2.Rodrigues(self.vector)[0]

    @property
    def as_quaternion(self) -> QuaternionArray:
        return R.from_matrix(self.as_rotation_matrix).as_quat(canonical=False)

    @classmethod
    def mean_from_rotation_vectors(cls, rotation_vectors: list["RotationVector"]) -> "RotationVector":
        if not all([rv.reference_frame == rotation_vectors[0].reference_frame for rv in rotation_vectors]):
            raise ValueError("All rotation vectors must have the same reference frame!")
        quaternions = [rv.as_quaternion for rv in rotation_vectors]

        # Compute the Karcher mean of the quaternions
        mean_quat = karcher_mean_quaternions(quaternions)

        # Convert the mean quaternion back to a rotation vector
        mean_rotation = R.from_quat(mean_quat)
        mean_rotation_vector = mean_rotation.as_rotvec()

        # Assuming all rotation vectors have the same reference frame
        reference_frame = rotation_vectors[0].reference_frame

        return cls(vector=mean_rotation_vector,
                   reference_frame=reference_frame)


class TranslationVector(BaseModel):
    vector: TranslationVectorArray
    reference_frame: str

    @classmethod
    def mean_from_translation_vectors(cls, translation_vectors: list["TranslationVector"]) -> "TranslationVector":
        if not all([tv.reference_frame == translation_vectors[0].reference_frame for tv in translation_vectors]):
            raise ValueError("All translation vectors must have the same reference frame!")
        mean_translation_vector = np.mean([tv.vector for tv in translation_vectors], axis=0)

        # Assuming all rotation vectors have the same reference frame
        reference_frame = translation_vectors[0].reference_frame

        return cls(vector=mean_translation_vector,
                   reference_frame=reference_frame)


class TransformationMatrix(BaseModel):
    matrix: NDArray[Shape["4, 4"], np.float64]
    reference_frame: str

    @classmethod
    def from_extrinsics(cls, extrinsics_matrix: CameraExtrinsicsMatrix, reference_frame: str):
        rotation_matrix = np.squeeze(extrinsics_matrix[:3, :3])
        translation_vector = np.squeeze(extrinsics_matrix[:3, 3])
        return cls.from_rotation_translation(rotation_vector=RotationVector(vector=np.squeeze(cv2.Rodrigues(rotation_matrix)[0]),
                                                                            reference_frame=reference_frame),
                                                 translation_vector=TranslationVector(vector=translation_vector,
                                                                                    reference_frame=reference_frame))

    @classmethod
    def from_rotation_translation(cls,
                                  rotation_vector: RotationVector,
                                  translation_vector: TranslationVector):
        if rotation_vector.reference_frame != translation_vector.reference_frame:
            raise ValueError("Rotation and translation vectors must be in the same reference frame")
        rotation_matrix = rotation_vector.as_rotation_matrix
        transformation_matrix = np.eye(4)
        transformation_matrix[:3, :3] = rotation_matrix
        transformation_matrix[:3, 3] = translation_vector.vector
        return cls(matrix=transformation_matrix, reference_frame=translation_vector.reference_frame)

    @classmethod
    def mean_from_transformation_matrices(cls, transformation_matrices: list[
        "TransformationMatrix"]) -> "TransformationMatrix":
        if not all(
                [tm.reference_frame == transformation_matrices[0].reference_frame for tm in transformation_matrices]):
            raise ValueError("All transformation matrices must have the same reference frame!")

        rotation_vectors = [tm.rotation_vector for tm in transformation_matrices]
        translation_vectors = [tm.translation_vector for tm in transformation_matrices]

        mean_rotation_vector = RotationVector.mean_from_rotation_vectors(rotation_vectors)
        mean_translation_vector = TranslationVector.mean_from_translation_vectors(translation_vectors)

        return cls.from_rotation_translation(rotation_vector=mean_rotation_vector,
                                             translation_vector=mean_translation_vector)

    @property
    def rotation_matrix(self) -> NDArray[Shape["3, 3"], np.float32]:
        return self.matrix[:3, :3]

    @property
    def translation_vector(self) -> TranslationVector:
        return TranslationVector(vector=self.matrix[:3, 3], reference_frame=self.reference_frame)

    @property
    def rotation_vector(self) -> RotationVector:
        return RotationVector(vector=np.squeeze(cv2.Rodrigues(self.rotation_matrix)[0]), reference_frame=self.reference_frame)

    @property
    def extrinsics_matrix(self) -> CameraExtrinsicsMatrix:
        return self.matrix[:3, :]


    def get_inverse(self):
        inverse_rotation_matrix = self.rotation_matrix.T
        inverse_translation_vector = -inverse_rotation_matrix @ self.translation_vector.vector

        inverse_matrix = np.eye(4)
        inverse_matrix[:3, :3] = inverse_rotation_matrix
        inverse_matrix[:3, 3] = inverse_translation_vector

        return TransformationMatrix(matrix=inverse_matrix, reference_frame=self.reference_frame)

    def __matmul__(self, other: "TransformationMatrix") -> "TransformationMatrix":
        if not isinstance(other, TransformationMatrix):
            raise TypeError(
                "Unsupported operand type(s) for @: 'TransformationMatrix' and '{}'".format(type(other).__name__))
        # Perform matrix multiplication and use self's reference frame
        return TransformationMatrix(matrix=self.matrix @ other.matrix, reference_frame=self.reference_frame)


    def __str__(self) -> str:
        return (f"\treference_frame={self.reference_frame},\n"
                f"\tmatrix=\n"
                f"\t\t{self.matrix[0, :]:.3f},\n"
                f"\t\t{self.matrix[1, :]:.3f},\n"
                f"\t\t{self.matrix[2, :]:.3f},\n"
                f"\t\t{self.matrix[3, :]:.3f},\n")


class CameraDistortionCoefficients(BaseModel):
    """
    https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html
    Distortion coefficients for the camera, must be either 4, 5, 8, 12, or 14 values.

    0-3 are k1, k2, p1, p2
    4 is k3
    5-7 are k4, k5, k6
    8-11 are s1, s2, s3, s4
    12-13 are τ1, τ2 (τ like tau)

    `k` values refer to radial distortion coefficients
    `p` values refer to tangential distortion coefficients
    `s` values refer to thin prism distortion coefficients
    `τ` values refer to x/y values of the 'tilted sensor' model

    NOTE - RECOMMEND USING 5 VALUES, things get weird with more than 5
    """
    coefficients: CameraDistortionCoefficientsArray

    @model_validator(mode="after")
    def validate(self):
        self.coefficients = np.square(self.coefficients)
        if len(self.coefficients) not in [4, 5, 8, 12, 14]:
            raise ValueError("Invalid number of distortion coefficients. Must be 4, 5, 8, 12, or 14.")
        return self


class CameraMatrix(BaseModel):
    matrix: CameraMatrixArray

    @classmethod
    def from_image_size(cls, image_size: tuple[int, ...]):
        camera_matrix = np.eye(3)
        camera_matrix[0, 2] = image_size[0] / 2  # x_center
        camera_matrix[1, 2] = image_size[1] / 2  # y_center
        return cls(matrix=camera_matrix)

    @model_validator(mode="after")
    def validate(self):
        if self.matrix.shape != (3, 3):
            raise ValueError("Camera matrix must be 3x3")
        return self

    @property
    def focal_length(self) -> float:
        return self.matrix[0, 0]

    @property
    def focal_length_x(self) -> float:
        return self.matrix[0, 0]

    @property
    def focal_length_y(self) -> float:
        return self.matrix[1, 1]

    @property
    def focal_length_xy(self) -> float:
        return (self.focal_length_x + self.focal_length_y) / 2

    @property
    def principal_point(self) -> tuple[float, float]:
        return self.matrix[0, 2], self.matrix[1, 2]
