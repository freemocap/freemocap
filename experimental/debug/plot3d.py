from mpl_toolkits.mplot3d import Axes3D
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial.transform import Rotation as R

def translate(points, translation_vector):
    return points + translation_vector

def rotate(points, rotation_vector):
    # Using scipy's Rotation for demonstration
    rotation = R.from_rotvec(rotation_vector)
    return rotation.apply(points)

def plot_points(points, translation_vector, rotation_vector):
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    # Plot original points
    original_scatter = ax.scatter(points[:, 0], points[:, 1], points[:, 2], label='Original Points')

    # Apply transformations
    translated_points = translate(points, translation_vector)
    transformed_points = rotate(translated_points, rotation_vector)

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
    raw_skeleton_datapath = "/Users/philipqueen/freemocap_data/recording_sessions/aaron_ground_charuco_test/recording_14_23_11_gmt-4/output_data/mediaPipeSkel_3d_body_hands_face.npy"
    raw_skeleton_data = np.load(raw_skeleton_datapath)

    good_frame = 443

    good_frame_skeleton_data = raw_skeleton_data[good_frame, :, :]
    
    
    # Example translation and rotation vectors
    # rotation_vector = np.array([-0.9073614688297462, -1.2558728420057141, -1.557351087317003])
    rotation_vector = np.array([0, 0, 0])
    translation_vector = np.array([2210.774828053054, -150.00270933214654, -1684.2280492589714,])
    # translation_vector = np.array([0, 0, 0])

    plot_points(good_frame_skeleton_data, translation_vector, rotation_vector)