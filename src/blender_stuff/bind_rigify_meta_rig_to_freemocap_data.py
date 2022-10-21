from typing import List

import bpy
import addon_utils

import numpy as np
from pathlib import Path
import json

import sys

print("Running script to create Blender file from freemocap session data: " + __file__)
###############################################################
### parse arguments from command line

try:
    ##% Session path
    # #get session path as command line argument
    argv = sys.argv
    argv = argv[argv.index("--") + 1 :]

    session_path = Path(argv[0])

    if len(argv) > 1:
        good_clean_frame_number = int(argv[1])
    else:
        good_clean_frame_number = 0
except:
    print(
        "we appear to be running from the Blender Scripting tab! Manually enter your `session_path` at line 23"
    )
    # TODO - This should point to some kinda online-hosted demo session data or something
    session_path = Path(
        r"D:\Dropbox\FreeMoCapProject\teddy_animation\FreeMocap_Data\sesh_2022-10-01_13_38_04_paul_dance_2"
    )
    good_clean_frame_number = (
        0  # pick a frame where subject is in a good pose (e.g. T- or A-pose
    )

############
## Define some things that we'll need later

# Mediapipe Tracked Point Names
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

mediapipe_virtual_marker_definitions_dict = {
    "head_center": {
        "marker_names": ["left_ear", "right_ear"],
        "marker_weights": [0.5, 0.5],
    },
    "neck_center": {
        "marker_names": ["left_shoulder", "right_shoulder"],
        "marker_weights": [0.5, 0.5],
    },
    "hips_center": {
        "marker_names": ["left_hip", "right_hip"],
        "marker_weights": [0.5, 0.5],
    },
    "trunk_center": {
        "marker_names": ["left_shoulder", "right_shoulder", "left_hip", "right_hip"],
        "marker_weights": [0.25, 0.25, 0.25, 0.25],
    },
}

# Skeleton segments names and the rigify bone names that they correspond to
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

# A dictionary where the `keys` are  rigify bone names and the `values` are bone constraints and their parameters.
# NOTE - the `targets` must correspond to the `mediapipe_body_names` list above (or one of the virtural markers we'll make later)
rig_constraint_dict_of_dicts = {
    "spine": {
        "COPY_LOCATION": {"target": "hips_center"},
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
        "COPY_LOCATION": {"target": "armature", "subtarget": "spine.006"},
        "DAMPED_TRACK": {
            "target": "head_center",
        },
        "LOCKED_TRACK": {
            "target": "nose",
            "track_axis": "TRACK_Z",
            "lock_axis": "LOCK_Y",
            "influence": 1.0,
        },
        "LOCKED_TRACK.001": {
            "target": "left_ear",
            "track_axis": "TRACK_Z",
            "lock_axis": "LOCK_Z",
            "influence": 1.0,
        },
    },
    "shoulder.R": {
        "COPY_LOCATION": {"target": "neck_center"},
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
        "COPY_LOCATION": {"target": "neck_center"},
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
        "COPY_LOCATION": {"target": "right_hip"},
        "DAMPED_TRACK": {"target": "right_knee"},
    },
    "shin.R": {
        "DAMPED_TRACK": {"target": "right_ankle"},
    },
    "foot.R": {
        "DAMPED_TRACK": {"target": "right_foot_index"},
    },
    "thigh.L": {
        "COPY_LOCATION": {"target": "left_hip"},
        "DAMPED_TRACK": {"target": "left_knee"},
    },
    "shin.L": {
        "DAMPED_TRACK": {"target": "left_ankle"},
    },
    "foot.L": {
        "DAMPED_TRACK": {"target": "left_foot_index"},
    },
}

