import json
import logging
import sys
from pathlib import Path
from typing import List

import addon_utils
import bpy
import numpy as np

logging.info("Running script to create Blender file from freemocap session data: " + __file__)

logger = logging.getLogger(__name__)
###############################################################
### parse arguments from command line

logger.info(f"Running script to create Blender file from freemocap session data from script {__file__}")
try:
    ##% Session path
    # #get session path as command line argument
    argv = sys.argv
    print(f"Received command line arguments: {argv}")
    argv = argv[argv.index("--") + 1 :]

    recording_path = Path(argv[0])
    blender_file_save_path = Path(argv[1])
except:
    logger.info("No command line arguments received, using hard-coded path instead :D")
    recording_path = Path(
        r"C:\Users\jonma\freemocap_data\recording_sessions\session_2023-02-15_08_46_43_wud\recording_08_47_25_gmt-5_wud"
    )
    blender_file_save_path = Path(recording_path).parent / f"{Path(recording_path).name}_.blend"

skeleton_points_names_and_connections = (
    Path(recording_path).parent / "output_data" / "skeleton_points_names_and_connections.json"
)

print(skeleton_points_names_and_connections)


print("Loading data....")

# %% load mediapipe data
# paths and whatnot
if Path(recording_path / "output_data").exists():  # freemocap version > v0.0.54
    path_to_data_arrays_folder = recording_path / "output_data"
    path_to_body_npy = path_to_data_arrays_folder / "mediapipe_body_3d_xyz.npy"
    path_to_reprojection_error_npy = (
        path_to_data_arrays_folder / "raw_data" / "mediapipe3dData_numFrames_numTrackedPoints_reprojectionError.npy"
    )
    mediapipe_skel_fr_mar_xyz = np.load(str(path_to_body_npy))
    mediapipe_reprojection_error_fr_mar = np.load(str(path_to_reprojection_error_npy))

else:
    path_to_data_arrays_folder = recording_path / "DataArrays"  # freemocap version <= v0.0.54
    if Path(path_to_data_arrays_folder / "mediapipe_body_3d_xyz.npy").exists():  # data has been 'post processed'
        path_to_body_npy = path_to_data_arrays_folder / "mediapipe_body_3d_xyz.npy"
    else:
        path_to_body_npy = path_to_data_arrays_folder / "mediaPipeSkel_3d_smoothed.npy"

    path_to_reprojection_error_npy = path_to_data_arrays_folder / "mediaPipeSkel_reprojErr.npy"

    print(f"Loading mediapipe data from {path_to_body_npy}")

    mediapipe_skel_fr_mar_xyz = np.load(str(path_to_body_npy))
    mediapipe_reprojection_error_fr_mar = np.load(str(path_to_reprojection_error_npy))

    mediapipe_skel_fr_mar_xyz = mediapipe_skel_fr_mar_xyz[:, :33, :]  # remove the hand and face markers
    mediapipe_reprojection_error_fr_mar = mediapipe_reprojection_error_fr_mar[
        :, :33
    ]  # remove the hand and face markers

# load mediapipe skeleton data

mediapipe_skel_fr_mar_xyz = mediapipe_skel_fr_mar_xyz / 1000  # convert to meters
number_of_frames = mediapipe_skel_fr_mar_xyz.shape[0]
print(f"mediapipe_skel_fr_mar_dim.shape: {mediapipe_skel_fr_mar_xyz.shape}")
print(f"mediapipe_reprojection_error_fr_mar.shape: {mediapipe_reprojection_error_fr_mar.shape}")

# get video paths (running through all iterations of our folder names
if Path(recording_path / "annotated_videos").is_dir():
    video_folder_path = Path(recording_path / "annotated_videos")
elif Path(recording_path / "synchronized_videos").is_dir():
    video_folder_path = recording_path / "synchronized_videos"
elif Path(recording_path / "Annotated_Videos").is_dir():
    video_folder_path = recording_path / "Annotated_Videos"
elif Path(recording_path / "SyncedVideos").is_dir():
    video_folder_path = recording_path / "SyncedVideos"
else:
    print("Couldn't find a video folder")

# load skeleton segment lengths
path_to_segment_length_json = path_to_data_arrays_folder / "mediapipe_skeleton_segment_lengths.json"
try:
    print(f"loading skeleton segment lengths from `json` at - {str(path_to_segment_length_json)}")
    f = open(path_to_segment_length_json)
    skeleton_segment_lengths_dict = json.load(f)
    f.close()
except Exception as e:
    print(e)
    print(f"Failed to load skeleton segment lengths from `json` at : {str(path_to_segment_length_json)}")
    skeleton_segment_lengths_dict = None

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
    empty_object = bpy.context.editable_objects[-1]
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
        print(f"constraint: {constraint_name} with parameters:{constrain_parameters_dict}")

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
        component_trajectory_xyz = trajectory_3d_frame_marker_xyz[:, all_trajectory_names.index(trajectory_name), :]

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
        bpy.ops.mesh.primitive_uv_sphere_add(segments=8, ring_count=8, scale=(sphere_scale, sphere_scale, sphere_scale))
        sphere = bpy.context.editable_objects[-1]
        sphere.name = f"{empty_name}_sphere"
        sphere.parent = parent_object

        constraint = sphere.constraints.new(type="COPY_LOCATION")
        constraint.target = bpy.data.objects[empty_name]


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

