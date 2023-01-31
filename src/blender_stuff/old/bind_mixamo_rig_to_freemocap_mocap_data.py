import bpy
import numpy as np
from pathlib import Path
import json

from src.utils.get_video_files import get_video_files

#####################################################################
###%% clear the scene - Scorch the earth \o/
print("clearing scene")
try:
    bpy.ops.object.mode_set(mode="OBJECT")
except:
    pass

try:
    bpy.ops.object.select_all(action="SELECT")  # select all objects
    bpy.ops.object.delete(use_global=True)  # delete all objects from all scenes
except:
    pass

##################
### Getcher paths straight
path_to_data_folder = Path("/Users/jon/Dropbox/FreeMoCapProject/FreeMocap_Data/")
# path_to_data_folder = Path("D:\Dropbox\FreeMoCapProject\FreeMocap_Data")

session_id = "sesh_2022-09-19_16_16_50_in_class_jsm"

session_path = path_to_data_folder / session_id
path_to_data_arrays_folder = session_path / "DataArrays"
path_to_body_npy = path_to_data_arrays_folder / "mediapipe_body_3d_xyz.npy"

annotated_videos_path = session_path / "annotated_videos"

if annotated_videos_path.is_dir():
    vidFolderPath = annotated_videos_path
else:
    vidFolderPath = session_path / "synchronized_videos"

path_to_segment_length_json = (
    path_to_data_arrays_folder / "skeleton_segment_lengths.json"
)
print(f" json path - {str(path_to_segment_length_json)}")
f = open(path_to_segment_length_json)
skeleton_segment_lengths_dict = json.load(f)

path_to_mixamo_fbx = r"/Users/jon/Dropbox/FreeMoCapProject/teddy_animation/mixamo_binding_stuff/mixamo_mannequin_fbx_Ch36_nonPBR.fbx"
# path_to_mixamo_fbx = r"D:\Dropbox\FreeMoCapProject\teddy_animation\mixamo_binding_stuff\mixamo_mannequin_fbx_Ch36_nonPBR.fbx"

#########################
### Create Origin Axes

bpy.ops.object.empty_add(type="ARROWS")
world_origin_axes = bpy.context.active_object
world_origin_axes.name = "world_origin"  # will stay at origin

bpy.ops.object.empty_add(type="ARROWS")
freemocap_origin_axes = bpy.context.active_object
freemocap_origin_axes.name = "freemocap_origin_axes"  # will translate to put skelly on ground symmetric-ish about origin

#####################
## Load nSynched Videos
try:
    print("loading videos as planes...")

    world_origin = bpy.data.objects["world_origin"]

    number_of_videos = len(get_video_files(vidFolderPath))

    vid_location_scale = 1

    for (
        vid_number,
        thisVidPath,
    ) in enumerate(get_video_files(vidFolderPath)):
        print(thisVidPath)
        # use 'images as planes' add on to load in the video files as planes
        bpy.ops.import_image.to_plane(
            files=[{"name": thisVidPath.name}],
            directory=str(thisVidPath.parent),
            shader="EMISSION",
        )
        this_vid_as_plane = bpy.context.active_object
        this_vid_as_plane.name = "vid_" + str(vid_number)

        vid_x = (vid_number - number_of_videos / 2) * vid_location_scale

        this_vid_as_plane.location = [
            vid_x,
            vid_location_scale,
            vid_location_scale,
        ]
        this_vid_as_plane.rotation_euler = [np.pi / 2, 0, 0]
        this_vid_as_plane.scale = [vid_location_scale * 1.5] * 3
        this_vid_as_plane.parent = world_origin
        # create a light
        # bpy.ops.object.light_add(type='POINT', radius=1, align='WORLD')
except Exception as e:
    print(e)
    print(
        'Failed to load videos to Blender scene - You might need to install the "images as planes" addon to this version of Blender'
    )

############
## Mediapipe Tracked Point Names