# connects the dots what for to make the stick figure friend
stick_figure_mesh_edges_list_of_lists = [
    ["head_center", "nose"],
    ["nose", "left_eye_inner"],
    ["left_eye_inner", "left_eye"],
    ["left_eye", "left_eye_outer"],
    ["left_eye_outer", "left_ear"],
    ["nose", "right_eye_inner"],
    ["right_eye_inner", "right_eye"],
    ["right_eye", "right_eye_outer"],
    ["right_eye_outer", "right_ear"],
    ["nose", "mouth_right"],
    ["mouth_right", "mouth_left"],
    ["nose", "mouth_left"],
    ["left_elbow", "left_wrist"],
    ["left_shoulder", "left_elbow"],
    ["neck_center", "left_shoulder"],
    ["right_elbow", "right_wrist"],
    ["right_shoulder", "right_elbow"],
    ["neck_center", "right_shoulder"],
    ["left_hip", "left_knee"],
    ["left_knee", "left_ankle"],
    ["left_heel", "left_ankle"],
    ["left_ankle", "left_foot_index"],
    ["left_foot_index", "left_heel"],
    ["right_hip", "right_knee"],
    ["right_knee", "right_ankle"],
    ["right_heel", "right_ankle"],
    ["right_ankle", "right_foot_index"],
    ["right_foot_index", "right_heel"],
    ["hips_center", "left_hip"],
    ["hips_center", "right_hip"],
    ["hips_center", "neck_center"],
    ["neck_center", "head_center"],
    ["head_center", "nose"],
    # right hand
    ["right_wrist", "right_hand_index_finger_mcp"],
    ["right_wrist", "right_hand_middle_finger_mcp"],
    ["right_wrist", "right_hand_ring_finger_mcp"],
    ["right_wrist", "right_hand_pinky_finger_mcp"],
    ["right_wrist", "right_hand_thumb_cmc"],
    ["right_hand_thumb_cmc", "right_hand_thumb_mcp"],
    ["right_hand_thumb_mcp", "right_hand_thumb_ip"],
    ["right_hand_thumb_ip", "right_hand_thumb_tip"],
    ["right_hand_index_finger_mcp", "right_hand_index_finger_pip"],
    ["right_hand_index_finger_pip", "right_hand_index_finger_dip"],
    ["right_hand_index_finger_dip", "right_hand_index_finger_tip"],
    ["right_hand_middle_finger_mcp", "right_hand_middle_finger_pip"],
    ["right_hand_middle_finger_pip", "right_hand_middle_finger_dip"],
    ["right_hand_middle_finger_dip", "right_hand_middle_finger_tip"],
    ["right_hand_ring_finger_mcp", "right_hand_ring_finger_pip"],
    ["right_hand_ring_finger_pip", "right_hand_ring_finger_dip"],
    ["right_hand_ring_finger_dip", "right_hand_ring_finger_tip"],
    ["right_hand_pinky_finger_mcp", "right_hand_pinky_finger_pip"],
    ["right_hand_pinky_finger_pip", "right_hand_pinky_finger_dip"],
    ["right_hand_pinky_finger_dip", "right_hand_pinky_finger_tip"],
    # left hand
    ["left_wrist", "left_hand_thumb_cmc"],
    ["left_hand_thumb_cmc", "left_hand_thumb_mcp"],
    ["left_hand_thumb_mcp", "left_hand_thumb_ip"],
    ["left_hand_thumb_ip", "left_hand_thumb_tip"],
    ["left_wrist", "left_hand_index_finger_mcp"],
    ["left_wrist", "left_hand_middle_finger_mcp"],
    ["left_wrist", "left_hand_ring_finger_mcp"],
    ["left_wrist", "left_hand_pinky_finger_mcp"],
    ["left_hand_index_finger_mcp", "left_hand_index_finger_pip"],
    ["left_hand_index_finger_pip", "left_hand_index_finger_dip"],
    ["left_hand_index_finger_dip", "left_hand_index_finger_tip"],
    ["left_hand_middle_finger_mcp", "left_hand_middle_finger_pip"],
    ["left_hand_middle_finger_pip", "left_hand_middle_finger_dip"],
    ["left_hand_middle_finger_dip", "left_hand_middle_finger_tip"],
    ["left_hand_ring_finger_mcp", "left_hand_ring_finger_pip"],
    ["left_hand_ring_finger_pip", "left_hand_ring_finger_dip"],
    ["left_hand_ring_finger_dip", "left_hand_ring_finger_tip"],
    ["left_hand_pinky_finger_mcp", "left_hand_pinky_finger_pip"],
    ["left_hand_pinky_finger_pip", "left_hand_pinky_finger_dip"],
    ["left_hand_pinky_finger_dip", "left_hand_pinky_finger_tip"],
]


