import bpy
import numpy as np
import sys
from pathlib import Path

print("loading gaze data as empties")


def load_gaze_data(gaze_fr_xyz: np.ndarray, eye_empty_name: str):

    this_eyeball_empty = bpy.data.objects[eye_empty_name]

    bpy.ops.object.empty_add(type="SPHERE")
    this_gaze_empty = bpy.context.active_object
    print(f"loading {eye_empty_name} gaze data...")
    for frame_num in range(r_gaze_eye_in_head_xyz.shape[0]):

        this_gaze_empty.location = (
            gaze_fr_xyz[frame_num, 0],
            gaze_fr_xyz[frame_num, 1],
            gaze_fr_xyz[frame_num, 2],
        )
        this_gaze_empty.scale = (0.01, 0.01, 0.01)

        this_gaze_empty.name = eye_empty_name + "_gaze_empty"

        this_gaze_empty.keyframe_insert(data_path="location", frame=frame_num)

    bpy.ops.object.armature_add(
        enter_editmode=False, align="WORLD", location=(0, 0, 0), scale=(1, 1, 1)
    )
    this_gaze_armature = bpy.context.active_object
    this_gaze_armature.name = eye_empty_name + "_gaze_armature"

    this_gaze_bone_name = eye_empty_name + "_gaze_bone"
    this_gaze_bone = this_gaze_armature.data.bones[0]
    this_gaze_bone.name = this_gaze_bone_name

    # #create gaze bone
    # this_gaze_edit_bone= this_gaze_armature.data.edit_bones[0] # note this is using EDIT_bones, not regular bones b/c blender is a wild wacky place
    # this_gaze_edit_bone.tail = this_eyeball_empty.location
    # this_gaze_edit_bone.head = this_gaze_empty.location

    # track gaze bone to gaze empty
    this_gaze_pose_bone = this_gaze_armature.pose.bones[0]

    this_gaze_constraint = this_gaze_pose_bone.constraints.new("COPY_LOCATION")
    this_gaze_constraint.target = this_eyeball_empty
    this_gaze_constraint = this_gaze_pose_bone.constraints.new("DAMPED_TRACK")
    this_gaze_constraint.target = this_gaze_empty


try:
    ##% Session path
    # #get session path as command line argument
    argv = sys.argv
    argv = argv[argv.index("--") + 1 :]
    session_path = argv[0]

    if len(argv) > 1:
        good_clean_frame_number = int(argv[1])
    else:
        good_clean_frame_number = 0
except:
    print(
        "we appear to be running from the Blender Scripting tab! Manually enter your `session_path` at line 23"
    )
    session_path = Path(
        r"C:\Users\jonma\Dropbox\FreeMoCapProject\FreeMocap_Data\sesh_2022-05-07_17_15_05_pupil_wobble_juggle_0"
    )


data_arrays_path = session_path / "DataArrays"

path_to_right_eye_gaze_xyz_npy = data_arrays_path / "right_eye_gaze_fr_xyz.npy"
path_to_left_eye_gaze_xyz_npy = data_arrays_path / "left_eye_gaze_fr_xyz.npy"


# right eye
print(f"loading right_eye_data...")
r_gaze_eye_in_head_xyz = np.load(path_to_right_eye_gaze_xyz_npy)
r_gaze_eye_in_head_xyz *= 0.001  # convert to meters
load_gaze_data(r_gaze_eye_in_head_xyz, "right_eye")

# right eye
print(f"loading left_eye_data...")
l_gaze_eye_in_head_xyz = np.load(path_to_left_eye_gaze_xyz_npy)
l_gaze_eye_in_head_xyz *= 0.001  # convert to meters
load_gaze_data(l_gaze_eye_in_head_xyz, "left_eye")


print("done!")