mediapipe_body_names = [
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

#######################################################################
# %% load mediapipe data
# %%
print("loading data")
# %%


mediapipe_skel_fr_mar_dim = np.load(str(path_to_body_npy))
mediapipe_skel_fr_mar_dim = mediapipe_skel_fr_mar_dim / 1000  # convert to meters

print(f"mediapipe_skel_fr_mar_dim.shape: {mediapipe_skel_fr_mar_dim.shape}")

##############################
# %% Set start and end frames
number_of_frames = mediapipe_skel_fr_mar_dim.shape[0]
start_frame = 1
end_frame = number_of_frames

bpy.context.scene.frame_start = start_frame
bpy.context.scene.frame_end = end_frame

############################
### Load body data as empty markers


empty_size = 0.01

for this_point_index, this_point_name in enumerate(mediapipe_body_names):
    print(f"loading {this_point_name}...")
    bpy.ops.object.empty_add(type="SPHERE")
    this_empty = bpy.context.active_object
    this_empty.name = this_point_name

    this_empty.scale = [empty_size] * 3

    this_empty.parent = freemocap_origin_axes

    this_point_fr_xyz = mediapipe_skel_fr_mar_dim[:, this_point_index, :]

    for frame_num in range(end_frame):
        this_empty.location = [
            this_point_fr_xyz[frame_num, 0],
            this_point_fr_xyz[frame_num, 1],
            this_point_fr_xyz[frame_num, 2],
        ]
        bpy.context.view_layer.update()

        this_empty.keyframe_insert(data_path="location", frame=frame_num)

#######################################################################
# %% create virtual markers
print("creating virtual markers")

left_ear_index = 7
right_ear_index = 8
print("head_center - midway between left and right ears")
head_xyz = (
    mediapipe_skel_fr_mar_dim[:, left_ear_index, :]
    + mediapipe_skel_fr_mar_dim[:, right_ear_index, :]
) / 2
bpy.ops.object.empty_add(type="SPHERE")
this_empty = bpy.context.active_object
this_empty.name = "head_center"
this_empty.scale = [empty_size] * 3
this_empty.parent = freemocap_origin_axes

for frame_num in range(end_frame):
    this_empty.location = [
        head_xyz[frame_num, 0],
        head_xyz[frame_num, 1],
        head_xyz[frame_num, 2],
    ]
    this_empty.keyframe_insert(data_path="location", frame=frame_num)

print("neck_center - midway between left and right shoulders")
left_shoulder_index = 11
right_shoulder_index = 12
neck_xyz = (
    mediapipe_skel_fr_mar_dim[:, left_shoulder_index, :]
    + mediapipe_skel_fr_mar_dim[:, right_shoulder_index, :]
) / 2
bpy.ops.object.empty_add(type="PLAIN_AXES")
this_empty = bpy.context.active_object
this_empty.name = "neck_center"
this_empty.scale = [empty_size] * 3
this_empty.parent = freemocap_origin_axes

for frame_num in range(end_frame):
    this_empty.location = [
        neck_xyz[frame_num, 0],
        neck_xyz[frame_num, 1],
        neck_xyz[frame_num, 2],
    ]
    this_empty.keyframe_insert(data_path="location", frame=frame_num)

print("hip_center - midway between left and right hips")
left_hip_index = 23
right_hip_index = 24
hips_xyz = (
    mediapipe_skel_fr_mar_dim[:, left_hip_index, :]
    + mediapipe_skel_fr_mar_dim[:, right_hip_index, :]
) / 2
bpy.ops.object.empty_add(type="PLAIN_AXES")
this_empty = bpy.context.active_object
this_empty.name = "hip_center"
this_empty.scale = [empty_size] * 3
this_empty.parent = freemocap_origin_axes

for frame_num in range(end_frame):
    this_empty.location = [
        hips_xyz[frame_num, 0],
        hips_xyz[frame_num, 1],
        hips_xyz[frame_num, 2],
    ]
    this_empty.keyframe_insert(data_path="location", frame=frame_num)

print("chest_center - midway between hips and neck centers")

chest_xyz = (hips_xyz + neck_xyz) / 2
bpy.ops.object.empty_add(type="PLAIN_AXES")
this_empty = bpy.context.active_object
this_empty.name = "chest_center"
this_empty.scale = [empty_size] * 3
this_empty.parent = freemocap_origin_axes

for frame_num in range(end_frame):
    this_empty.location = [
        chest_xyz[frame_num, 0],
        chest_xyz[frame_num, 1],
        chest_xyz[frame_num, 2],
    ]
    this_empty.keyframe_insert(data_path="location", frame=frame_num)

######################
### Load Mixamo Armature
print(f"Loading Mixamo rigged mesh from: {path_to_mixamo_fbx}")
bpy.ops.import_scene.fbx(filepath=path_to_mixamo_fbx, use_anim=False)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
armature_name = "Armature"
armature = bpy.data.objects[armature_name]

freemocap_origin_axes.rotation_euler[2] = np.pi
##################
### Scale armature

rig_name = "mixamorig1"
mixamo_bone_to_skeleton_segment_name_correspondance = {
    "lower_spine": ["Hips", "Spine"],
    "upper_spine": ["Spine1", "Spine2"],
    "head": ["Neck", "Head"],
    "left_upper_arm": ["LeftArm"],
    "left_forearm": ["LeftForeArm"],
    "left_hand": ["LeftHand"],
    "right_upper_arm": ["RightArm"],
    "right_forearm": ["RightForeArm"],
    "right_hand": ["RightHand"],
    "left_thigh": ["LeftUpLeg"],
    "left_calf": ["LeftLeg"],
    "left_foot": ["LeftFoot"],
    "right_thigh": ["RightUpLeg"],
    "right_calf": ["RightLeg"],
    "right_foot": ["RightFoot"],
}

try:
    bpy.ops.object.mode_set(mode="EDIT")
except:
    pass

for (
    segment_name,
    mixamo_bones_list,
) in mixamo_bone_to_skeleton_segment_name_correspondance.items():
    print(
        f"segment: {segment_name}, length: {skeleton_segment_lengths_dict[segment_name]['median']}mm"
    )

    for mixamo_bone in mixamo_bones_list:
        segment_length = (
            skeleton_segment_lengths_dict[segment_name]["median"]
            / len(mixamo_bones_list)
        ) * 0.001
        print(f"setting: {mixamo_bone} length to: {segment_length} m")
        armature.data.edit_bones[f"{rig_name}:{mixamo_bone}"].length = segment_length

    ####################
#### get segment lengths

########################
### Constrain mixamo bones to track empty locations


rig_constraint_dict_of_dicts_og = {
    "Hips": {
        "COPY_LOCATION": "hip_center",
    },
    "Spine": {
        "IK": "chest_center",
    },
    "Spine1": {
        "COPY_LOCATION": "chest_center",
    },
    "Spine2": {
        "IK": "neck_center",
    },
    "Neck": {
        "COPY_LOCATION": "neck_center",
    },
    "Head": {
        "IK": "head_center",
    },
    "RightShoulder": {
        "COPY_LOCATION": "neck_center",
        "DAMPED_TRACK": "right_shoulder",
    },
    "RightArm": {
        "COPY_LOCATION": "right_shoulder",
        "DAMPED_TRACK": "right_elbow",
    },
    "RightForeArm": {
        "COPY_LOCATION": "right_elbow",
        "DAMPED_TRACK": "right_wrist",
    },
    "RightHand": {
        "COPY_LOCATION": "right_wrist",
        "DAMPED_TRACK": "right_index",
    },
    "LeftShoulder": {
        "COPY_LOCATION": "neck_center",
        "DAMPED_TRACK": "left_shoulder",
    },
    "LeftArm": {
        "COPY_LOCATION": "left_shoulder",
        "DAMPED_TRACK": "left_elbow",
    },
    "LeftForeArm": {
        "COPY_LOCATION": "left_elbow",
        "DAMPED_TRACK": "left_wrist",
    },
    "LeftHand": {
        "COPY_LOCATION": "left_wrist",
        "DAMPED_TRACK": "left_index",
    },
    "RightUpLeg": {
        "COPY_LOCATION": "right_hip",
        "DAMPED_TRACK": "right_knee",
    },
    "RightLeg": {
        "COPY_LOCATION": "right_knee",
        "DAMPED_TRACK": "right_ankle",
    },
    "RightFoot": {
        "COPY_LOCATION": "right_ankle",
        "DAMPED_TRACK": "right_foot_index",
    },
    "LeftUpLeg": {
        "COPY_LOCATION": "left_hip",
        "DAMPED_TRACK": "left_knee",
    },
    "LeftLeg": {
        "COPY_LOCATION": "left_knee",
        "DAMPED_TRACK": "left_ankle",
    },
    "LeftFoot": {
        "COPY_LOCATION": "left_ankle",
        "DAMPED_TRACK": "left_foot_index",
    },
}

### Pre-pend `rig_name` or whatever to bone names
rig_constraint_dict_of_dicts = {}
for key in rig_constraint_dict_of_dicts_og.keys():
    rig_constraint_dict_of_dicts[f"{rig_name}:{key}"] = rig_constraint_dict_of_dicts_og[
        key
    ]

####
#### Constrain bones to empties
####

# loop through dictionary applying  constraints
try:
    bpy.ops.object.mode_set(mode="POSE")
except:
    pass

for this_bone_name, this_bone_dict in rig_constraint_dict_of_dicts.items():
    print(f"---Setting constraints for bone:{this_bone_name}---")

    for (
        this_constraint_name,
        this_constraint_target_empty_name,
    ) in this_bone_dict.items():
        print(
            f"constraint: {this_constraint_name} with target:{this_constraint_target_empty_name}"
        )
        print("grab bone")
        this_bone = armature.pose.bones[this_bone_name]
        print("apply bone")
        this_constraint = this_bone.constraints.new(type=this_constraint_name)
        this_constraint.name = this_constraint_name
        this_constraint.target = bpy.data.objects[
            this_constraint_target_empty_name
        ]  # point constraint at relevant empty object