#################################################
## FUNCTIONS - We'll define some functions here and use them later


def create_keyframed_empty_from_3d_trajectory_data(
    trajectory_fr_xyz: np.ndarray,
    trajectory_name: str,
    parent_origin: bpy.types.Object = None,
    empty_scale: float = 0.1,
    empty_type: str = "PLAIN_AXES",
):
    """
    Create a key framed empty from 3d trajectory data
    """
    print(f"Creating keyframed empty from: {trajectory_name}...")
    bpy.ops.object.empty_add(type=empty_type)
    empty_object = bpy.context.active_object
    empty_object.name = trajectory_name

    empty_object.scale = [empty_scale] * 3

    empty_object.parent = freemocap_origin_axes

    for frame_number in range(end_frame):
        empty_object.location = [
            trajectory_fr_xyz[frame_number, 0],
            trajectory_fr_xyz[frame_number, 1],
            trajectory_fr_xyz[frame_number, 2],
        ]
        bpy.context.view_layer.update()

        empty_object.keyframe_insert(data_path="location", frame=frame_number)


def apply_constraints_to_bone(bone_name: str, bone_constraint_dict: dict, armature_rig):
    """
    Apply constraints to a bone (that exists in `armature_rig` based on a dictionary of constraints
    """
    for (
        constraint_name,
        constrain_parameters_dict,
    ) in bone_constraint_dict.items():
        constraint_name = constraint_name.split(".")[
            0
        ]  # for duplicated constraints, named `[constraint_name].001`, etc
        print(
            f"constraint: {constraint_name} with parameters:{constrain_parameters_dict}"
        )

        bone = armature_rig.pose.bones[bone_name]
        print(f"bone: {bone.name}")

        constraint = bone.constraints.new(type=constraint_name)
        print(f"constraint: {constraint.name}")

        # generic constraint settings
        if "target" in constrain_parameters_dict:

            if constrain_parameters_dict["target"] == "armature":
                constraint.target = armature_rig
                constraint.subtarget = constrain_parameters_dict["subtarget"]
                print(f"constraint.target: {constraint.target.name}")
                print(f"constraint.subtarget: {constraint.target.name}")
            else:
                constraint.target = bpy.data.objects[
                    constrain_parameters_dict["target"]
                ]  # point constraint at relevant empty object
                print(f"constraint.target: {constraint.target.name}")

        if "influence" in constrain_parameters_dict:
            constraint.influence = constrain_parameters_dict["influence"]
            print(f"constraint.influence: {constraint.influence}")

        # constraint-specific settings
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


# Virtual marker stuff


def test_virtual_marker_definitions(virtual_marker_definitions_dict: dict):
    """
    Validate the virtual marker definitions dictionary to ensure that there are the same number of marker names and weights, and that the weights sum to 1
    """

    for (
        virtual_marker_name,
        virtual_marker_definition,
    ) in virtual_marker_definitions_dict.items():
        assert len(virtual_marker_definition["marker_names"]) == len(
            virtual_marker_definition["marker_weights"]
        ), f"marker_names and marker_weights must be the same length for virtual marker {virtual_marker_name}"
        assert (
            sum(virtual_marker_definition["marker_weights"]) == 1
        ), f"marker_weights must sum to 1 for virtual marker {virtual_marker_name}"


