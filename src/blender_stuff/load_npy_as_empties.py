import bpy
import numpy as np
from mathutils import Vector
from pathlib import Path

try:
    import pandas as pd
    import numpy as np
except:
    import sys
    import os
    import subprocess

    python_exe = os.path.join(sys.prefix, "bin", "python.exe")

    subprocess.call([python_exe, "-m", "ensurepip"])
    subprocess.call([python_exe, "-m", "pip", "install", "--upgrade", "pip"])
    subprocess.call([python_exe, "-m", "pip", "install", "--upgrade", "pandas"])
    subprocess.call([python_exe, "-m", "pip", "install", "--upgrade", "numpy"])
    import pandas as pd
    import numpy as np

mediapipe_body_trajectory_names = [
    "nose",
    "left_eye_inner",
    "left_eye",
    "left_eye_outer",
    "right_eye_inner",
    "right_eye",
    "right_eye_outer",
    "left_ear",
    "right_ear",
    "mouth_left",
    "mouth_right",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_pinky",
    "right_pinky",
    "left_index",
    "right_index",
    "left_thumb",
    "right_thumb",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
    "left_heel",
    "right_heel",
    "left_foot_index",
    "right_foot_index",
]


def create_keyframed_empty_from_3d_trajectory_data(
    trajectory_fr_xyz: np.ndarray,
    parent_origin: bpy.types.Object = None,
    empty_scale: float = 0.0251,
    empty_type: str = "SPHERE",
    empty_name: str = None,
):
    """
    Create a key framed empty from 3d trajectory data
    """

    bpy.ops.object.empty_add(type=empty_type)
    empty_object = bpy.context.active_object

    empty_object.scale = [empty_scale] * 3

    if parent_origin is not None:
        empty_object.parent = parent_origin

    if empty_name is not None:
        empty_object.name = empty_name

    for frame_number in range(trajectory_fr_xyz.shape[0]):
        empty_object.location = [
            trajectory_fr_xyz[frame_number, 0],
            trajectory_fr_xyz[frame_number, 1],
            trajectory_fr_xyz[frame_number, 2],
        ]
        bpy.context.view_layer.update()

        empty_object.keyframe_insert(data_path="location", frame=frame_number)


og_npy_path = "D:\Dropbox\FreeMoCapProject\FreeMocap_Data\sesh_2022-11-09_20_38_23_neurons_demo\DataArrays\mediapipe_body_3d_xyz_blender_rotated.npy"
og_skel = np.load(og_npy_path) / 1000
rot_skel = og_skel.copy()

# og_csv_path = "D:\Dropbox\FreeMoCapProject\FreeMocap_Data\sesh_2022-11-09_20_38_23_neurons_demo\DataArrays\mediapipe_body_3d_xyz.csv"
# of_skel_df = pd.read_csv(og_csv_path)


bpy.ops.object.empty_add(type="ARROWS")
freemocap_axes = bpy.context.active_object
freemocap_axes.name = "freemocap_origin_axes"  # will translate to put skelly on ground symmetric-ish about origin

for marker_name, marker_number in zip(
    mediapipe_body_trajectory_names, range(og_skel.shape[1])
):
    create_keyframed_empty_from_3d_trajectory_data(
        og_skel[:, marker_number, :],
        parent_origin=freemocap_axes,
        empty_name=marker_name,
    )


bpy.context.scene.frame_end = og_skel.shape[0]
