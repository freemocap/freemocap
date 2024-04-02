import numpy as np
import matplotlib.pyplot as plt

def plot_axis_indicator(ax: plt.Axes, identity: np.ndarray = np.identity(3)) -> None:
    ax.quiver(0, 0, 0, identity[0, 0], identity[0, 1], identity[0, 2], length=1, normalize=True, color='r')
    ax.quiver(0, 0, 0, identity[1, 0], identity[1, 1], identity[1, 2], length=1, normalize=True, color='g')
    ax.quiver(0, 0, 0, identity[2, 0], identity[2, 1], identity[2, 2], length=1, normalize=True, color='b')

    ax.set_xlim((-1, 1))
    ax.set_ylim((-1, 1))
    ax.set_zlim((-1, 1))

    ax.set_xlabel('X axis')
    ax.set_ylabel('Y axis')
    ax.set_zlabel('Z axis')

    ax.set_aspect('equal', 'box')


if __name__ == "__main__":
    plot_axis_indicator(identity)