def create_virtual_marker(
    trajectory_3d_frame_marker_xyz: np.ndarray,
    all_trajectory_names: list,
    component_trajectory_names: List,
    trajectory_weights: List,
) -> np.ndarray:
    """
    Create a virtual marker from a set of component markers. A 'Virtual Marker' is a 'fake' marker created by combining the data from 'real' (measured) marker/trajectory data
    `trajectory_3d_frame_marker_xyz`: all trajectory data in a numpy array with shape [frame, marker, xyz]
    `all_trajectory_names`: list of all trajectory names
    `component_trajectory_names`: the trajectories we'll use to make this virtual marker
    `trajectory_weights`: the weights we'll use to combine the compoenent trajectories into the virtual maker
    """

    # double check that the weights scale to one, otherwise this function will return screwy results
    assert np.sum(trajectory_weights) == 1, "Error - Trajectory_weights must sum to 1!"

    virtual_marker_xyz = np.zeros((trajectory_3d_frame_marker_xyz.shape[0], 3))

    for trajectory_number, trajectory_name in enumerate(component_trajectory_names):
        # pull out the trajectory data for this component trajectory
        component_trajectory_xyz = trajectory_3d_frame_marker_xyz[
            :, all_trajectory_names.index(trajectory_name), :
        ]

        # scale it by its weight
        component_trajectory_xyz *= trajectory_weights[trajectory_number]

        # add it to the virtual marker
        virtual_marker_xyz += component_trajectory_xyz

    return virtual_marker_xyz


def put_sphere_meshes_on_empties(
    empty_names_list: list,
    parent_object: bpy.types.Object,
    sphere_scale: float = 0.02,
):
    """
    put uv sphere meshes on the empties in `empty_names_list` with a scale of `sphere_scale`
    """

    for empty_name in empty_names_list:
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=8, ring_count=8, scale=(sphere_scale, sphere_scale, sphere_scale)
        )
        sphere = bpy.context.active_object
        sphere.name = f"{empty_name}_sphere"
        sphere.parent = parent_object

        constraint = sphere.constraints.new(type="COPY_LOCATION")
        constraint.target = bpy.data.objects[empty_name]


def make_stick_figure_mesh(
    skel3d_frame_landmark_xyz: np.ndarray,
    stick_figure_mesh_edges: list,
    mediapipe_landmark_names: list,
    good_clean_frame_number: int,
):
    """
    Create a stick figure mesh from a skeleton 3d data set
    `skel3d_frame_landmark_xyz`: skeleton 3d data set with shape [frame, landmark, xyz]
    `stick_figure_mesh_edge`: list of edges that make up the stick figure mesh
    `good_clean_frame_number`: the frame number to use for the stick figure mesh
    """

    # create a mesh
    mesh = bpy.data.meshes.new("stick_figure_mesh")

    # create a new object with the mesh
    stick_figure_mesh = bpy.data.objects.new("stick_figure_mesh", mesh)

    # get a reference to the scene
    scene = bpy.context.scene

    # link the object to the scene so it'll appear in the scene
    scene.collection.objects.link(stick_figure_mesh)

    # select the object
    stick_figure_mesh.select_set(True)

    # create the mesh from a list of verts/edges
    stick_figure_mesh_indicies = []
    for edge in stick_figure_mesh_edges:
        try:
            stick_figure_mesh_indicies.append(
                [
                    mediapipe_landmark_names.index(edge[0]),
                    mediapipe_landmark_names.index(edge[1]),
                ]
            )
        except Exception as e:
            print(e)

    mesh.from_pydata(
        skel3d_frame_landmark_xyz[good_clean_frame_number, :, :],
        stick_figure_mesh_indicies,
        [],
    )

    # update mesh with new data
    mesh.update(calc_edges=True)

    return stick_figure_mesh


