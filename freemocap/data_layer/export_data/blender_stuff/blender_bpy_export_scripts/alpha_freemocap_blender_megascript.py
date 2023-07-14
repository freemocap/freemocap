import sys
from pathlib import Path

import bpy
import numpy as np

print(" - Starting (alpha) blender megascript - ")

#######################################################################
##% Activate necessary addons
bpy.ops.preferences.addon_enable(module="io_import_images_as_planes")
bpy.ops.preferences.addon_enable(module="rigify")

#######################################################################


def get_video_paths(path_to_video_folder: Path) -> list:
    """Search the folder for 'mp4' files (case insensitive) and return them as a list"""

    list_of_video_paths = list(Path(path_to_video_folder).glob("*.mp4")) + list(
        Path(path_to_video_folder).glob("*.MP4")
    )
    unique_list_of_video_paths = get_unique_list(list_of_video_paths)

    return unique_list_of_video_paths


def get_unique_list(list: list) -> list:
    """Return a list of the unique elements from input list"""
    unique_list = []
    [unique_list.append(clip) for clip in list if clip not in unique_list]

    return unique_list


try:
    ##% Session path
    # #get session path as command line argument
    argv = sys.argv
    argv = argv[argv.index("--") + 1 :]
    session_path = argv[0]

    blend_file_save_path = argv[1]
    if len(argv) > 2:
        good_clean_frame_number = int(argv[2])
    else:
        good_clean_frame_number = 0
except:
    print("we appear to be running from the Blender Scripting tab! Manually enter your `session_path` at line 23")
    session_path = Path(
        r"C:\Users\jonma\Dropbox\FreeMoCapProject\FreeMocap_Data\sesh_2022-05-07_17_15_05_pupil_wobble_juggle_0"
    )
    good_clean_frame_number = 3341

print(f"Using session path - {str(session_path)}")
session_path = Path(session_path)

path_to_mediapipe_npy = (
    session_path / "output_data" / "raw_data" / "mediapipe3dData_numFrames_numTrackedPoints_spatialXYZ.npy"
)
path_to_mediapipe_3d_reproj = (
    session_path / "output_data" / "raw_data" / "mediapipe3dData_numFrames_numTrackedPoints_reprojectionError.npy"
)

print(f"Loading mediapipe data from {path_to_mediapipe_npy}")
#######################################################################
# %% load mediapipe data
# %%
print("loading data")
# %%
print(f"Loading mediapipe data from {path_to_mediapipe_npy}")
mediapipe_skel_fr_mar_dim = np.load(str(path_to_mediapipe_npy))
print("mediapipe_skel_fr_mar_dim.shape", mediapipe_skel_fr_mar_dim.shape)
mediapipe_skel_fr_mar_dim = mediapipe_skel_fr_mar_dim / 1000  # convert to meters

print(f"Loading mediapipe reprojection error data from {path_to_mediapipe_3d_reproj}")
mediapipe_reprojection_error_fr_mar = np.load(str(path_to_mediapipe_3d_reproj))
print(f"mediapipe_reprojection_error_fr_mar.shape = {mediapipe_reprojection_error_fr_mar.shape}")

body_marker_range = np.arange(0, 33)
right_hand_marker_range = np.arange(33, 33 + 21)
left_hand_marker_range = np.arange(33 + 21, 33 + 21 + 21)
face_marker_range = np.arange(left_hand_marker_range[-1], mediapipe_skel_fr_mar_dim.shape[1])

body_skel_fr_mar_dim = mediapipe_skel_fr_mar_dim[
    :,
    body_marker_range,
    :,
]
right_hand_fr_mar_dim = mediapipe_skel_fr_mar_dim[
    :,
    right_hand_marker_range,
    :,
]
left_hand_fr_mar_dim = mediapipe_skel_fr_mar_dim[
    :,
    left_hand_marker_range,
    :,
]
face_fr_mar_dim = mediapipe_skel_fr_mar_dim[
    :,
    face_marker_range,
    :,
]

# %% Session Specific stuff
number_of_frames = mediapipe_skel_fr_mar_dim.shape[0]
start_frame = 1
end_frame = number_of_frames

bpy.context.scene.frame_start = start_frame
bpy.context.scene.frame_end = end_frame

########################
## Find Good Clean Frame with some fiddly nonsense
if good_clean_frame_number == 0:
    frame_nan_counts = []
    frame_mean_reproj_error = []

    for this_frame in range(mediapipe_skel_fr_mar_dim.shape[0]):
        frame_nan_counts.append(np.sum(np.isnan(mediapipe_skel_fr_mar_dim[this_frame, :, 0])))
        frame_mean_reproj_error.append(np.nanmean(mediapipe_reprojection_error_fr_mar[this_frame, :]))

    nan_times_vis = np.array(frame_nan_counts) * np.array(frame_mean_reproj_error)
    num_frames = len(frame_nan_counts)
    # nan_times_vis[0:int(num_frames/5)] = np.nanmax(nan_times_vis)
    # nan_times_vis[-int(num_frames/5):-1] = np.nanmax(nan_times_vis)

    good_clean_frame_number = np.nanargmin(
        nan_times_vis
    )  # the frame with the fewest nans (i.e. hopefully a frame where all tracked points are visible)

print(f"----good_clean_frame_number: {good_clean_frame_number}----")

#######################################################################
# %% Mediapipe tracked point names
mediapipe_tracked_point_names = [
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
    "right_hand_wrist",
    "right_hand_thumb_cmc",
    "right_hand_thumb_mcp",
    "right_hand_thumb_ip",
    "right_hand_thumb_tip",
    "right_hand_index_finger_mcp",
    "right_hand_index_finger_pip",
    "right_hand_index_finger_dip",
    "right_hand_index_finger_tip",
    "right_hand_middle_finger_mcp",
    "right_hand_middle_finger_pip",
    "right_hand_middle_finger_dip",
    "right_hand_middle_finger_tip",
    "right_hand_ring_finger_mcp",
    "right_hand_ring_finger_pip",
    "right_hand_ring_finger_dip",
    "right_hand_ring_finger_tip",
    "right_hand_pinky_finger_mcp",
    "right_hand_pinky_finger_pip",
    "right_hand_pinky_finger_dip",
    "right_hand_pinky_finger_tip",
    "left_hand_wrist",
    "left_hand_thumb_cmc",
    "left_hand_thumb_mcp",
    "left_hand_thumb_ip",
    "left_hand_thumb_tip",
    "left_hand_index_finger_mcp",
    "left_hand_index_finger_pip",
    "left_hand_index_finger_dip",
    "left_hand_index_finger_tip",
    "left_hand_middle_finger_mcp",
    "left_hand_middle_finger_pip",
    "left_hand_middle_finger_dip",
    "left_hand_middle_finger_tip",
    "left_hand_ring_finger_mcp",
    "left_hand_ring_finger_pip",
    "left_hand_ring_finger_dip",
    "left_hand_ring_finger_tip",
    "left_hand_pinky_finger_mcp",
    "left_hand_pinky_finger_pip",
    "left_hand_pinky_finger_dip",
    "left_hand_pinky_finger_tip",
]

