import logging
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import numpy as np

from freemocap.core_processes.capture_volume_calibration.charuco_stuff.set_groundplane_with_charuco import create_rotation_matrix_from_rotation_vector, rotate_point

logging.getLogger("matplotlib").setLevel(logging.WARNING)

def rotate_skeleton_to_vector(vector_to_rotate_to: np.ndarray, original_points: np.ndarray) -> np.ndarray:
    rotation_matrix  = create_rotation_matrix_from_rotation_vector(vector_to_rotate_to)

    rotated_points = np.zeros(original_points.shape)
    for point in range(original_points.shape[0]):
        rotated_points[point, :] = rotate_point(original_points[point, :], rotation_matrix)
    return rotated_points

obj_points = np.asarray([[1., 1., 0.], [2., 1., 0.],
            [3., 1., 0.], [4., 1., 0.],
            [5., 1., 0.], [6., 1., 0.],
            [1., 2., 0.], [2., 2., 0.],
            [3., 2., 0.], [4., 2., 0.],
            [5., 2., 0.], [6., 2., 0.],
            [1., 3., 0.], [2., 3., 0.],
            [3., 3., 0.], [4., 3., 0.], 
            [4., 3., 0.], [5., 3., 0.], 
            [6., 3., 0.], [1., 4., 0.],
            [2., 4., 0.], [3., 4., 0.],
            [4., 4., 0.]])

# vector_to_rotate_to = np.array([-0.96589522, -0.77364613, -1.11162952])
vector_to_rotate_to = np.array([0.9658952227181706, 0.7736461280213088, 1.1116295230333113])

transformed_obj_points = rotate_skeleton_to_vector(vector_to_rotate_to, obj_points)

# Extracting the x, y, z coordinates for plotting
xs = obj_points[:, 0]
ys = obj_points[:, 1]
zs = obj_points[:, 2]

transformed_xs = transformed_obj_points[:, 0]
transformed_ys = transformed_obj_points[:, 1]
transformed_zs = transformed_obj_points[:, 2]

# Plotting the Charuco board corners in world coordinates
fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')
ax.scatter(xs, ys, zs, c='r', marker='o', label='Original Charuco Board Points')

ax.scatter(transformed_xs, transformed_ys, transformed_zs, c='b', marker='o', label='Transformed Charuco Board Points')

ax.set_xlabel('X Label')
ax.set_ylabel('Y Label')
ax.set_zlabel('Z Label')

plt.legend(loc='upper left')

plt.show()