def find_good_clean_frame_reprojection_error_method(
    skeleton_3d_fr_mar_xyz: np.ndarray, skeleton_reprojection_error_fr_mar: np.ndarray
):
    """
    Find the frame with the fewest nans, scaled by reprojection error (i.e. hopefully a frame where all tracked points are visible and well tracked)
    """
    print(
        "estimating good clean frame as the one where there few `nans`, reprojection error is low, and velocity is low..."
    )

    nans_per_frame = np.sum(np.isnan(skeleton_3d_fr_mar_xyz[:, :, 0]), axis=1)
    reprojection_error_per_frame = np.nanmedian(
        skeleton_reprojection_error_fr_mar, axis=1
    )
    marker_velocity_per_frame = np.nanmedian(
        np.abs(np.diff(skeleton_3d_fr_mar_xyz, axis=1)), axis=1
    )
    marker_velocity_per_frame = np.nanmean(np.abs(marker_velocity_per_frame), axis=1)

    print(f"nans_per_frame.shape: {nans_per_frame.shape}")
    print(f"reprojection_error_per_frame.shape: {reprojection_error_per_frame.shape}")
    print(f"marker_velocity_per_frame.shape: {marker_velocity_per_frame.shape}")

    # normalize errors by relevant thing
    nans_per_frame_normalized = nans_per_frame / skeleton_3d_fr_mar_xyz.shape[1]
    reprojection_error_per_frame_normalized = (
        reprojection_error_per_frame / np.nanmedian(reprojection_error_per_frame)
    )
    marker_velocity_per_frame_normalized = marker_velocity_per_frame / np.nanmedian(
        marker_velocity_per_frame
    )

    print(
        f"nans_per_frame_normalized (mean, [standard_deviation] : {np.nanmean(nans_per_frame_normalized):.3f} [{np.nanstd(nans_per_frame_normalized):.3f}]"
    )
    print(
        f"reprojection_error_per_frame_normalized (mean, [standard_deviation] : {np.nanmean(reprojection_error_per_frame_normalized):.3f} [{np.nanstd(reprojection_error_per_frame_normalized):.3f}]"
    )
    print(
        f"marker_velocity_per_frame_normalized (mean, [standard_deviation] : {np.nanmean(marker_velocity_per_frame_normalized):.3f} [{np.nanstd(marker_velocity_per_frame_normalized):.3f}]"
    )

    frame_cleanliness_score_where_low_scores_are_good = (
        nans_per_frame_normalized
        + reprojection_error_per_frame_normalized
        + marker_velocity_per_frame_normalized
    )

    good_clean_frame_number = np.nanargmin(
        frame_cleanliness_score_where_low_scores_are_good
    )
    print(f"----estimated good_clean_frame_number: {good_clean_frame_number}----")
    return good_clean_frame_number


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
### Getcher paths straight, lock and load yr data
# path_to_data_folder = Path("/Users/jon/Dropbox/FreeMoCapProject/FreeMocap_Data/")

print("Loading data....")
# %% load mediapipe data
# paths and whatnot
if Path(session_path / "output_data").exists():  # freemocap version > v0.0.54
    path_to_data_arrays_folder = session_path / "output_data"
    path_to_body_npy = path_to_data_arrays_folder / "mediapipe_body_3d_xyz.npy"
    path_to_reprojection_error_npy = (
        path_to_data_arrays_folder
        / "raw_data"
        / "mediapipe_3dData_numFrames_numTrackedPoints_reprojectionError.npy"
    )
    mediapipe_skel_fr_mar_xyz = np.load(str(path_to_body_npy))
    mediapipe_reprojection_error_fr_mar = np.load(str(path_to_reprojection_error_npy))

else:
    path_to_data_arrays_folder = (
        session_path / "DataArrays"
    )  # freemocap version <= v0.0.54
    if Path(
        path_to_data_arrays_folder / "mediapipe_body_3d_xyz.npy"
    ).exists():  # data has been 'post processed'
        path_to_body_npy = path_to_data_arrays_folder / "mediapipe_body_3d_xyz.npy"
    else:
        path_to_body_npy = (
            path_to_data_arrays_folder / "mediaPipeSkel_3d_smoothed.npy.npy"
        )

    path_to_reprojection_error_npy = (
        path_to_data_arrays_folder / "mediaPipeSkel_reprojErr.npy"
    )

    print(f"Loading mediapipe data from {path_to_body_npy}")

    mediapipe_skel_fr_mar_xyz = np.load(str(path_to_body_npy))
    mediapipe_reprojection_error_fr_mar = np.load(str(path_to_reprojection_error_npy))

    mediapipe_skel_fr_mar_xyz = mediapipe_skel_fr_mar_xyz[
        :, :33, :
    ]  # remove the hand and face markers
    mediapipe_reprojection_error_fr_mar = mediapipe_reprojection_error_fr_mar[
        :, :33
    ]  # remove the hand and face markers

# load mediapipe skeleton data

