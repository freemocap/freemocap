"""
============
3D animation
============

An animated plot in 3D.
from - https://matplotlib.org/2.1.2/gallery/animation/simple_3danim.html
"""
import numpy as np
import matplotlib.pyplot as plt
import mpl_toolkits.mplot3d.axes3d as p3
import matplotlib.animation as animation
from matplotlib.widgets import Slider

#RICH CONSOLE STUFF
from rich import pretty
pretty.install() #makes all print statement output pretty
from rich import inspect
from rich.console import Console
console = Console()  
from rich.traceback import install as rich_traceback_install
rich_traceback_install()

def main():
    # Fixing random state for reproducibility
    np.random.seed(19680801)



    def Gen_RandLine(length, dims=2):
        """
        Create a line using a random walk algorithm

        length is the number of points for the line.
        dims is the number of dimensions the line has.
        """
        lineData = np.empty((dims, length))
        lineData[:, 0] = np.random.rand(dims)
        for index in range(1, length):
            # scaling the random numbers by 0.1 so
            # movement is small compared to position.
            # subtraction by 0.5 is to change the range to [-0.5, 0.5]
            # to allow a line to move backwards.
            step = ((np.random.rand(dims) - 0.5) * 0.1)
            lineData[:, index] = lineData[:, index - 1] + step

        return lineData


    def update_lines(num, dataLines, lines):
        for line, data in zip(lines, dataLines):
            # NOTE: there is no .set_data() for 3 dim data...
            line.set_data(data[0:2, :num])
            line.set_3d_properties(data[2, :num])
        animSlider.set_val(val=num)
        return lines

    # Attaching 3D axis to the figure
    fig = plt.figure()
    plt.ion()
    plt.show()

    ax3d = p3.Axes3D(fig)
    ax3d.set_position([.1, .1, .8, .8]) # [left, bottom, width, height])


    # Fifty lines of random 3-D lines
    data = [Gen_RandLine(100, 3) for index in range(5)]

    # Creating fifty line objects.
    # NOTE: Can't pass empty arrays into 3d version of plot()
    lines = [ax3d.plot(dat[0, 0:1], dat[1, 0:1], dat[2, 0:1])[0] for dat in data]

    # Setting the axes properties
    ax3d.set_xlim3d([0.0, 1.0])
    ax3d.set_xlabel('X')

    ax3d.set_ylim3d([0.0, 1.0])
    ax3d.set_ylabel('Y')

    ax3d.set_zlim3d([0.0, 1.0])
    ax3d.set_zlabel('Z')

    ax3d.set_title('3D Test')




    numFrames = 100
    #slider
    axControls = fig.add_subplot(2,1,2)
    axControls.set_position([0.25, 0.01, 0.6, 0.05])
    animSlider = Slider(
        ax=axControls,
        label="FrameNum",
        valmin=0,
        valmax=numFrames,
        valinit=0,
        orientation="horizontal"
    )
    # Creating the Animation object
    line_animation = animation.FuncAnimation(fig, update_lines, numFrames, fargs=(data, lines),
                                    interval=50, blit=False)

    plt.draw()
    plt.pause(.001) # pause a bit so that plots are updated                                  
    
    console.print(":sparkle: :skull: :sparkle:")

if __name__ == '__main__':
    main()