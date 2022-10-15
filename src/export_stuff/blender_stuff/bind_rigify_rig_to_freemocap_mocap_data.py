import bpy
import addon_utils

import numpy as np
from pathlib import Path
import json

#######################################################################
##% Activate necessary addons
addon_utils.enable("io_import_images_as_planes")
addon_utils.enable("rigify")

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
# path_to_data_folder = Path("/Users/jon/Dropbox/FreeMoCapProject/FreeMocap_Data/")
path_to_data_folder = Path(
    r"D:\Dropbox\FreeMoCapProject\teddy_animation\FreeMocap_Data"
)

session_id = "sesh_2022-10-09_13_55_45_calib_and_take_1_alpha"

session_path = path_to_data_folder / session_id
path_to_data_arrays_folder = session_path / "output_data"
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

# path_to_mixamo_fbx = r"/Users/jon/Dropbox/FreeMoCapProject/teddy_animation/mixamo_binding_stuff/mixamo_mannequin_fbx_Ch36_nonPBR.fbx"
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

    number_of_videos = len(list(vidFolderPath.glob("*.mp4")))

    vid_location_scale = 1

    for (
        vid_number,
        thisVidPath,
    ) in enumerate(vidFolderPath.glob("*.mp4")):
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
print(f"Loading rigify human meta-rig")
bpy.ops.object.armature_human_metarig_add()
human_metarig = bpy.context.active_object
freemocap_origin_axes.rotation_euler[2] = np.pi
##################
### Scale armature


rigify_bone_to_skeleton_segment_name_correspondance = {
    "lower_spine": ["spine", "spine.001"],
    "upper_spine": ["spine.002", "spine.003"],
    "head": ["spine.004", "spine.005", "spine.006"],
    "left_hand": ["hand.L"],
    "left_forearm": ["forearm.L"],
    "left_upper_arm": ["upper_arm.L"],
    "right_hand": ["hand.R"],
    "right_forearm": ["forearm.R"],
    "right_upper_arm": ["upper_arm.R"],
    "left_thigh": ["thigh.L"],
    "left_calf": ["shin.L"],
    "left_foot": ["foot.L"],
    "right_thigh": ["thigh.R"],
    "right_calf": ["shin.R"],
    "right_foot": ["foot.R"],
}

try:
    bpy.ops.object.mode_set(mode="EDIT")
except:
    pass

for (
    segment_name,
    rigify_bones_list,
) in rigify_bone_to_skeleton_segment_name_correspondance.items():
    print(
        f"segment: {segment_name}, length: {skeleton_segment_lengths_dict[segment_name]['median']:.3f}mm"
    )

    for rigify_bone_name in rigify_bones_list:
        segment_length = (
            skeleton_segment_lengths_dict[segment_name]["median"]
            / len(rigify_bones_list)
        ) * 0.001
        print(f"setting {rigify_bone_name} length to: {segment_length:.3f} m")
        human_metarig.data.edit_bones[rigify_bone_name].length = segment_length


##also, make the face bone tiny so it's centered on the head
human_metarig.data.edit_bones["face"].length = 0.01

########################
### Constrain mixamo bones to track empty locations


rig_constraint_dict_of_dicts = {
    "spine": {
        "COPY_LOCATION": {"target": "hip_center"},
    },
    "spine.003": {
        "IK": {"target": "neck_center", "chain_length": 4},
    },
    "spine.004": {
        "COPY_LOCATION": {"target": "neck_center"},
    },
    "spine.006": {
        "IK": {"target": "head_center", "chain_length": 2},
    },
    "face": {
        "COPY_LOCATION": {"target": "head_center"},
        "DAMPED_TRACK": {
            "target": "mouth_left",
            "track_axis": "TRACK_Z",
            "influence": 1.0,
        },
        "DAMPED_TRACK.001": {
            "target": "mouth_left",
            "track_axis": "TRACK_Z",
            "influence": 0.5,
        },
    },
    "shoulder.R": {
        "DAMPED_TRACK": {"target": "right_shoulder"},
    },
    "upper_arm.R": {
        "DAMPED_TRACK": {"target": "right_elbow"},
    },
    "forearm.R": {
        "DAMPED_TRACK": {"target": "right_wrist"},
    },
    "hand.R": {
        "DAMPED_TRACK": {"target": "right_index"},
    },
    "shoulder.L": {
        "DAMPED_TRACK": {"target": "left_shoulder"},
    },
    "upper_arm.L": {
        "DAMPED_TRACK": {"target": "left_elbow"},
    },
    "forearm.L": {
        "DAMPED_TRACK": {"target": "left_wrist"},
    },
    "hand.L": {
        "DAMPED_TRACK": {"target": "left_index"},
    },
    "thigh.R": {
        "DAMPED_TRACK": {"target": "right_knee"},
    },
    "shin.R": {
        "DAMPED_TRACK": {"target": "right_ankle"},
    },
    "foot.R": {
        "DAMPED_TRACK": {"target": "right_foot_index"},
    },
    "thigh.L": {
        "DAMPED_TRACK": {"target": "left_knee"},
    },
    "shin.L": {
        "DAMPED_TRACK": {"target": "left_ankle"},
    },
    "foot.L": {
        "DAMPED_TRACK": {"target": "left_foot_index"},
    },
}

####
#### Constrain bones to empties
####

# loop through dictionary applying  constraints
try:
    bpy.ops.object.mode_set(mode="POSE")
except:
    pass

for bone_name, bone_dict in rig_constraint_dict_of_dicts.items():
    print(f"---Setting constraints for bone:{bone_name}---")

    for (
        constraint_name,
        constrain_parameters_dict,
    ) in bone_dict.items():
        constraint_name = constraint_name.split(".")[
            0
        ]  # for duplicated constraints, named `[constraint_name].001`, etc
        print(
            f"constraint: {constraint_name} with parameters:{constrain_parameters_dict}"
        )

        bone = human_metarig.pose.bones[bone_name]
        print(f"bone: {bone.name}")

        constraint = bone.constraints.new(type=constraint_name)
        print(f"constraint: {constraint.name}")
        # constraint.name = constraint_name
        constraint.target = bpy.data.objects[
            constrain_parameters_dict["target"]
        ]  # point constraint at relevant empty object
        print(f"constraint.target: {constraint.target.name}")

        if "influence" in constrain_parameters_dict:
            constraint.influence = constrain_parameters_dict["influence"]
            print(f"constraint.influence: {constraint.influence}")

        if constraint_name == "IK":
            constraint.chain_count = constrain_parameters_dict["chain_length"]
            print(f"constraint.chain_count: {constraint.chain_count}")

        if constraint_name == "LOCKED_TRACK":
            constraint.track_axis = constrain_parameters_dict["track_axis"]
            constraint.lock_axis = constrain_parameters_dict["lock_axis"]
            print(f"constraint.track_axis: {constraint.track_axis}")
            print(f"constraint.lock_axis: {constraint.lock_axis}")

        if constraint_name == "DAMPED_TRACK":
            if "track_axis" in constrain_parameters_dict:
                constraint.track_axis = constrain_parameters_dict["track_axis"]
                print(f"constraint.track_axis: {constraint.track_axis}")


# bpy.context.scene.frame_start = 500
# bpy.context.scene.frame_current = 500