#####################################################################
## Blender Stuff
#####################################################################

try:
    #####################################################################
    ###%% clear scene
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

    #######################################################################
    # %% create world origin

    bpy.ops.object.empty_add(type="ARROWS")
    world_origin_axes = bpy.context.active_object
    world_origin_axes.name = "world_origin"  # will stay at origin
    # inspect(world_origin_axes, methods=True)

    bpy.ops.object.empty_add(type="ARROWS")
    freemocap_origin_axes = bpy.context.active_object
    freemocap_origin_axes.name = (
        "freemocap_origin_axes"  # will translate to put skelly on ground symmetric-ish about origin
    )

    #######################################################################
    # %% load empties
    print("loading {} empties on {} frames".format(len(mediapipe_tracked_point_names), number_of_frames))

    empty_size = 0.01

    for this_point_index, this_point_name in enumerate(mediapipe_tracked_point_names):
        print(f"loading {this_point_name}...")
        bpy.ops.object.empty_add(type="SPHERE")
        this_empty = bpy.context.active_object
        this_empty.name = this_point_name

        if "face" in this_point_name:
            this_empty.scale = [empty_size / 4] * 3
        if "hand" in this_point_name:
            this_empty.scale = [empty_size / 2] * 3
        else:
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
    left_ear_index = 7
    right_ear_index = 8
    #######################################################################
    print("creating virtual markers")
    print("head_center - midway between left and right ears")
    hips_xyz = (mediapipe_skel_fr_mar_dim[:, left_ear_index, :] + mediapipe_skel_fr_mar_dim[:, right_ear_index, :]) / 2
    bpy.ops.object.empty_add(type="SPHERE")
    this_empty = bpy.context.active_object
    this_empty.name = "head_center"
    this_empty.scale = [empty_size] * 3
    this_empty.parent = freemocap_origin_axes
    mediapipe_tracked_point_names.append(this_empty.name)

    for frame_num in range(end_frame):
        this_empty.location = [
            hips_xyz[frame_num, 0],
            hips_xyz[frame_num, 1],
            hips_xyz[frame_num, 2],
        ]
        this_empty.keyframe_insert(data_path="location", frame=frame_num)

    print("neck_center - midway between left and right shoulders")
    left_shoulder_index = 11
    right_shoulder_index = 12
    neck_xyz = (
        mediapipe_skel_fr_mar_dim[:, left_shoulder_index, :] + mediapipe_skel_fr_mar_dim[:, right_shoulder_index, :]
    ) / 2
    bpy.ops.object.empty_add(type="PLAIN_AXES")
    this_empty = bpy.context.active_object
    this_empty.name = "neck_center"
    this_empty.scale = [empty_size] * 3
    this_empty.parent = freemocap_origin_axes
    mediapipe_tracked_point_names.append(this_empty.name)

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
    hips_xyz = (mediapipe_skel_fr_mar_dim[:, left_hip_index, :] + mediapipe_skel_fr_mar_dim[:, right_hip_index, :]) / 2
    bpy.ops.object.empty_add(type="PLAIN_AXES")
    this_empty = bpy.context.active_object
    this_empty.name = "hip_center"
    this_empty.scale = [empty_size] * 3
    this_empty.parent = freemocap_origin_axes
    mediapipe_tracked_point_names.append(this_empty.name)
    rig_constraint_dict_of_dicts = {
        "spine": {
            "COPY_LOCATION": "hip_center",
            "STRETCH_TO": "chest_center",
        },
        "spine.001": {
            "STRETCH_TO": "neck_center",
        },
        "spine.002": {
            "STRETCH_TO": "head_center",
        },
        "spine.003": {
            "STRETCH_TO": "nose",
        },
        "pelvis.L": {
            "STRETCH_TO": "left_hip",
        },
        "thigh.L": {
            "COPY_LOCATION": "left_hip",
            "STRETCH_TO": "left_knee",
        },
        "shin.L": {
            "STRETCH_TO": "left_ankle",
        },
        "foot.L": {
            "STRETCH_TO": "left_foot_index",
        },
        "heel.02.L": {
            "STRETCH_TO": "left_ankle",
        },
        "shoulder.L": {
            "COPY_LOCATION": "neck_center",
            "STRETCH_TO": "left_shoulder",
        },
        "upper_arm.L": {
            "STRETCH_TO": "left_elbow",
        },
        "forearm.L": {
            "STRETCH_TO": "left_wrist",
        },
        "hand.L": {
            "STRETCH_TO": "left_index",
        },
        "pelvis.R": {
            "STRETCH_TO": "right_hip",
        },
        "thigh.R": {
            "COPY_LOCATION": "right_hip",
            "STRETCH_TO": "right_knee",
        },
        "shin.R": {
            "STRETCH_TO": "right_ankle",
        },
        "foot.R": {
            "STRETCH_TO": "right_foot_index",
        },
        "heel.02.R": {
            "STRETCH_TO": "right_ankle",
        },
        "shoulder.R": {
            "COPY_LOCATION": "neck_center",
            "STRETCH_TO": "right_shoulder",
        },
        "upper_arm.R": {
            "STRETCH_TO": "right_elbow",
        },
        "forearm.R": {
            "STRETCH_TO": "right_wrist",
        },
        "hand.R": {
            "STRETCH_TO": "right_index",
        },
        "thumb.01.R": {
            "COPY_LOCATION": "right_wrist",
            "STRETCH_TO": "right_hand_thumb_mcp",
        },
        "thumb.02.R": {
            "STRETCH_TO": "right_hand_thumb_ip",
        },
        "thumb.02.R": {
            "STRETCH_TO": "right_hand_thumb_tip",
        },
        "palm.01.R": {
            "COPY_LOCATION": "right_wrist",
            "STRETCH_TO": "right_hand_index_finger_mcp",
        },
        "f_index.01.R": {
            "STRETCH_TO": "right_hand_index_finger_pip",
        },
        "f_index.02.R": {
            "STRETCH_TO": "right_hand_index_finger_dip",
        },
        "f_index.03.R": {
            "STRETCH_TO": "right_hand_index_finger_tip",
        },
        "palm.02.R": {
            "COPY_LOCATION": "right_wrist",
            "STRETCH_TO": "right_hand_middle_finger_mcp",
        },
        "f_middle.01.R": {
            "STRETCH_TO": "right_hand_middle_finger_pip",
        },
        "f_middle.02.R": {
            "STRETCH_TO": "right_hand_middle_finger_dip",
        },
        "f_middle.03.R": {
            "STRETCH_TO": "right_hand_middle_finger_tip",
        },
        "palm.03.R": {
            "COPY_LOCATION": "right_wrist",
            "STRETCH_TO": "right_hand_ring_finger_mcp",
        },
        "f_ring.01.R": {
            "STRETCH_TO": "right_hand_ring_finger_pip",
        },
        "f_ring.02.R": {
            "STRETCH_TO": "right_hand_ring_finger_dip",
        },
        "f_ring.03.R": {
            "STRETCH_TO": "right_hand_ring_finger_tip",
        },
        "palm.04.R": {
            "COPY_LOCATION": "right_wrist",
            "STRETCH_TO": "right_hand_pinky_finger_mcp",
        },
        "f_pinky.01.R": {
            "STRETCH_TO": "right_hand_pinky_finger_pip",
        },
        "f_pinky.02.R": {
            "STRETCH_TO": "right_hand_pinky_finger_dip",
        },
        "f_pinky.03.R": {
            "STRETCH_TO": "right_hand_pinky_finger_tip",
        },
        "thumb.01.L": {
            "COPY_LOCATION": "left_wrist",
            "STRETCH_TO": "left_hand_thumb_mcp",
        },
        "thumb.02.L": {
            "STRETCH_TO": "left_hand_thumb_ip",
        },
        "thumb.03.L": {
            "STRETCH_TO": "left_hand_thumb_tip",
        },
        "palm.01.L": {
            "COPY_LOCATION": "left_wrist",
            "STRETCH_TO": "left_hand_index_finger_mcp",
        },
        "f_index.01.L": {
            "STRETCH_TO": "left_hand_index_finger_pip",
        },
        "f_index.02.L": {
            "STRETCH_TO": "left_hand_index_finger_dip",
        },
        "f_index.03.L": {
            "STRETCH_TO": "left_hand_index_finger_tip",
        },
        "palm.02.L": {
            "COPY_LOCATION": "left_wrist",
            "STRETCH_TO": "left_hand_middle_finger_mcp",
        },
        "f_middle.01.L": {
            "STRETCH_TO": "left_hand_middle_finger_pip",
        },
        "f_middle.02.L": {
            "STRETCH_TO": "left_hand_middle_finger_dip",
        },
        "f_middle.03.L": {
            "STRETCH_TO": "left_hand_middle_finger_tip",
        },
        "palm.03.L": {
            "COPY_LOCATION": "left_wrist",
            "STRETCH_TO": "left_hand_ring_finger_mcp",
        },
        "f_ring.01.L": {
            "STRETCH_TO": "left_hand_ring_finger_pip",
        },
        "f_ring.02.L": {
            "STRETCH_TO": "left_hand_ring_finger_dip",
        },
        "f_ring.03.L": {
            "STRETCH_TO": "left_hand_ring_finger_tip",
        },
        "palm.04.L": {
            "COPY_LOCATION": "left_wrist",
            "STRETCH_TO": "left_hand_pinky_finger_mcp",
        },
        "f_pinky.01.L": {
            "STRETCH_TO": "left_hand_pinky_finger_pip",
        },
        "f_pinky.02.L": {
            "STRETCH_TO": "left_hand_pinky_finger_dip",
        },
        "f_pinky.03.L": {
            "STRETCH_TO": "left_hand_pinky_finger_tip",
        },
    }

    # loop through dictionary applying  constraints
    try:
        bpy.ops.object.mode_set(mode="POSE")
    except:
        pass

        for frame_num in range(end_frame):
            this_empty.location = [
                hips_xyz[frame_num, 0],
                hips_xyz[frame_num, 1],
                hips_xyz[frame_num, 2],
            ]
            this_empty.keyframe_insert(data_path="location", frame=frame_num)

        print("chest_center - mean of R/L shoulders and R/L hips")
        chest_xyz = (neck_xyz + hips_xyz) / 2
        bpy.ops.object.empty_add(type="PLAIN_AXES")
        this_empty = bpy.context.active_object
        this_empty.name = "chest_center"
        this_empty.scale = [empty_size] * 3
        this_empty.parent = freemocap_origin_axes
        mediapipe_tracked_point_names.append(this_empty.name)

        for frame_num in range(end_frame):
            this_empty.location = [
                chest_xyz[frame_num, 0],
                chest_xyz[frame_num, 1],
                chest_xyz[frame_num, 2],
            ]
            this_empty.keyframe_insert(data_path="location", frame=frame_num)

        print("Done loading empties :D")

        ######################################################################
        ## Fit Rigify metarig armatures to empties

        bpy.context.scene.frame_set(good_clean_frame_number)

        # each bone  name has to match one in the Blender Rigify Human Metarig, or it will be ignored
        metarig_bone_empty_pairs_dict_of_dicts = {
            "nose.001": {
                "head": "head_center",
                "tail": "nose",
            },
            "nose.L.001": {
                "head": "nose",
                "tail": "left_eye_inner",
            },
            "eye.L": {
                "head": "left_eye_inner",
                "tail": "left_eye",
            },
            "lid.B.L": {
                "head": "left_eye",
                "tail": "left_eye_outer",
            },
            "ear.L": {
                "head": "left_eye_outer",
                "tail": "left_ear",
            },
            "nose.R.001": {
                "head": "nose",
                "tail": "right_eye_inner",
            },
            "eye.R": {
                "head": "right_eye_inner",
                "tail": "right_eye",
            },
            "lid.B.R": {
                "head": "right_eye",
                "tail": "right_eye_outer",
            },
            "ear.R": {
                "head": "right_eye_outer",
                "tail": "right_ear",
            },
            "lip.T.R": {
                "head": "nose",
                "tail": "mouth_right",
            },
            "lip.B.R": {
                "head": "mouth_right",
                "tail": "mouth_left",
            },
            "lip.T.L": {
                "head": "nose",
                "tail": "mouth_left",
            },
            "hand.L": {
                "head": "left_wrist",
                "tail": "left_index",
            },
            "forearm.L": {
                "head": "left_elbow",
                "tail": "left_wrist",
            },
            "upper_arm.L": {
                "head": "left_shoulder",
                "tail": "left_elbow",
            },
            "shoulder.L": {
                "head": "neck_center",
                "tail": "left_shoulder",
            },
            "hand.R": {
                "head": "right_wrist",
                "tail": "right_index",
            },
            "forearm.R": {
                "head": "right_elbow",
                "tail": "right_wrist",
            },
            "upper_arm.R": {
                "head": "right_shoulder",
                "tail": "right_elbow",
            },
            "shoulder.R": {
                "head": "neck_center",
                "tail": "right_shoulder",
            },
            "thigh.L": {
                "head": "left_hip",
                "tail": "left_knee",
            },
            "shin.L": {
                "head": "left_knee",
                "tail": "left_ankle",
            },
            "heel.02.L": {
                "head": "left_heel",
                "tail": "left_ankle",
            },
            "foot.L": {
                "head": "left_ankle",
                "tail": "left_foot_index",
            },
            "toe.L": {
                "head": "left_foot_index",
                "tail": "left_heel",
            },
            "thigh.R": {
                "head": "right_hip",
                "tail": "right_knee",
            },
            "shin.R": {
                "head": "right_knee",
                "tail": "right_ankle",
            },
            "heel.02.R": {
                "head": "right_heel",
                "tail": "right_ankle",
            },
            "foot.R": {
                "head": "right_ankle",
                "tail": "right_foot_index",
            },
            "toe.R": {
                "head": "right_foot_index",
                "tail": "right_heel",
            },
            "pelvis.L": {
                "head": "hip_center",
                "tail": "left_hip",
            },
            "pelvis.R": {
                "head": "hip_center",
                "tail": "right_hip",
            },
            "spine": {
                "head": "hip_center",
                "tail": "chest_center",
            },
            "spine.001": {
                "head": "chest_center",
                "tail": "neck_center",
            },
            "spine.002": {
                "head": "neck_center",
                "tail": "head_center",
            },
            "spine.003": {
                "head": "head_center",
                "tail": "nose",
            },
            "palm.01.R": {
                "head": "right_wrist",
                "tail": "right_hand_index_finger_mcp",
            },
            "palm.02.R": {
                "head": "right_wrist",
                "tail": "right_hand_middle_finger_mcp",
            },
            "palm.03.R": {
                "head": "right_wrist",
                "tail": "right_hand_ring_finger_mcp",
            },
            "palm.04.R": {
                "head": "right_wrist",
                "tail": "right_hand_pinky_finger_mcp",
            },
            "thumb.01.R": {
                "head": "right_wrist",
                "tail": "right_hand_thumb_mcp",
            },
            "thumb.02.R": {
                "head": "right_hand_thumb_mcp",
                "tail": "right_hand_thumb_ip",
            },
            "thumb.03.R": {
                "head": "right_hand_thumb_ip",
                "tail": "right_hand_thumb_tip",
            },
            "f_index.01.R": {
                "head": "right_hand_index_finger_mcp",
                "tail": "right_hand_index_finger_pip",
            },
            "f_index.02.R": {
                "head": "right_hand_index_finger_pip",
                "tail": "right_hand_index_finger_dip",
            },
            "f_index.03.R": {
                "head": "right_hand_index_finger_dip",
                "tail": "right_hand_index_finger_tip",
            },
            "f_middle.01.R": {
                "head": "right_hand_middle_finger_mcp",
                "tail": "right_hand_middle_finger_pip",
            },
            "f_middle.02.R": {
                "head": "right_hand_middle_finger_pip",
                "tail": "right_hand_middle_finger_dip",
            },
            "f_middle.03.R": {
                "head": "right_hand_middle_finger_dip",
                "tail": "right_hand_middle_finger_tip",
            },
            "f_ring.01.R": {
                "head": "right_hand_ring_finger_mcp",
                "tail": "right_hand_ring_finger_pip",
            },
            "f_ring.02.R": {
                "head": "right_hand_ring_finger_pip",
                "tail": "right_hand_ring_finger_dip",
            },
            "f_ring.03.R": {
                "head": "right_hand_ring_finger_dip",
                "tail": "right_hand_ring_finger_tip",
            },
            "f_pinky.01.R": {
                "head": "right_hand_pinky_finger_mcp",
                "tail": "right_hand_pinky_finger_pip",
            },
            "f_pinky.02.R": {
                "head": "right_hand_pinky_finger_pip",
                "tail": "right_hand_pinky_finger_dip",
            },
            "f_pinky.03.R": {
                "head": "right_hand_pinky_finger_dip",
                "tail": "right_hand_pinky_finger_tip",
            },
            "thumb.01.L": {
                "head": "left_wrist",
                "tail": "left_hand_thumb_mcp",
            },
            "thumb.02.L": {
                "head": "left_hand_thumb_mcp",
                "tail": "left_hand_thumb_ip",
            },
            "thumb.03.L": {
                "head": "left_hand_thumb_ip",
                "tail": "left_hand_thumb_tip",
            },
            "palm.01.L": {
                "head": "left_wrist",
                "tail": "left_hand_index_finger_mcp",
            },
            "palm.02.L": {
                "head": "left_wrist",
                "tail": "left_hand_middle_finger_mcp",
            },
            "palm.03.L": {
                "head": "left_wrist",
                "tail": "left_hand_ring_finger_mcp",
            },
            "palm.04.L": {
                "head": "left_wrist",
                "tail": "left_hand_pinky_finger_mcp",
            },
            "f_index.01.L": {
                "head": "left_hand_index_finger_mcp",
                "tail": "left_hand_index_finger_pip",
            },
            "f_index.02.L": {
                "head": "left_hand_index_finger_pip",
                "tail": "left_hand_index_finger_dip",
            },
            "f_index.03.L": {
                "head": "left_hand_index_finger_dip",
                "tail": "left_hand_index_finger_tip",
            },
            "f_middle.01.L": {
                "head": "left_hand_middle_finger_mcp",
                "tail": "left_hand_middle_finger_pip",
            },
            "f_middle.02.L": {
                "head": "left_hand_middle_finger_pip",
                "tail": "left_hand_middle_finger_dip",
            },
            "f_middle.03.L": {
                "head": "left_hand_middle_finger_dip",
                "tail": "left_hand_middle_finger_tip",
            },
            "f_ring.01.L": {
                "head": "left_hand_ring_finger_mcp",
                "tail": "left_hand_ring_finger_pip",
            },
            "f_ring.02.L": {
                "head": "left_hand_ring_finger_pip",
                "tail": "left_hand_ring_finger_dip",
            },
            "f_ring.03.L": {
                "head": "left_hand_ring_finger_dip",
                "tail": "left_hand_ring_finger_tip",
            },
            "f_pinky.01.L": {
                "head": "left_hand_pinky_finger_mcp",
                "tail": "left_hand_pinky_finger_pip",
            },
            "f_pinky.02.L": {
                "head": "left_hand_pinky_finger_pip",
                "tail": "left_hand_pinky_finger_dip",
            },
            "f_pinky.03.L": {
                "head": "left_hand_pinky_finger_dip",
                "tail": "left_hand_pinky_finger_tip",
            },
        }

        # %% create metarig
        bpy.ops.object.armature_human_metarig_add()
        this_metarig = bpy.context.active_object

        # %% loop through dictionary - set head and tail of each bone's to the relevant empty
        # bpy.ops.object.posemode_toggle()
        try:
            bpy.ops.object.mode_set(mode="EDIT")
        except:
            pass

        for this_bone in list(this_metarig.data.bones):
            this_bone_name = this_bone.name
            print(f"--{this_bone_name}--")

            this_edit_bone = this_metarig.data.edit_bones[
                this_bone_name
            ]  # note this is using EDIT_bones, not regular bones b/c blender is a wild wacky place

            if this_bone_name in metarig_bone_empty_pairs_dict_of_dicts:
                this_bone_dict = metarig_bone_empty_pairs_dict_of_dicts[this_bone_name]

                this_head_empty_name = this_bone_dict["head"]
                this_tail_empty_name = this_bone_dict["tail"]
                print(
                    "setting (bone:head->tail){}:{}->{})".format(
                        this_bone_name, this_head_empty_name, this_tail_empty_name
                    )
                )

                if this_tail_empty_name is not None:
                    print(
                        f"setting bone: {this_bone_name}: head: {bpy.data.objects[this_head_empty_name].location}, tail: {bpy.data.objects[this_tail_empty_name].location}"
                    )
                    this_edit_bone.head = bpy.data.objects[this_head_empty_name].location
                    this_edit_bone.tail = bpy.data.objects[this_tail_empty_name].location
                else:  # remove bones with no tail (and/or head) until we figure out a better plan
                    print(f"removing bone: {this_bone_name}")
                    this_metarig.data.edit_bones.remove(this_edit_bone)
            else:
                print(f"removing bone: {this_bone_name}")
                this_metarig.data.edit_bones.remove(this_edit_bone)

        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except:
            pass

        #######################################################
        #### Damped track bones to empties
        bpy.ops.object.mode_set(mode="OBJECT")
        armature_name = "metarig"
        this_armature = bpy.data.objects[armature_name]

        rig_constraint_dict_of_dicts = {
            "nose.001": {
                "COPY_LOCATION": "head_center",
                "DAMPED_TRACK": "nose",
            },
            "nose.L.001": {
                "DAMPED_TRACK": "left_eye_inner",
            },
            "eye.L": {
                "DAMPED_TRACK": "left_eye",
            },
            "lid.B.L": {
                "DAMPED_TRACK": "left_eye_outer",
            },
            "ear.L": {
                "DAMPED_TRACK": "left_ear",
            },
            "nose.R.001": {
                "DAMPED_TRACK": "right_eye_inner",
            },
            "eye.R": {
                "DAMPED_TRACK": "right_eye",
            },
            "lid.B.R": {
                "DAMPED_TRACK": "right_eye_outer",
            },
            "ear.R": {
                "DAMPED_TRACK": "right_ear",
            },
            "lip.T.R": {
                "DAMPED_TRACK": "mouth_right",
            },
            "lip.B.R": {
                "DAMPED_TRACK": "mouth_left",
            },
            "lip.T.L": {
                "DAMPED_TRACK": "nose",
            },
            "spine": {
                "COPY_LOCATION": "hip_center",
                "DAMPED_TRACK": "chest_center",
            },
            "spine.001": {
                "DAMPED_TRACK": "neck_center",
            },
            "spine.002": {
                "DAMPED_TRACK": "head_center",
            },
            "spine.003": {
                "DAMPED_TRACK": "nose",
            },
            "pelvis.L": {
                "DAMPED_TRACK": "left_hip",
            },
            "thigh.L": {
                "COPY_LOCATION": "left_hip",
                "DAMPED_TRACK": "left_knee",
            },
            "shin.L": {
                "DAMPED_TRACK": "left_ankle",
            },
            "foot.L": {
                "DAMPED_TRACK": "left_foot_index",
            },
            "heel.02.L": {
                "DAMPED_TRACK": "left_ankle",
            },
            "shoulder.L": {
                "COPY_LOCATION": "neck_center",
                "DAMPED_TRACK": "left_shoulder",
            },
            "upper_arm.L": {
                "DAMPED_TRACK": "left_elbow",
            },
            "forearm.L": {
                "DAMPED_TRACK": "left_wrist",
            },
            "hand.L": {
                "DAMPED_TRACK": "left_index",
            },
            "pelvis.R": {
                "DAMPED_TRACK": "right_hip",
            },
            "thigh.R": {
                "COPY_LOCATION": "right_hip",
                "DAMPED_TRACK": "right_knee",
            },
            "shin.R": {
                "DAMPED_TRACK": "right_ankle",
            },
            "foot.R": {
                "DAMPED_TRACK": "right_foot_index",
            },
            "heel.02.R": {
                "DAMPED_TRACK": "right_ankle",
            },
            "shoulder.R": {
                "COPY_LOCATION": "neck_center",
                "DAMPED_TRACK": "right_shoulder",
            },
            "upper_arm.R": {
                "DAMPED_TRACK": "right_elbow",
            },
            "forearm.R": {
                "DAMPED_TRACK": "right_wrist",
            },
            "hand.R": {
                "DAMPED_TRACK": "right_index",
            },
            "thumb.01.R": {
                "COPY_LOCATION": "right_wrist",
                "DAMPED_TRACK": "right_hand_thumb_mcp",
            },
            "thumb.02.R": {
                "DAMPED_TRACK": "right_hand_thumb_ip",
            },
            "thumb.02.R": {
                "DAMPED_TRACK": "right_hand_thumb_tip",
            },
            "palm.01.R": {
                "COPY_LOCATION": "right_wrist",
                "DAMPED_TRACK": "right_hand_index_finger_mcp",
            },
            "f_index.01.R": {
                "DAMPED_TRACK": "right_hand_index_finger_pip",
            },
            "f_index.02.R": {
                "DAMPED_TRACK": "right_hand_index_finger_dip",
            },
            "f_index.03.R": {
                "DAMPED_TRACK": "right_hand_index_finger_tip",
            },
            "palm.02.R": {
                "COPY_LOCATION": "right_wrist",
                "DAMPED_TRACK": "right_hand_middle_finger_mcp",
            },
            "f_middle.01.R": {
                "DAMPED_TRACK": "right_hand_middle_finger_pip",
            },
            "f_middle.02.R": {
                "DAMPED_TRACK": "right_hand_middle_finger_dip",
            },
            "f_middle.03.R": {
                "DAMPED_TRACK": "right_hand_middle_finger_tip",
            },
            "palm.03.R": {
                "COPY_LOCATION": "right_wrist",
                "DAMPED_TRACK": "right_hand_ring_finger_mcp",
            },
            "f_ring.01.R": {
                "DAMPED_TRACK": "right_hand_ring_finger_pip",
            },
            "f_ring.02.R": {
                "DAMPED_TRACK": "right_hand_ring_finger_dip",
            },
            "f_ring.03.R": {
                "DAMPED_TRACK": "right_hand_ring_finger_tip",
            },
            "palm.04.R": {
                "COPY_LOCATION": "right_wrist",
                "DAMPED_TRACK": "right_hand_pinky_finger_mcp",
            },
            "f_pinky.01.R": {
                "DAMPED_TRACK": "right_hand_pinky_finger_pip",
            },
            "f_pinky.02.R": {
                "DAMPED_TRACK": "right_hand_pinky_finger_dip",
            },
            "f_pinky.03.R": {
                "DAMPED_TRACK": "right_hand_pinky_finger_tip",
            },
            "thumb.01.L": {
                "COPY_LOCATION": "left_wrist",
                "DAMPED_TRACK": "left_hand_thumb_mcp",
            },
            "thumb.02.L": {
                "DAMPED_TRACK": "left_hand_thumb_ip",
            },
            "thumb.03.L": {
                "DAMPED_TRACK": "left_hand_thumb_tip",
            },
            "palm.01.L": {
                "COPY_LOCATION": "left_wrist",
                "DAMPED_TRACK": "left_hand_index_finger_mcp",
            },
            "f_index.01.L": {
                "DAMPED_TRACK": "left_hand_index_finger_pip",
            },
            "f_index.02.L": {
                "DAMPED_TRACK": "left_hand_index_finger_dip",
            },
            "f_index.03.L": {
                "DAMPED_TRACK": "left_hand_index_finger_tip",
            },
            "palm.02.L": {
                "COPY_LOCATION": "left_wrist",
                "DAMPED_TRACK": "left_hand_middle_finger_mcp",
            },
            "f_middle.01.L": {
                "DAMPED_TRACK": "left_hand_middle_finger_pip",
            },
            "f_middle.02.L": {
                "DAMPED_TRACK": "left_hand_middle_finger_dip",
            },
            "f_middle.03.L": {
                "DAMPED_TRACK": "left_hand_middle_finger_tip",
            },
            "palm.03.L": {
                "COPY_LOCATION": "left_wrist",
                "DAMPED_TRACK": "left_hand_ring_finger_mcp",
            },
            "f_ring.01.L": {
                "DAMPED_TRACK": "left_hand_ring_finger_pip",
            },
            "f_ring.02.L": {
                "DAMPED_TRACK": "left_hand_ring_finger_dip",
            },
            "f_ring.03.L": {
                "DAMPED_TRACK": "left_hand_ring_finger_tip",
            },
            "palm.04.L": {
                "COPY_LOCATION": "left_wrist",
                "DAMPED_TRACK": "left_hand_pinky_finger_mcp",
            },
            "f_pinky.01.L": {
                "DAMPED_TRACK": "left_hand_pinky_finger_pip",
            },
            "f_pinky.02.L": {
                "DAMPED_TRACK": "left_hand_pinky_finger_dip",
            },
            "f_pinky.03.L": {
                "DAMPED_TRACK": "left_hand_pinky_finger_tip",
            },
        }

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
                print(f"constraint: {this_constraint_name} with target:{this_constraint_target_empty_name}")
                print("grab bone")
                this_bone = this_armature.pose.bones[this_bone_name]
                print("apply bone")
                this_constraint = this_bone.constraints.new(type=this_constraint_name)
                this_constraint.name = this_constraint_name
                this_constraint.target = bpy.data.objects[
                    this_constraint_target_empty_name
                ]  # point constraint at relevant empty object

        ##############
        ## create extra bones

        extra_bone_empty_pairs_dict_of_dicts = {
            "hand.L": {
                "head": "left_wrist",
                "tail": "left_index",
            },
            "forearm.L": {
                "head": "left_elbow",
                "tail": "left_wrist",
            },
        }

        ###################################################################
        #### Create Stick Figure Mesh

        stick_figure_mesh_edge_pairs_dict_of_dicts = {
            "nose.001": {
                "head": "head_center",
                "tail": "nose",
            },
            "nose.L.001": {
                "head": "nose",
                "tail": "left_eye_inner",
            },
            "eye.L": {
                "head": "left_eye_inner",
                "tail": "left_eye",
            },
            "lid.B.L": {
                "head": "left_eye",
                "tail": "left_eye_outer",
            },
            "ear.L": {
                "head": "left_eye_outer",
                "tail": "left_ear",
            },
            "nose.R.001": {
                "head": "nose",
                "tail": "right_eye_inner",
            },
            "eye.R": {
                "head": "right_eye_inner",
                "tail": "right_eye",
            },
            "lid.B.R": {
                "head": "right_eye",
                "tail": "right_eye_outer",
            },
            "ear.R": {
                "head": "right_eye_outer",
                "tail": "right_ear",
            },
            "lip.T.R": {
                "head": "nose",
                "tail": "mouth_right",
            },
            "lip.B.R": {
                "head": "mouth_right",
                "tail": "mouth_left",
            },
            "lip.T.L": {
                "head": "nose",
                "tail": "mouth_left",
            },
            "forearm.L": {
                "head": "left_elbow",
                "tail": "left_wrist",
            },
            "upper_arm.L": {
                "head": "left_shoulder",
                "tail": "left_elbow",
            },
            "shoulder.L": {
                "head": "neck_center",
                "tail": "left_shoulder",
            },
            "forearm.R": {
                "head": "right_elbow",
                "tail": "right_wrist",
            },
            "upper_arm.R": {
                "head": "right_shoulder",
                "tail": "right_elbow",
            },
            "shoulder.R": {
                "head": "neck_center",
                "tail": "right_shoulder",
            },
            "thigh.L": {
                "head": "left_hip",
                "tail": "left_knee",
            },
            "shin.L": {
                "head": "left_knee",
                "tail": "left_ankle",
            },
            "heel.02.L": {
                "head": "left_heel",
                "tail": "left_ankle",
            },
            "foot.L": {
                "head": "left_ankle",
                "tail": "left_foot_index",
            },
            "toe.L": {
                "head": "left_foot_index",
                "tail": "left_heel",
            },
            "thigh.R": {
                "head": "right_hip",
                "tail": "right_knee",
            },
            "shin.R": {
                "head": "right_knee",
                "tail": "right_ankle",
            },
            "heel.02.R": {
                "head": "right_heel",
                "tail": "right_ankle",
            },
            "foot.R": {
                "head": "right_ankle",
                "tail": "right_foot_index",
            },
            "toe.R": {
                "head": "right_foot_index",
                "tail": "right_heel",
            },
            "pelvis.L": {
                "head": "hip_center",
                "tail": "left_hip",
            },
            "pelvis.R": {
                "head": "hip_center",
                "tail": "right_hip",
            },
            "spine": {
                "head": "hip_center",
                "tail": "chest_center",
            },
            "spine.001": {
                "head": "chest_center",
                "tail": "neck_center",
            },
            "spine.002": {
                "head": "neck_center",
                "tail": "head_center",
            },
            "spine.003": {
                "head": "head_center",
                "tail": "nose",
            },
            "palm.01.R": {
                "head": "right_wrist",
                "tail": "right_hand_index_finger_mcp",
            },
            "palm.02.R": {
                "head": "right_wrist",
                "tail": "right_hand_middle_finger_mcp",
            },
            "palm.03.R": {
                "head": "right_wrist",
                "tail": "right_hand_ring_finger_mcp",
            },
            "palm.04.R": {
                "head": "right_wrist",
                "tail": "right_hand_pinky_finger_mcp",
            },
            "thumb.01.R": {
                "head": "right_wrist",
                "tail": "right_hand_thumb_cmc",
            },
            "thumb.02.R": {
                "head": "right_hand_thumb_cmc",
                "tail": "right_hand_thumb_mcp",
            },
            "thumb.03.R": {
                "head": "right_hand_thumb_mcp",
                "tail": "right_hand_thumb_ip",
            },
            "thumb.04.R": {
                "head": "right_hand_thumb_ip",
                "tail": "right_hand_thumb_tip",
            },
            "f_index.01.R": {
                "head": "right_hand_index_finger_mcp",
                "tail": "right_hand_index_finger_pip",
            },
            "f_index.02.R": {
                "head": "right_hand_index_finger_pip",
                "tail": "right_hand_index_finger_dip",
            },
            "f_index.03.R": {
                "head": "right_hand_index_finger_dip",
                "tail": "right_hand_index_finger_tip",
            },
            "f_middle.01.R": {
                "head": "right_hand_middle_finger_mcp",
                "tail": "right_hand_middle_finger_pip",
            },
            "f_middle.02.R": {
                "head": "right_hand_middle_finger_pip",
                "tail": "right_hand_middle_finger_dip",
            },
            "f_middle.03.R": {
                "head": "right_hand_middle_finger_dip",
                "tail": "right_hand_middle_finger_tip",
            },
            "f_ring.01.R": {
                "head": "right_hand_ring_finger_mcp",
                "tail": "right_hand_ring_finger_pip",
            },
            "f_ring.02.R": {
                "head": "right_hand_ring_finger_pip",
                "tail": "right_hand_ring_finger_dip",
            },
            "f_ring.03.R": {
                "head": "right_hand_ring_finger_dip",
                "tail": "right_hand_ring_finger_tip",
            },
            "f_pinky.01.R": {
                "head": "right_hand_pinky_finger_mcp",
                "tail": "right_hand_pinky_finger_pip",
            },
            "f_pinky.02.R": {
                "head": "right_hand_pinky_finger_pip",
                "tail": "right_hand_pinky_finger_dip",
            },
            "f_pinky.03.R": {
                "head": "right_hand_pinky_finger_dip",
                "tail": "right_hand_pinky_finger_tip",
            },
            "thumb.01.L": {
                "head": "left_wrist",
                "tail": "left_hand_thumb_cmc",
            },
            "thumb.02.L": {
                "head": "left_hand_thumb_cmc",
                "tail": "left_hand_thumb_mcp",
            },
            "thumb.03.L": {
                "head": "left_hand_thumb_mcp",
                "tail": "left_hand_thumb_ip",
            },
            "thumb.04.L": {
                "head": "left_hand_thumb_ip",
                "tail": "left_hand_thumb_tip",
            },
            "palm.01.L": {
                "head": "left_wrist",
                "tail": "left_hand_index_finger_mcp",
            },
            "palm.02.L": {
                "head": "left_wrist",
                "tail": "left_hand_middle_finger_mcp",
            },
            "palm.03.L": {
                "head": "left_wrist",
                "tail": "left_hand_ring_finger_mcp",
            },
            "palm.04.L": {
                "head": "left_wrist",
                "tail": "left_hand_pinky_finger_mcp",
            },
            "f_index.01.L": {
                "head": "left_hand_index_finger_mcp",
                "tail": "left_hand_index_finger_pip",
            },
            "f_index.02.L": {
                "head": "left_hand_index_finger_pip",
                "tail": "left_hand_index_finger_dip",
            },
            "f_index.03.L": {
                "head": "left_hand_index_finger_dip",
                "tail": "left_hand_index_finger_tip",
            },
            "f_middle.01.L": {
                "head": "left_hand_middle_finger_mcp",
                "tail": "left_hand_middle_finger_pip",
            },
            "f_middle.02.L": {
                "head": "left_hand_middle_finger_pip",
                "tail": "left_hand_middle_finger_dip",
            },
            "f_middle.03.L": {
                "head": "left_hand_middle_finger_dip",
                "tail": "left_hand_middle_finger_tip",
            },
            "f_ring.01.L": {
                "head": "left_hand_ring_finger_mcp",
                "tail": "left_hand_ring_finger_pip",
            },
            "f_ring.02.L": {
                "head": "left_hand_ring_finger_pip",
                "tail": "left_hand_ring_finger_dip",
            },
            "f_ring.03.L": {
                "head": "left_hand_ring_finger_dip",
                "tail": "left_hand_ring_finger_tip",
            },
            "f_pinky.01.L": {
                "head": "left_hand_pinky_finger_mcp",
                "tail": "left_hand_pinky_finger_pip",
            },
            "f_pinky.02.L": {
                "head": "left_hand_pinky_finger_pip",
                "tail": "left_hand_pinky_finger_dip",
            },
            "f_pinky.03.L": {
                "head": "left_hand_pinky_finger_dip",
                "tail": "left_hand_pinky_finger_tip",
            },
        }

        mediapipe_virtual_markers_weights_dict = {
            "head_center": {"right_ear": 0.5, "left_ear": 0.5},
            "neck_center": {"right_shoulder": 0.5, "left_shoulder": 0.5},
            "hip_center": {"right_hip": 0.5, "left_hip": 0.5},
            "chest_center": {
                "right_shoulder": 0.25,
                "left_shoulder": 0.25,
                "right_hip": 0.25,
                "left_hip": 0.25,
            },
        }

        print("loading data as stick figure mesh \o/")
        #######################################################################

        # %% create virtual marker points (redundant from above, I think ? )

        current_frame = bpy.data.scenes[0].frame_current
        virtual_point_index_dict = {}
        for this_virtual_marker_dict in mediapipe_virtual_markers_weights_dict.items():
            this_virtual_marker_name = this_virtual_marker_dict[0]
            these_weighted_points = []
            for this_weighted_point_dict in this_virtual_marker_dict[1].items():
                this_point_name = this_weighted_point_dict[0]

                this_weight = this_weighted_point_dict[1]
                these_weighted_points.append(
                    mediapipe_skel_fr_mar_dim[:, mediapipe_tracked_point_names.index(this_point_name), :] * this_weight
                )
            this_virtual_point_fr_xyz = np.sum(these_weighted_points, axis=0)
            this_virtual_point_fr_mar_xyz = np.expand_dims(this_virtual_point_fr_xyz, axis=1)
            mediapipe_skel_fr_mar_dim = np.append(mediapipe_skel_fr_mar_dim, this_virtual_point_fr_mar_xyz, axis=1)
            virtual_point_index_dict[this_virtual_marker_name] = mediapipe_skel_fr_mar_dim.shape[1] - 1
            print(
                f"Virtual marker: {this_virtual_marker_name} created at marker index {mediapipe_skel_fr_mar_dim.shape[1] - 1}"
            )

        # %% define edges

        edges = []
        # regular data
        for this_bone_dict in stick_figure_mesh_edge_pairs_dict_of_dicts.items():
            edge_name = this_bone_dict[0]
            head_name = this_bone_dict[1]["head"]
            tail_name = this_bone_dict[1]["tail"]

            try:
                head_index = mediapipe_tracked_point_names.index(head_name)
                tail_index = mediapipe_tracked_point_names.index(tail_name)

                if (
                    "center" in head_name
                ):  # virtual markers are acting weird so we're brute forcing it :-/ this will fail if there is a virtual marker without 'center' in the name....
                    head_index = virtual_point_index_dict[head_name]
                if "center" in tail_name:
                    tail_index = virtual_point_index_dict[tail_name]

                this_edge = (head_index, tail_index)

                edges.append(this_edge)
                print(
                    f"edge created for bone: ({this_bone_dict[0]} : {head_name}-{tail_name}), indicies({this_edge[0]},{this_edge[1]})"
                )
            except:
                print(f"edge FAILED for for bone:{this_bone_dict[0]} : {head_name}-{tail_name}")
                pass

        print("edges created!")
        # #
        # # ##############################
        # # # %% Create mesh
        # # try:
        # #     bpy.ops.object.mode_set(mode='OBJECT')
        # # except:
        # #     pass
        # #
        # # print('loading verticies')
        # # vertices = mediapipe_skel_fr_mar_dim[current_frame, :,
        # #            :]  # don't plot face dottos until we know what to do with them
        # # print('done loading verticies')
        # # # edges defined above
        # # faces = []
        # # stick_figure_mesh = bpy.data.meshes.new('stick_figure_mesh')
        # # print('a')
        # # stick_figure_mesh.from_pydata(vertices, edges, faces)
        # # print('b')
        # # stick_figure_mesh.update()
        # # print('c')
        # # # make object from mesh
        # # stick_figure_mesh_object = bpy.data.objects.new('stick_figure_mesh', stick_figure_mesh)
        # # print('d')
        # # # make collection
        # # mesh_collection = bpy.data.collections.new('mesh_collection')
        # # print('e')
        # # bpy.context.scene.collection.children.link(mesh_collection)
        # # print('f')
        # # # add object to scene collection
        # # mesh_collection.objects.link(stick_figure_mesh_object)
        # # print('g')
        # #
        # # bpy.context.view_layer.objects.active = bpy.data.objects['stick_figure_mesh']
        # # print('h')
        #
        # bpy.context.object.mode
        # try:
        #     bpy.ops.object.editmode_toggle()
        # except:
        #     pass
        # print('i')
        #
        # #### skin that mesh!
        # print('skinning mesh \o/')
        # bpy.data.objects['stick_figure_mesh'].modifiers.new('stick_figure_mesh_skin', 'SKIN')
        # print('resizing mesh')
        # skin_radius = .025
        # bpy.ops.transform.skin_resize(value=(skin_radius, skin_radius, skin_radius))
        #
        # ########
        # # # parent mesh to armature
        # print('parenting mesh to armarture with automatic weights...')
        # bpy.ops.object.mode_set(mode='OBJECT')
        # bpy.data.objects['stick_figure_mesh'].parent = this_metarig
        # bpy.context.view_layer.objects.active = this_metarig
        # bpy.context.active_object.select_set(True)
        # bpy.data.objects['stick_figure_mesh'].select_set(True)
        # bpy.ops.object.parent_set(type='ARMATURE_AUTO')

        #####################
        ## Load nSynched Videos
        try:
            print("loading videos as planes...")
            annotated_videos_path = session_path / "annotated_videos"

            if annotated_videos_path.is_dir():
                vidFolderPath = annotated_videos_path
            else:
                vidFolderPath = session_path / "synchronized_videos"

            world_origin = bpy.data.objects["world_origin"]

            number_of_videos = len(list(get_video_paths(vidFolderPath)))

            vid_location_scale = 1

            for (
                vid_number,
                thisVidPath,
            ) in enumerate(get_video_paths(vidFolderPath)):
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
        except:
            print(
                'Failed to load videos to Blender scene - You might need to install the "images as planes" addon to this version of Blender'
            )
except Exception as e:
    print(e)
    print(
        "Something broke in the Blender Megascript - Maybe it failed to find a good clean frame and then that borked something downstream?"
    )

# set shading type to 'Material Preview' so you can see the videos
# bpy.context.space_data.shading.type = "MATERIAL"

# save .blend file
sessionID = session_path.stem

print(f"Saving Blender output file to: {str(blend_file_save_path)}")
bpy.ops.wm.save_as_mainfile(filepath=str(blend_file_save_path))
