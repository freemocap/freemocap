from typing import Tuple
import cv2
import numpy as np
import matplotlib.pyplot as plt

def plot_axis_indicator(ax: plt.Axes, x_vector: np.ndarray, y_vector: np.ndarray, z_vector: np.ndarray) -> None:
    ax.quiver(0, 0, 0, x_vector[0], x_vector[1], x_vector[2], length=1, normalize=True, color='r', alpha=0.5)
    ax.quiver(0, 0, 0, y_vector[0], y_vector[1], y_vector[2], length=1, normalize=True, color='g', alpha=0.5)
    ax.quiver(0, 0, 0, z_vector[0], z_vector[1], z_vector[2], length=1, normalize=True, color='b', alpha=0.5)

    ax.set_xlim((-1, 1))
    ax.set_ylim((-1, 1))
    ax.set_zlim((-1, 1))

    ax.set_xlabel('X axis')
    ax.set_ylabel('Y axis')
    ax.set_zlabel('Z axis')

    ax.set_aspect('equal', 'box')

def setup_plot() -> Tuple[plt.Figure, plt.Axes]:
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    return fig, ax

def show_plot(fig: plt.Figure, ax: plt.Axes) -> None:
    """
    Ensures axes are correctly set up and labeled, then calls plt.show()
    """

    ax.set_xlabel('X axis')
    ax.set_ylabel('Y axis')
    ax.set_zlabel('Z axis')

    ax.set_aspect('equal', 'box')
    plt.show()


if __name__ == "__main__":
    id = np.identity(3)
    fig, ax = setup_plot()
    plot_axis_indicator(ax=ax, x_vector=id[0, :], y_vector=id[1, :], z_vector=id[2, :])

    rad = np.radians(45)
    # rad around z
    z_rotation_matrix = np.array([
        [np.cos(rad), -np.sin(rad), 0],
        [np.sin(rad), np.cos(rad), 0],
        [0, 0, 1]
    ])

    # rad around y
    y_rotation_matrix = np.array([
        [np.cos(rad), 0, np.sin(rad)],
        [0, 1, 0],
        [-np.sin(rad), 0, np.cos(rad)]
    ])

    # rad around x
    x_rotation_matrix = np.array([
        [1, 0, 0],
        [0, np.cos(rad), -np.sin(rad)],
        [0, np.sin(rad), np.cos(rad)]
    ])

    # rotation_matrix = z_rotation_matrix
    rotation_matrix = x_rotation_matrix @ y_rotation_matrix @ z_rotation_matrix
    rotated_id = rotation_matrix @ id
    print(id)
    print(rotated_id)
    rodrigues, _ = cv2.Rodrigues(rotated_id)
    print(rodrigues)
    plot_axis_indicator(ax=ax, x_vector=rotated_id[0, :], y_vector=rotated_id[1, :], z_vector=rotated_id[2, :])

    show_plot(fig=fig, ax=ax)