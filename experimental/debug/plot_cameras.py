import cv2
import numpy as np
import toml

from pathlib import Path
from matplotlib import pyplot as plt


def camera_dict_from_toml(path_to_toml: str | Path) -> dict:
    camera_dict = {}
    calibration_dict = toml.load(Path(path_to_toml))

    for key, value in calibration_dict.items():
        if key == "metadata":
            continue
        camera_dict[key] = {"rotation": value["rotation"], "translation": value["translation"]}
        print(f"{key}: {camera_dict[key]}")

    return camera_dict

def plot_axis_indicator(ax: plt.Axes, identity: np.ndarray = np.identity(3)) -> None:
    ax.quiver(0, 0, 0, identity[0, 0], identity[0, 1], identity[0, 2], length=300, normalize=True, color='r')
    ax.quiver(0, 0, 0, identity[1, 0], identity[1, 1], identity[1, 2], length=300, normalize=True, color='g')
    ax.quiver(0, 0, 0, identity[2, 0], identity[2, 1], identity[2, 2], length=300, normalize=True, color='b')

def plot_groundplane(ax: plt.Axes) -> None:
    
    xx, yy = np.meshgrid(range(10), range(10))
    z = (9 - xx - yy) / 2 

    # plot the plane
    ax.plot_surface(xx, yy, z, alpha=0.5)


def rotation_matrix_to_direction(rvec: np.ndarray) -> np.ndarray:
    rotation_matrix, _ = cv2.Rodrigues(rvec)
    direction = rotation_matrix[:, 2]

    return direction

def plot_points(camera_dict: dict, skeleton: np.ndarray, line_length: float = 300) -> None:
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    for camera_name, camera_data in camera_dict.items():
        rotation = np.asarray(camera_data["rotation"])
        translation = camera_data["translation"]

        ax.scatter(translation[0], translation[1], translation[2], label=f"{camera_name}")

        rotation_matrix, _ = cv2.Rodrigues(rotation)

        ax.quiver(translation[0], translation[1], translation[2], 
                  rotation_matrix[0, 0], rotation_matrix[0,1], rotation_matrix[0,2], 
                  length=line_length, normalize=True, color='r', alpha=0.5)

        ax.quiver(translation[0], translation[1], translation[2], 
                  rotation_matrix[1, 0], rotation_matrix[1,1], rotation_matrix[1,2], 
                  length=line_length, normalize=True, color='g', alpha=0.5)

        ax.quiver(translation[0], translation[1], translation[2], 
                  rotation_matrix[2, 0], rotation_matrix[2,1], rotation_matrix[2,2], 
                  length=line_length, normalize=True, color='b', alpha=0.5)
        
        
    skeleton_scatter = ax.scatter(skeleton[:, 0], skeleton[:, 1], skeleton[:, 2], label='Original Points')

    plot_axis_indicator(ax=ax)
    
    ax.set_xlabel('X axis')
    ax.set_ylabel('Y axis')
    ax.set_zlabel('Z axis')

    ax.set_aspect('equal', 'box')

    plt.legend()

    plt.show()

if __name__ == "__main__":
    toml_path = "/Users/philipqueen/freemocap_data/recording_sessions/iphone_testing/iPhoneTesting_camera_calibration.toml"

    raw_skeleton_data = np.load("/Users/philipqueen/freemocap_data/recording_sessions/iphone_testing/output_data/raw_data/mediapipe3dData_numFrames_numTrackedPoints_spatialXYZ.npy")

    good_frame = 600

    good_frame_skeleton_data = raw_skeleton_data[good_frame, :, :]
    print(good_frame_skeleton_data)
    print(good_frame_skeleton_data.shape)

    camera_dict = camera_dict_from_toml(toml_path)

    plot_points(camera_dict, good_frame_skeleton_data)
