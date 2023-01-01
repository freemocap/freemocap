import matplotlib
from matplotlib import pyplot as plt


def simple_plot_3d(data_pt_xyz):
    x = data_pt_xyz[:, 0]
    y = data_pt_xyz[:, 1]
    z = data_pt_xyz[:, 2]

    fig = plt.figure()
    matplotlib.use("qtagg")
    ax3d = fig.add_subplot(projection="3d")
    ax3d.scatter(x, y, z)
    plt.pause(0.1)
    plt.show()


if __name__ == "__main__":
    import numpy as np

    data_pt_xyz = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
    simple_plot_3d(data_pt_xyz)
