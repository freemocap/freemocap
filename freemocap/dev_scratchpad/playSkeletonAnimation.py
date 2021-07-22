#https://matplotlib.org/stable/api/animation_api.html
from operator import is_
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from mpl_toolkits.mplot3d import axes3d
from matplotlib.widgets import Slider

fig = plt.figure()
ax3d = fig.add_subplot(211,projection="3d")
xdata, ydata , zdata = [], [], []
ln, = plt.plot([], [], [], 'r-o')

axControls = fig.add_subplot(212)

numFrames = 128
#slider
animSlider = Slider(
    ax=axControls,
    label="FrameNum",
    valmin=0,
    valmax=100,
    valinit=0,
    orientation="horizontal"
)
# Animation controls
is_manual = False # True if user has taken control of the animation
interval = 0 # ms, time between animation frames
loop_len = 0.1  # seconds per loop
scale = interval / 1000 / loop_len

def init():
    ax3d.set_xlim(0, 2*np.pi)
    ax3d.set_ylim(-1, 1)
    ax3d.set_zlim(-1, 1)
    return ln,

def update_slider(frameNum):
    global is_manual
    is_manual = True
    update_figure(frameNum)

def update_figure(frameNum):
    global is_manual
    if is_manual:
        return ln, #don't change in manual mode

    xdata.append(frameNum)
    ydata.append(np.sin(frameNum))
    zdata.append(np.sin(frameNum))
    ln.set_data_3d(xdata, ydata,zdata)
    is_manual = False # the above line called update_slider, so we need to reset this
    return ln,

def on_click(event):
    # Check where the click happened
    (xm,ym),(xM,yM) = animSlider.label.clipbox.get_points()
    if xm < event.x < xM and ym < event.y < yM:
        # Event happened within the slider, ignore since it is handled in update_slider
        return
    else:
        # user clicked somewhere else on canvas = unpause
        global is_manual
        is_manual=False

# call update function on slider value change
animSlider.on_changed(update_slider)
fig.canvas.mpl_connect('button_press_event', on_click)

ani = FuncAnimation(fig, update_figure, frames=np.linspace(0, 2*np.pi, numFrames),
                    init_func=init, blit=True)
plt.show()