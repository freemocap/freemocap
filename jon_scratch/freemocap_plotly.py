# Import data
import time
import numpy as np
import plotly.graph_objects as go
from skimage import io
from pathlib import Path
## load in freemocap data
session_id = 'sesh_2022-02-15_11_54_28_pupil_maybe'
freemocap_data_folder = Path('C:/Users/jonma/Dropbox/FreeMoCapProject/FreeMocap_Data')
session_folder_path = freemocap_data_folder / session_id
data_arrays_path = session_folder_path / 'DataArrays'
mediapipe_skeleton_data_path = data_arrays_path / 'mediaPipeSkel_3d_smoothed.npy'
mediapipe_skeleton_fr_mar_xyz = np.load(mediapipe_skeleton_data_path)

##
vol = io.imread("https://s3.amazonaws.com/assets.datacamp.com/blog_assets/attention-mri.tif")
volume = vol.T
r, c = volume[0].shape

# Define frames
number_of_frames = mediapipe_skeleton_fr_mar_xyz.shape[0]

fig = go.Figure(frames=[
    go.Frame(

        data=go.Scatter3d(
            x=mediapipe_skeleton_fr_mar_xyz[this_frame_number, :, 0],
            y=mediapipe_skeleton_fr_mar_xyz[this_frame_number, :, 1],
            z=mediapipe_skeleton_fr_mar_xyz[this_frame_number, :, 2],
            mode='markers',
            marker=dict(
                size=12,
                color='red',  # set color to an array/list of desired values
                colorscale='Viridis',  # choose a colorscale
                opacity=0.8
            )
        ),

        name=str(this_frame_number)  # you need to name the frame for the animation to behave properly
    )
    for this_frame_number in range(number_of_frames)])

# Add data to be displayed before animation starts
fig.add_trace(go.Surface(
    z=6.7 * np.ones((r, c)),
    surfacecolor=np.flipud(volume[67]),
    colorscale='Gray',
    cmin=0, cmax=200,
    colorbar=dict(thickness=20, ticklen=4)
))


def frame_args(duration):
    return {
        "frame": {"duration": duration},
        "mode": "immediate",
        "fromcurrent": True,
        "transition": {"duration": duration, "easing": "linear"},
    }


sliders = [
    {
        "pad": {"b": 10, "t": 60},
        "len": 0.9,
        "x": 0.1,
        "y": 0,
        "steps": [
            {
                "args": [[f.name], frame_args(0)],
                "label": str(k),
                "method": "animate",
            }
            for k, f in enumerate(fig.frames)
        ],
    }
]

# Layout
fig.update_layout(
    title='Slices in volumetric data',
    width=600,
    height=600,
    scene=dict(
        zaxis=dict(range=[-2e3, 2e3], autorange=False),
        aspectratio=dict(x=1, y=1, z=1),
    ),
    updatemenus=[
        {
            "buttons": [
                {
                    "args": [None, frame_args(0)],
                    "label": "&#9654;",  # play symbol
                    "method": "animate",
                },
                {
                    "args": [[None], frame_args(0)],
                    "label": "&#9724;",  # pause symbol
                    "method": "animate",
                },
            ],
            "direction": "left",
            "pad": {"r": 10, "t": 70},
            "type": "buttons",
            "x": 0.1,
            "y": 0,
        }
    ],
    sliders=sliders
)

fig.show()