mediapipe_skel_fr_mar_xyz = mediapipe_skel_fr_mar_xyz / 1000  # convert to meters
number_of_frames = mediapipe_skel_fr_mar_xyz.shape[0]
print(f"mediapipe_skel_fr_mar_dim.shape: {mediapipe_skel_fr_mar_xyz.shape}")
print(
    f"mediapipe_reprojection_error_fr_mar.shape: {mediapipe_reprojection_error_fr_mar.shape}"
)

# get video paths (running through all iterations of our folder names
if Path(session_path / "annotated_videos").is_dir():
    video_folder_path = Path(session_path / "annotated_videos")
elif Path(session_path / "synchronized_videos").is_dir():
    video_folder_path = session_path / "synchronized_videos"
elif Path(session_path / "Annotated_Videos").is_dir():
    video_folder_path = session_path / "Annotated_Videos"
elif Path(session_path / "SyncedVideos").is_dir():
    video_folder_path = session_path / "SyncedVideos"
else:
    print("Couldn't find a video folder")

# load skeleton segment lengths
path_to_segment_length_json = (
    path_to_data_arrays_folder / "skeleton_segment_lengths.json"
)
try:
    print(
        f"loading skeleton segment lengths from `json` at - {str(path_to_segment_length_json)}"
    )
    f = open(path_to_segment_length_json)
    skeleton_segment_lengths_dict = json.load(f)
    f.close()
except Exception as e:
    print(e)
    print(
        f"Failed to load skeleton segment lengths from `json` at : {str(path_to_segment_length_json)}"
    )
    skeleton_segment_lengths_dict = None

#########################
### Create Origin Axes

bpy.ops.object.empty_add(type="ARROWS")
world_origin_axes = bpy.context.active_object
world_origin_axes.name = "world_origin"  # will stay at origin

bpy.ops.object.empty_add(type="ARROWS")
freemocap_origin_axes = bpy.context.active_object
freemocap_origin_axes.name = "freemocap_origin_axes"  # will translate to put skelly on ground symmetric-ish about origin

##############################
# %% Set start and end frames

start_frame = 1
end_frame = number_of_frames

if good_clean_frame_number == 0 or good_clean_frame_number is None:
    # estimate a good clean frame (ideally the T or A pose, but that's hard to pick out automatically)
    good_clean_frame_number = find_good_clean_frame_reprojection_error_method(
        skeleton_3d_fr_mar_xyz=mediapipe_skel_fr_mar_xyz,
        skeleton_reprojection_error_fr_mar=mediapipe_reprojection_error_fr_mar,
    )

bpy.context.scene.frame_start = start_frame
bpy.context.scene.frame_end = end_frame
bpy.context.scene.frame_current = good_clean_frame_number

############################
### Load body data as empty markers
empty_scale = 0.01
for trajectory_name in mediapipe_body_trajectory_names:
    this_trajectory_fr_xyz = mediapipe_skel_fr_mar_xyz[
        :, mediapipe_body_trajectory_names.index(trajectory_name), :
    ]
    create_keyframed_empty_from_3d_trajectory_data(
        trajectory_fr_xyz=this_trajectory_fr_xyz,
        trajectory_name=trajectory_name,
        parent_origin=freemocap_origin_axes,
        empty_scale=0.01,
        empty_type="SPHERE",
    )

#######################################################################
# %% create virtual markers
print("Creating virtual markers...")

# verify that the virtual marker definition dictionary is valid
test_virtual_marker_definitions(mediapipe_virtual_marker_definitions_dict)

for (
    virtual_marker_name,
    virtual_marker_dict,
) in mediapipe_virtual_marker_definitions_dict.items():
    print(
        f"Creating virtual marker: {virtual_marker_name}: "
        f"from 'real' markers: {virtual_marker_dict['marker_names']}, "
        f"with weights: {virtual_marker_dict['marker_weights']}"
    )

    mediapipe_body_trajectory_names.append(virtual_marker_name)
    virtual_marker_xyz = create_virtual_marker(
        trajectory_3d_frame_marker_xyz=mediapipe_skel_fr_mar_xyz,
        all_trajectory_names=mediapipe_body_trajectory_names,
        component_trajectory_names=virtual_marker_dict["marker_names"],
        trajectory_weights=virtual_marker_dict["marker_weights"],
    )
    create_keyframed_empty_from_3d_trajectory_data(
        trajectory_fr_xyz=virtual_marker_xyz,
        trajectory_name=virtual_marker_name,
        parent_origin=freemocap_origin_axes,
        empty_scale=empty_scale * 3,
        empty_type="PLAIN_AXES",
    )

