import logging
from mpl_toolkits.mplot3d import Axes3D
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial.transform import Rotation as R

from freemocap.core_processes.capture_volume_calibration.charuco_stuff.set_groundplane_with_charuco import calculate_rotation_matrix, create_unit_vector, create_vector, rotate_point

def translate(points, translation_vector):
    return points + translation_vector

def create_rotation_matrix_from_rotation_vector(rotation_vector: np.ndarray) -> np.ndarray:
    origin_normal_unit_vector = create_vector(np.array([0, 0, 0]), np.array([0, 0, 1]))
    unit_rotation_vector = create_unit_vector(rotation_vector)
    return calculate_rotation_matrix(unit_rotation_vector, origin_normal_unit_vector)

def rotate_skeleton_to_vector(vector_to_rotate_to:np.ndarray, original_skeleton_np_array:np.ndarray) -> np.ndarray:
    """ 
    Find the rotation matrix needed to rotate the 'reference vector' to match the 'vector_to_rotate_to', and 
    rotate the entire skeleton with that matrix.

        Input: 
            Reference Vector: The vector on the skeleton that you want to rotate/base the rotation matrix on 
            Vector_to_rotate_to: The vector that you want to align the skeleton too (i.e. the x-axis/y-axis etc.)
            Original skeleton data: The freemocap data you want to rotate
        Output:
            rotated_skeleton_data: A numpy data array of your rotated skeleton

    """

    rotation_matrix  = create_rotation_matrix_from_rotation_vector(vector_to_rotate_to)

    rotated_skeleton_data_array = np.zeros(original_skeleton_np_array.shape)
    for point in range(original_skeleton_np_array.shape[0]):
        rotated_skeleton_data_array[point, :] = rotate_point(original_skeleton_np_array[point, :], rotation_matrix)
    return rotated_skeleton_data_array

def plot_points(points, translation_vector, rotation_vector):
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    # Plot original points
    original_scatter = ax.scatter(points[:, 0], points[:, 1], points[:, 2], label='Original Points')

    # Apply transformations
    translated_points = translate(points, translation_vector)
    transformed_points = rotate_skeleton_to_vector(rotation_vector, translated_points)

    # Plot transformed points
    transformed_scatter = ax.scatter(transformed_points[:, 0], transformed_points[:, 1], transformed_points[:, 2], 
                                     color='r', label='Transformed Points')
    
    ax.scatter([0], [0], [0], color='g', s=100, marker='*', label='Origin')

    # Set labels and plot range for better visualization
    ax.set_xlabel('X axis')
    ax.set_ylabel('Y axis')
    ax.set_zlabel('Z axis')

    # Add legend
    plt.legend()

    plt.show()


if __name__ == '__main__':
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    raw_skeleton_datapath = "/Users/philipqueen/freemocap_data/recording_sessions/aaron_ground_charuco_test/recording_14_23_11_gmt-4/output_data/mediaPipeSkel_3d_body_hands_face.npy"
    raw_skeleton_data = np.load(raw_skeleton_datapath)

    good_frame = 443

    good_frame_skeleton_data = raw_skeleton_data[good_frame, :, :]
    
    
    # Example translation and rotation vectors
    # rotation_vector = np.array([0.53001589, 0.29190598, 1.03438838])
    # rotation_vector = np.array([0.7736461280213088, 1.1116295230333113, 0.9658952227181706])
    rotation_vector = np.array([0, 0, 1])
    translation_vector = np.array([2221.526610089684, -164.67318405283316, -1736.7409796095908])
    # translation_vector = np.array([0, 0, 0])

    plot_points(good_frame_skeleton_data, translation_vector, rotation_vector)