#########################
### Create Origin Axes

bpy.ops.object.empty_add(type="SPHERE", scale=(3.0, 3.0, 3.0))
world_origin_axes = bpy.context.editable_objects[-1]
world_origin_axes.name = "world_origin"  # will stay at origin

bpy.ops.object.empty_add(type="ARROWS")
freemocap_origin_axes = bpy.context.editable_objects[-1]
freemocap_origin_axes.name = (
    "freemocap_origin_axes"  # will translate to put skelly on ground symmetric-ish about origin
)

##############################
# %% Set start and end frames

start_frame = 1
end_frame = number_of_frames

bpy.context.scene.frame_start = start_frame
bpy.context.scene.frame_end = end_frame

############################
### Load body data as empty markers
empty_scale = 0.01
for trajectory_name in mediapipe_body_trajectory_names:
    trajectory_fr_xyz = mediapipe_skel_fr_mar_xyz[:, mediapipe_body_trajectory_names.index(trajectory_name), :]
    create_keyframed_empty_from_3d_trajectory_data(
        trajectory_fr_xyz=trajectory_fr_xyz,
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
    logging.info(
        f"Creating virtual marker: {virtual_marker_name}: \n"
        f"from 'real' markers: {virtual_marker_dict['marker_names']}, \n"
        f"with weights: {virtual_marker_dict['marker_weights']}\n"
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

logging.info(
    "____________________________________________________________________________\n",
    "Done loading in motion capture data -  Now lets use it to drive an armature!\n"
    "____________________________________________________________________________\n",
)

######################
### Create Rigify human meta-rig
logging.info(f"Creating `rigify human meta-rig`")
bpy.ops.object.armature_human_metarig_add()
human_metarig = bpy.context.editable_objects[-1]

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
        logging.info(f"setting {rigify_bone_name} length to: {segment_length:.3f} m")
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
        logging.info(f"---Setting constraints for bone:{bone_name}---")
        apply_constraints_to_bone(
            bone_name=bone_name,
            bone_constraint_dict=bone_constraint_dict,
            armature_rig=human_metarig,
        )

except Exception as e:
    logging.info(e)
    logging.info("Something went wrong applying constraints to armarture bones")

logging.info(
    "____________________________________________________________________________\n",
    "Done constraining armature bones to follow keyframed empties!",
    "____________________________________________________________________________",
)

####################
## Create simple stick figure mesh

logging.info(
    "____________________________________________________________________________\n",
    "Creating simple stick figure mesh\n",
    "____________________________________________________________________________",
)
try:
    bpy.ops.object.mode_set(mode="OBJECT")
except:
    pass
put_sphere_meshes_on_empties(
    empty_names_list=mediapipe_body_trajectory_names,
    parent_object=freemocap_origin_axes,
    sphere_scale=0.02,
)

#####################
## Load nSynched Videos
try:
    logger.info("loading videos as planes...")

    world_origin = bpy.data.objects["world_origin"]

    number_of_videos = len(list(video_folder_path.glob("*.mp4")))

    vid_location_scale = 1

    for (
        vid_number,
        thisVidPath,
    ) in enumerate(video_folder_path.glob("*.mp4")):
        logger.info(thisVidPath)
        # use 'images as planes' add on to load in the video files as planes
        bpy.ops.import_image.to_plane(
            files=[{"name": thisVidPath.name}],
            directory=str(thisVidPath.parent),
            shader="EMISSION",
        )
        vid_as_plane = bpy.context.editable_objects[-1]
        vid_as_plane.name = "vid_" + str(vid_number)

        vid_x = (vid_number - number_of_videos / 2) * vid_location_scale

        vid_as_plane.location = [
            vid_x,
            vid_location_scale,
            vid_location_scale,
        ]
        vid_as_plane.rotation_euler = [np.pi / 2, 0, 0]
        vid_as_plane.scale = [vid_location_scale * 1.5] * 3
        vid_as_plane.parent = world_origin
        # create a light
        # bpy.ops.object.light_add(type='POINT', radius=1, align='WORLD')
except Exception as e:
    logger.info(e)
    logger.info(
        'Failed to load videos to Blender scene - You might need to install the "images as planes" addon to this version of Blender'
    )

try:
    # from https://blender.stackexchange.com/a/238223

    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:  # iterate through areas in current screen
            if area.type == "VIEW_3D":
                for space in area.spaces:  # iterate through spaces in current VIEW_3D area
                    if space.type == "VIEW_3D":  # check if space is a 3D view
                        space.shading.type = "MATERIAL"
except Exception as e:
    logger.info(e)
    logger.info("Failed to set shading to material")

# save .blend file

bpy.ops.wm.save_as_mainfile(filepath=str(blender_file_save_path))

logging.info(
    "____________________________________________________________________________\n",
    "____________________________________________________________________________\n",
    "Done creating Blender scene!\n",
    f"Saved .blend file to: {blender_file_save_path}\n",
    "You can now open the `.blend` file in Blender and play the animation!\n",
    "____________________________________________________________________________\n",
    "____________________________________________________________________________",
)