print("____________________________________________________________________________")
print("Done loading in motion capture data -  Now lets use it to drive an armature!")
print("____________________________________________________________________________")

######################
### Create Rigify human meta-rig
print(f"Creating `rigify human meta-rig`")
bpy.ops.object.armature_human_metarig_add()
human_metarig = bpy.context.active_object

##################
### Scale armature


try:
    bpy.ops.object.mode_set(mode="EDIT")
except:
    pass

for (
    segment_name,
    rigify_bones_list,
) in rigify_bone_to_skeleton_segment_name_correspondance.items():

    for rigify_bone_name in rigify_bones_list:
        median_segment_length = skeleton_segment_lengths_dict[segment_name]["median"]
        median_segment_length *= 0.001  # scale to meters

        segment_length = median_segment_length / len(
            rigify_bones_list
        )  # divide by number of bones in segment (for now, eventually will want to set weights
        print(f"setting {rigify_bone_name} length to: {segment_length:.3f} m")
        human_metarig.data.edit_bones[rigify_bone_name].length = segment_length

####
#### Constrain bones to empties
####

# loop through dictionary applying  constraints
try:
    bpy.ops.object.mode_set(mode="POSE")
except:
    pass

try:
    for bone_name, bone_constraint_dict in rig_constraint_dict_of_dicts.items():
        print(f"---Setting constraints for bone:{bone_name}---")
        apply_constraints_to_bone(
            bone_name=bone_name,
            bone_constraint_dict=bone_constraint_dict,
            armature_rig=human_metarig,
        )

except Exception as e:
    print(e)
    print("Something went wrong applying constraints to armarture bones")

print("____________________________________________________________________________")
print("Done constraining armature bones to follow keyframed empties!")
print("____________________________________________________________________________")

####################
## Create simple stick figure mesh

print("____________________________________________________________________________")
print("Creating simple stick figure mesh")
print("____________________________________________________________________________")
try:
    bpy.ops.object.mode_set(mode="OBJECT")
except:
    pass
put_sphere_meshes_on_empties(
    empty_names_list=mediapipe_body_trajectory_names,
    parent_object=freemocap_origin_axes,
    sphere_scale=0.02,
)

stick_figure_mesh = make_stick_figure_mesh(
    skel3d_frame_landmark_xyz=mediapipe_skel_fr_mar_xyz,
    stick_figure_mesh_edges=stick_figure_mesh_edges_list_of_lists,
    mediapipe_landmark_names=mediapipe_body_trajectory_names,
    good_clean_frame_number=good_clean_frame_number,
)

#####################
## Load nSynched Videos
try:
    print("loading videos as planes...")

    world_origin = bpy.data.objects["world_origin"]

    number_of_videos = len(list(video_folder_path.glob("*.mp4")))

    vid_location_scale = 1

    for (
        vid_number,
        thisVidPath,
    ) in enumerate(video_folder_path.glob("*.mp4")):
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

try:
    # from https://blender.stackexchange.com/a/238223

    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:  # iterate through areas in current screen
            if area.type == "VIEW_3D":
                for (
                    space
                ) in area.spaces:  # iterate through spaces in current VIEW_3D area
                    if space.type == "VIEW_3D":  # check if space is a 3D view
                        space.shading.type = "MATERIAL"
except Exception as e:
    print(e)
    print("Failed to set shading to material")

# save .blend file
sessionID = session_path.stem
blend_file_save_path = session_path / (sessionID + ".blend")

bpy.ops.wm.save_as_mainfile(filepath=str(blend_file_save_path))

print("____________________________________________________________________________")
print("____________________________________________________________________________")
print(
    "Done creating Blender scene!\n",
    f"Saved .blend file to: {blend_file_save_path}\n",
    "You can now open the `.blend` file in Blender and play the animation!\n",
)
print("____________________________________________________________________________")
print("____________________________________________________________________________")
