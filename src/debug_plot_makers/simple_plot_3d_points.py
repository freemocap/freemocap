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
