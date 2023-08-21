import json
import logging
import sys
from copy import copy
from pathlib import Path
from typing import List, Union, Dict, Tuple

import addon_utils
import bpy
import numpy as np

print("Running script to create Blender file from freemocap session data: " + __file__)

logger = logging.getLogger(__name__)


###############################################################
### IF YOU ARE RUNNING THIS SCRIPT FROM WITHIN BLENDER -
### CHANGE THE PATH TO THE SESSION FOLDER IN THE `if __name__ == "__main__":` BLOCK AT THE **BOTTOM** OF THIS FILE
### the variable is named `recording_path_input`
###############################################################


def main(
    recording_path: Union[str, Path],
    blender_file_save_path: Union[str, Path],
    mediapipe_empty_names: Dict[str, List[str]],
    create_rig: bool = True,
):
    ###%% clear the scene - Scorch the earth \o/
    print("Clearing scene...")
    try:
        bpy.ops.object.mode_set(mode="OBJECT")
    except:
        pass
    try:
        bpy.ops.object.select_all(action="SELECT")  # select all objects
        bpy.ops.object.delete(use_global=True)  # delete all objects from all scenes
    except:
        pass

    print("Loading data....")

    # paths and whatnot
    try:
        # load mediapipe skeleton data
        path_to_data_arrays_folder = recording_path / "output_data"
        path_to_body_npy = path_to_data_arrays_folder / "mediapipe_body_3d_xyz.npy"
        path_to_right_hand_npy = path_to_data_arrays_folder / "mediapipe_right_hand_3d_xyz.npy"
        path_to_left_hand_npy = path_to_data_arrays_folder / "mediapipe_left_hand_3d_xyz.npy"
        path_to_face_npy = path_to_data_arrays_folder / "mediapipe_face_3d_xyz.npy"

        path_to_center_of_mass_npy = path_to_data_arrays_folder / "center_of_mass" / "total_body_center_of_mass_xyz.npy"
        path_to_body_segment_centers_npy = (
            path_to_data_arrays_folder / "center_of_mass" / "segmentCOM_frame_joint_xyz.npy"
        )

        mediapipe_body_fr_mar_xyz = np.load(str(path_to_body_npy)) / 1000  # load and convert to meters
        mediapipe_right_hand_fr_mar_xyz = np.load(str(path_to_right_hand_npy)) / 1000
        mediapipe_left_hand_fr_mar_xyz = np.load(str(path_to_left_hand_npy)) / 1000
        mediapipe_face_fr_mar_xyz = np.load(str(path_to_face_npy)) / 1000

        center_of_mass_fr_xyz = np.load(str(path_to_center_of_mass_npy)) / 1000
        body_segment_centers_fr_mar_xyz = np.load(str(path_to_body_segment_centers_npy)) / 1000

        # load reprojection error
        path_to_reprojection_error_npy = (
            path_to_data_arrays_folder / "raw_data" / "mediapipe3dData_numFrames_numTrackedPoints_reprojectionError.npy"
        )
        mediapipe_reprojection_error_fr_mar = np.load(str(path_to_reprojection_error_npy))

        # load skeleton segment lengths
        path_to_segment_length_json = path_to_data_arrays_folder / "mediapipe_skeleton_segment_lengths.json"
        print(f"loading skeleton segment lengths from `json` at - {str(path_to_segment_length_json)}")
        f = open(path_to_segment_length_json)
        skeleton_segment_lengths_dict = json.load(f)

    except Exception as e:
        print("Failed to load freemocap data")
        raise e

    number_of_frames = mediapipe_body_fr_mar_xyz.shape[0]
    print(f"mediapipe_body_fr_mar_dim.shape: {mediapipe_body_fr_mar_xyz.shape}")
    print(f"mediapipe_reprojection_error_fr_mar.shape: {mediapipe_reprojection_error_fr_mar.shape}")

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

    start_frame = 0
    end_frame = number_of_frames

    bpy.context.scene.frame_start = start_frame
    bpy.context.scene.frame_end = end_frame

    ############################
    ### Load mocap data as empty markers

    print(
        "_________________________\n"
        "__________________________\n"
        "Loading freemocap trajectory data as empty markers..."
        "_________________________\n"
    )

    mediapipe_body_trajectory_names = [empty_name for empty_name in mediapipe_empty_names["body"]]

    mediapipe_right_hand_trajectory_names = [f"right_hand_{empty_name}" for empty_name in mediapipe_empty_names["hand"]]
    mediapipe_left_hand_trajectory_names = [f"left_hand_{empty_name}" for empty_name in mediapipe_empty_names["hand"]]
    # mediapipe_face_trajectory_names = [f"face_{number}:{empty_name}" for number, empty_name in
    #                                    face_contour_marker_indices]

    try:  # load as much of the data as you can, but if there's an error keep going
        # create empty markers for body
        body_empty_scale = 0.03
        for marker_number in range(mediapipe_body_fr_mar_xyz.shape[1]):
            trajectory_name = mediapipe_body_trajectory_names[marker_number]
            trajectory_fr_xyz = mediapipe_body_fr_mar_xyz[:, marker_number, :]
            create_keyframed_empty_from_3d_trajectory_data(
                trajectory_fr_xyz=trajectory_fr_xyz,
                trajectory_name=trajectory_name,
                parent_origin=freemocap_origin_axes,
                empty_scale=body_empty_scale,
                empty_type="SPHERE",
            )

        # create empty markers for right hand
        hand_empty_scale = body_empty_scale * 0.5
        for marker_number in range(mediapipe_right_hand_fr_mar_xyz.shape[1]):
            trajectory_name = mediapipe_right_hand_trajectory_names[marker_number]
            trajectory_fr_xyz = mediapipe_right_hand_fr_mar_xyz[:, marker_number, :]
            create_keyframed_empty_from_3d_trajectory_data(
                trajectory_fr_xyz=trajectory_fr_xyz,
                trajectory_name=trajectory_name,
                parent_origin=freemocap_origin_axes,
                empty_scale=hand_empty_scale,
                empty_type="PLAIN_AXES",
            )

        # create empty markers for left hand
        for marker_number in range(mediapipe_left_hand_fr_mar_xyz.shape[1]):
            trajectory_name = mediapipe_left_hand_trajectory_names[marker_number]
            trajectory_fr_xyz = mediapipe_left_hand_fr_mar_xyz[:, marker_number, :]
            create_keyframed_empty_from_3d_trajectory_data(
                trajectory_fr_xyz=trajectory_fr_xyz,
                trajectory_name=trajectory_name,
                parent_origin=freemocap_origin_axes,
                empty_scale=hand_empty_scale,
                empty_type="PLAIN_AXES",
            )

        # create empty markers for body segment centers
        body_segment_center_empty_scale = body_empty_scale * 0.7
        for marker_number in range(body_segment_centers_fr_mar_xyz.shape[1]):
            trajectory_name = BODY_SEGMENT_NAMES[marker_number]
            trajectory_fr_xyz = body_segment_centers_fr_mar_xyz[:, marker_number, :]
            create_keyframed_empty_from_3d_trajectory_data(
                trajectory_fr_xyz=trajectory_fr_xyz,
                trajectory_name=trajectory_name,
                parent_origin=freemocap_origin_axes,
                empty_scale=body_segment_center_empty_scale,
                empty_type="PLAIN_AXES",
            )

        # create empty markers for full body center of mass
        full_body_center_of_mass_empty_scale = body_empty_scale * 1.5
        create_keyframed_empty_from_3d_trajectory_data(
            trajectory_fr_xyz=center_of_mass_fr_xyz,
            trajectory_name=FULL_BODY_CENTER_OF_MASS_NAME,
            parent_origin=freemocap_origin_axes,
            empty_scale=full_body_center_of_mass_empty_scale,
            empty_type="SPHERE",
        )

        # # create empty markers for face
        # face_empty_scale = 0.005
        # for marker_number in face_contour_marker_indices:
        #
        #     if marker_number < len(mediapipe_face_trajectory_names):
        #         trajectory_name = mediapipe_face_trajectory_names[marker_number]
        #     else:
        #         trajectory_name = f"face_{marker_number}"
        #
        #     trajectory_fr_xyz = mediapipe_face_fr_mar_xyz[:, marker_number, :]
        #     create_keyframed_empty_from_3d_trajectory_data(
        #         trajectory_fr_xyz=trajectory_fr_xyz,
        #         trajectory_name=trajectory_name,
        #         parent_origin=freemocap_origin_axes,
        #         empty_scale=face_empty_scale,
        #         empty_type="PLAIN_AXES",
        #     )
    except Exception as e:
        print(f"Error loading empty markers: {e}!")

    #######################################################################
    # %% create virtual markers
    print("_________________________\n" "-------------------------\n" "Creating virtual markers...")

    # verify that the virtual marker definition dictionary is valid
    test_virtual_marker_definitions(mediapipe_virtual_marker_definitions_dict)

    virtual_marker_names = list(mediapipe_virtual_marker_definitions_dict.keys())
    for virtual_marker_name in virtual_marker_names:
        component_trajectory_names = mediapipe_virtual_marker_definitions_dict[virtual_marker_name]["marker_names"]
        trajectory_weights = mediapipe_virtual_marker_definitions_dict[virtual_marker_name]["marker_weights"]

        print(
            f"Calculating virtual marker trajectory: {virtual_marker_name} \n"
            f"Component trajectories: {component_trajectory_names} \n"
            f" weights: {trajectory_weights}\n"
        )

        virtual_marker_xyz = calculate_virtual_marker_trajectory(
            trajectory_3d_frame_marker_xyz=mediapipe_body_fr_mar_xyz,
            all_trajectory_names=mediapipe_body_trajectory_names,
            component_trajectory_names=component_trajectory_names,
            trajectory_weights=trajectory_weights,
        )
        create_keyframed_empty_from_3d_trajectory_data(
            trajectory_fr_xyz=virtual_marker_xyz,
            trajectory_name=virtual_marker_name,
            parent_origin=freemocap_origin_axes,
            empty_scale=body_empty_scale * 3,
            empty_type="PLAIN_AXES",
        )

    print(f"Adding virtual marker names to body trajectory names  - {virtual_marker_names}")
    mediapipe_body_trajectory_names.extend(virtual_marker_names)
    print("Done creating virtual markers")

    #######################################################################
    # put sphere meshes on empty markers for visualization
    try:  # try to create sphere meshes on empty markers, if it fails, print the error and continue
        # body
        put_sphere_meshes_on_empties(
            empty_names_list=mediapipe_body_trajectory_names,
            parent_object=freemocap_origin_axes,
            sphere_scale=body_empty_scale * 0.8,
            marker_type="body",
            color="#33FF66",
        )

        # create_stick_meshes_between_emtpies(
        #     body_frame_marker_xyz=mediapipe_body_fr_mar_xyz,
        #     empty_names=mediapipe_body_trajectory_names,
        #     body_connections=body_connections,
        #     parent_object=freemocap_origin_axes,
        # )

        # right hand
        put_sphere_meshes_on_empties(
            empty_names_list=mediapipe_right_hand_trajectory_names,
            parent_object=freemocap_origin_axes,
            sphere_scale=hand_empty_scale * 0.8,
            marker_type="right_hand",
            color="#FF0000",
        )

        put_sphere_meshes_on_empties(
            empty_names_list=mediapipe_left_hand_trajectory_names,
            parent_object=freemocap_origin_axes,
            sphere_scale=hand_empty_scale * 0.8,
            marker_type="left_hand",
            color="#0000FF",
        )

        # # face
        # put_sphere_meshes_on_empties(
        #     empty_names_list=mediapipe_face_trajectory_names,
        #     parent_object=freemocap_origin_axes,
        #     sphere_scale=face_empty_scale,
        # )

        put_sphere_meshes_on_empties(
            empty_names_list=BODY_SEGMENT_NAMES,
            parent_object=freemocap_origin_axes,
            sphere_scale=body_segment_center_empty_scale * 0.8,
            marker_type="body_segment_center",
            color="#CCCC00",
        )

        put_sphere_meshes_on_empties(
            empty_names_list=[FULL_BODY_CENTER_OF_MASS_NAME],
            parent_object=freemocap_origin_axes,
            sphere_scale=body_empty_scale * 1.25,
            marker_type="center_of_mass",
            color="#FF00FF",
            emission_strength=30,
        )
    except Exception as e:
        print(f"Error creating sphere meshes on empties: {e}")

    ###########################
    ### Make stick figure
    # creating_stick_figure_mesh_from_bone_dictionary(trajectory_frame_marker_xyz=mediapipe_body_fr_mar_xyz,
    #                                                 body_connections=body_connections,)
    ############################
    ### Load videos into scene
    if Path(recording_path / "annotated_videos").is_dir():
        videos_path = Path(recording_path / "annotated_videos")
    elif Path(recording_path / "synchronized_videos").is_dir():
        videos_path = Path(recording_path / "synchronized_videos")
    else:
        print("Did not find an `annotated_videos` or `synchronized_videos` folder in the recording path")
        videos_path = None

    if videos_path is not None:
        try:
            addon_utils.enable("io_import_images_as_planes")
        except Exception as e:
            print("Error enabling `io_import_images_as_planes` addon: ")
            print(e)
        try:
            add_videos_to_scene(videos_path=videos_path, parent_object=world_origin_axes)
        except Exception as e:
            print("Error adding videos to scene: ")
            print(e)

    if create_rig:
        try:
            #######################################################################
            ### Create meta-rig
            print("Saving blender file with raw motion capture data before moving on to rigging")
            bpy.ops.object.mode_set(mode="OBJECT")
            bpy.ops.wm.save_as_mainfile(filepath=str(blender_file_save_path))

            print(
                "____________________________________________________________________________\n",
                "Done loading in motion capture data -  Now lets use it to drive an armature!\n"
                "____________________________________________________________________________\n",
            )

            #######################################################################
            ##% Activate necessary addons
            addon_utils.enable("rigify")

            ######################
            ### Create Rigify human meta-rig
            print("Creating `rigify human meta-rig`")
            bpy.ops.object.armature_human_metarig_add()
            human_metarig = bpy.context.editable_objects[-1]
            human_metarig.data.display_type = "WIRE"

            ##################
            ### Scale armature

            bpy.ops.object.mode_set(mode="EDIT")

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

            delete_bones = [
                "pelvis.L",
                "pelvis.R",
                "breast.L",
                "breast.R",
                "heel.02.L",
                "heel.02.R",
                "toe.L",
                "toe.R",
            ]

            for bone in delete_bones:
                human_metarig.data.edit_bones.remove(human_metarig.data.edit_bones[bone])

            extra_scale_bones = {"spine.005": 0.2}

            for bone, scale in extra_scale_bones.items():
                human_metarig.data.edit_bones[bone].length *= scale

            ####
            #### Constrain bones to empties
            ####

            # loop through dictionary applying  constraints
            bpy.ops.object.mode_set(mode="POSE")

            for bone_name, bone_constraint_dict in rig_constraint_dict_of_dicts.items():
                print(f"---Setting constraints for bone:{bone_name}---")
                apply_constraints_to_bone(
                    bone_name=bone_name,
                    bone_constraint_dict=bone_constraint_dict,
                    armature_rig=human_metarig,
                )

            print(
                "____________________________________________________________________________\n",
                "Done constraining armature bones to follow keyframed empties!",
                "____________________________________________________________________________",
            )

        except Exception as e:
            print("Error creating rig!! (You might need to manually activate the `rigify` addon in Blender)")
            print(e)

    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:  # iterate through areas in current screen
            if area.type == "VIEW_3D":
                for space in area.spaces:  # iterate through spaces in current VIEW_3D area
                    if space.type == "VIEW_3D":  # check if space is a 3D view
                        space.shading.type = "MATERIAL"

    # save .blend file
    bpy.ops.object.mode_set(mode="OBJECT")

    bpy.ops.wm.save_as_mainfile(filepath=str(blender_file_save_path))
    print(f"Saved .blend file to: {blender_file_save_path}")

    # print("try to hide the shameful metarig and then save again lol")
    # human_metarig.hide_set = True
    bpy.ops.wm.save_as_mainfile(filepath=str(blender_file_save_path))

    print(
        "____________________________________________________________________________\n",
        "____________________________________________________________________________\n",
        "Done creating Blender scene!\n",
        f"Saved .blend file to: {blender_file_save_path}\n",
        "You can now open the `.blend` file in Blender and play the animation!\n",
        "____________________________________________________________________________\n",
        "____________________________________________________________________________",
    )


def add_videos_to_scene(videos_path: Union[Path, str], parent_object: bpy.types.Object, vid_location_scale: float = 2):
    print("loading videos as planes...")

    number_of_videos = len(list(get_video_paths(videos_path)))
    print(f"Found {number_of_videos} videos in {videos_path}")
    for (
        video_number,
        video_path,
    ) in enumerate(get_video_paths(videos_path)):
        print(f"Adding video: {video_path.name} to scene")

        bpy.ops.import_image.to_plane(
            files=[{"name": video_path.name}],
            directory=str(video_path.parent),
            shader="EMISSION",
        )
        print(f"Added video: {video_path.name} to scene")
        video_as_plane = bpy.context.editable_objects[-1]
        print(f"video_as_plane: {video_as_plane}")
        video_as_plane.name = "video_" + str(video_number)
        print(f"video_as_plane.name: {video_as_plane.name}")
        buffer = 1.1
        vid_x = (video_number * buffer - np.mean(np.arange(0, number_of_videos))) * vid_location_scale

        video_as_plane.location = [
            vid_x,
            vid_location_scale,
            1,
        ]
        video_as_plane.rotation_euler = [np.pi / 2, 0, 0]
        video_as_plane.scale = [1] * 3
        video_as_plane.parent = parent_object


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

    empty_object.parent = parent_origin

    for frame_number in range(trajectory_fr_xyz.shape[0]):
        empty_object.location = [
            trajectory_fr_xyz[frame_number, 0],
            trajectory_fr_xyz[frame_number, 1],
            trajectory_fr_xyz[frame_number, 2],
        ]

        empty_object.keyframe_insert(data_path="location", frame=frame_number)


def create_material(
    name: str = "Generic",
    color: Union[str, Tuple, List] = "#00FFFF",
    emission_strength: float = 1.0,
):
    """
    Create a material with the given name and color, with a strong emission.

    :param name: The name of the material.
    :param color: The color of the material, in hex format.
    :return: The created material.
    """
    material = bpy.data.materials.new(name=name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    # Clear all nodes to start clean
    nodes.clear()

    # Create necessary nodes
    output = nodes.new(type="ShaderNodeOutputMaterial")
    emission = nodes.new(type="ShaderNodeEmission")
    bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
    mix = nodes.new(type="ShaderNodeMixShader")

    # Set the locations
    output.location = (300, 0)
    mix.location = (100, 0)
    bsdf.location = (-100, 50)
    emission.location = (-100, -50)

    # Set node links
    links.new(output.inputs[0], mix.outputs[0])
    links.new(mix.inputs[1], bsdf.outputs[0])
    links.new(mix.inputs[2], emission.outputs[0])

    # Convert color from hex to RGB
    if isinstance(color, str) and color.startswith("#"):
        color_rgb = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]  # skips the "#" and separates R, G, and B
    elif isinstance(color, list) or isinstance(color, tuple):
        color_rgb = color

    # Set the colors
    bsdf.inputs[0].default_value = (*color_rgb, 1)
    emission.inputs[0].default_value = (*color_rgb, 1)  # RGB + Alpha

    # Set the strength of the emission
    emission.inputs[1].default_value = emission_strength  # The higher this value, the more the material will glow

    return material


def put_sphere_meshes_on_empties(
    empty_names_list: list,
    parent_object: bpy.types.Object,
    sphere_scale: float = 0.02,
    material: Union[bpy.types.Material, str] = None,
    color: str = "#00FFFF",
    marker_type: str = "generic",
    emission_strength: float = 1.0,
):
    """
    Put uv sphere meshes on the empties in `empty_names_list` with a scale of `sphere_scale`.

    :param empty_names_list: List of empty object names.
    :param parent_object: The object to be set as parent for the created spheres.
    :param sphere_scale: The scale of the sphere.
    :param material: The material to be applied to the spheres, can be a bpy.types.Material object or a color string in hex format.
    """
    # If material is None, create a default material
    if material is None:
        material = create_material(
            color=color,
            name=marker_type,
            emission_strength=emission_strength,
        )

    # Ensure the provided material is a bpy.types.Material object
    assert isinstance(material, bpy.types.Material), "Material must be a bpy.types.Material object or a color string"

    for empty_name in empty_names_list:
        bpy.ops.mesh.primitive_uv_sphere_add(segments=8, ring_count=8, scale=(sphere_scale, sphere_scale, sphere_scale))
        sphere = bpy.context.editable_objects[-1]
        sphere.name = f"{empty_name}_sphere"
        sphere.parent = parent_object
        sphere.data.materials.append(material)

        constraint = sphere.constraints.new(type="COPY_LOCATION")
        constraint.target = bpy.data.objects[empty_name]


def create_stick_meshes_between_emtpies(
    body_frame_marker_xyz: np.ndarray,
    empty_names: List[str],
    body_connections: Dict[int, int],
    parent_object: bpy.types.Object,
):
    """make cylinder meshes between the empties as defined in `body_connections`"""
    for origin_marker_index, target_marker_index in body_connections.items():
        origin_marker_name = empty_names[origin_marker_index]
        target_marker_name = empty_names[target_marker_index]

        stick = create_stick_mesh()
        stick = bpy.context.editable_objects[-1]
        stick.name = f"{origin_marker_name}_to_{target_marker_name}"
        stick.parent = parent_object

        constraint = stick.constraints.new(type="COPY_LOCATION")
        constraint.target = bpy.data.objects[origin_marker_name]

        constraint = stick.constraints.new(type="DAMPED_TRACK")
        constraint.target = bpy.data.objects[target_marker_name]
        constraint.track_axis = "TRACK_Z"

        for frame_number in range(body_frame_marker_xyz.shape[0]):
            distance_between_markers = np.linalg.norm(
                body_frame_marker_xyz[frame_number, origin_marker_index, :]
                - body_frame_marker_xyz[frame_number, target_marker_index, :]
            )
            stick.scale = [1, 1, distance_between_markers]
            stick.keyframe_insert(data_path="scale", frame=frame_number)


def create_stick_mesh(
    vertices: int = 12,
    radius: float = 0.02,
    depth: float = 1.0,
    location=(0, 0, 0),
    rotation=(0, 0, 0),
    scale=(1, 1, 1),
    end_fill_type="TRIFAN",
    enter_editmode=False,
    align="WORLD",
):
    bpy.ops.mesh.primitive_cylinder_add(
        radius=radius,
        depth=depth,
        vertices=vertices,
        location=location,
        rotation=rotation,
        scale=scale,
        end_fill_type=end_fill_type,
        enter_editmode=enter_editmode,
        align=align,
    )
    # give 3dcursor new coordinates
    bpy.context.scene.cursor.location = (0.0, 0.0, -0.5)

    # set the origin on the current object to the 3dcursor location
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    return bpy.context.editable_objects[-1]


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


def calculate_virtual_marker_trajectory(
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
    assert len(component_trajectory_names) == len(
        trajectory_weights
    ), "Error - component_trajectory_names and trajectory_weights must be the same length!"
    virtual_marker_xyz = np.zeros((trajectory_3d_frame_marker_xyz.shape[0], 3))

    for trajectory_name, weight in zip(component_trajectory_names, trajectory_weights):
        # pull out the trajectory data for this component trajectory and scale by it's `weight`
        component_trajectory_xyz = copy(
            trajectory_3d_frame_marker_xyz[:, all_trajectory_names.index(trajectory_name), :] * weight
        )

        # add it to the virtual marker
        virtual_marker_xyz += component_trajectory_xyz

    return virtual_marker_xyz


def creating_stick_figure_mesh_from_bone_dictionary(
    trajectory_frame_marker_xyz: np.ndarray, body_connections: Dict[int, int]
):
    print("creating_stick_figure_mesh_from_bone_dictionary")

    assert (
        len(trajectory_frame_marker_xyz.shape) == 3
    ), "trajectory_frame_marker_xyz must have three axes - [frame, marker, xyz] (e.g. skeleton data from a single frame"
    mesh = bpy.data.meshes.new("stick_figure_mesh")

    init_zero_vertices = np.zeros((trajectory_frame_marker_xyz.shape[1], 3))

    edges = []
    for head_index, tail_index in body_connections.items():
        edges.append((head_index, tail_index))

    mesh.from_pydata(init_zero_vertices, edges, [])
    mesh.validate(verbose=True)
    mesh.update()

    skin_radius = 0.025
    print(f"Skinning stick figure mesh with radius {skin_radius}...")
    bpy.data.objects["stick_figure_mesh"].modifiers.new("stick_figure_mesh_skin", "SKIN")
    bpy.ops.transform.skin_resize(value=(skin_radius, skin_radius, skin_radius))

    for frame_number in range(trajectory_frame_marker_xyz.shape[0]):
        for vertex in mesh.vertices:
            vertex.co = trajectory_frame_marker_xyz[frame_number, vertex.index, :]
            vertex.keyframe_insert(data_path="co", frame=frame_number)  # keyframe the vertex location
        mesh.update()


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


mediapipe_empty_names = {
    # generated by: freemocap/core_processes/detecting_things_in_2d_images/mediapipe_stuff/mediapipe_skeleton_names_and_connections.py
    "body": [
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
    ],
    "hand": [
        "wrist",
        "thumb_cmc",
        "thumb_mcp",
        "thumb_ip",
        "thumb_tip",
        "index_finger_mcp",
        "index_finger_pip",
        "index_finger_dip",
        "index_finger_tip",
        "middle_finger_mcp",
        "middle_finger_pip",
        "middle_finger_dip",
        "middle_finger_tip",
        "ring_finger_mcp",
        "ring_finger_pip",
        "ring_finger_dip",
        "ring_finger_tip",
        "pinky_mcp",
        "pinky_pip",
        "pinky_dip",
        "pinky_tip",
    ],
    "face": ["right_eye", "left_eye", "nose_tip", "mouth_center", "right_ear_tragion", "left_ear_tragion"],
}

# NOTE - numbers refer to the index of the name in the relevant list above
body_connections = {
    15: 19,
    16: 18,
    18: 20,
    3: 7,
    14: 16,
    23: 24,
    28: 32,
    11: 12,
    27: 29,
    6: 8,
    24: 26,
    4: 5,
    5: 6,
    29: 31,
    12: 14,
    0: 4,
    9: 10,
    1: 2,
    30: 32,
    25: 27,
    26: 28,
    17: 19,
    2: 3,
    13: 15,
}

hand_connections = {
    3: 4,
    0: 1,
    17: 18,
    13: 17,
    18: 19,
    5: 9,
    14: 15,
    9: 13,
    1: 2,
    10: 11,
    19: 20,
    6: 7,
    15: 16,
    2: 3,
    11: 12,
    7: 8,
}
# boy howdy mediapipe did not make it easy to get this info...
face_contour_marker_indices = [
    0,
    7,
    10,
    13,
    14,
    17,
    21,
    33,
    37,
    39,
    40,
    46,
    52,
    53,
    54,
    55,
    58,
    61,
    63,
    65,
    66,
    67,
    70,
    78,
    80,
    81,
    82,
    84,
    87,
    88,
    91,
    93,
    95,
    103,
    105,
    107,
    109,
    127,
    132,
    133,
    136,
    144,
    145,
    146,
    148,
    149,
    150,
    152,
    153,
    154,
    155,
    157,
    158,
    159,
    160,
    161,
    162,
    163,
    172,
    173,
    176,
    178,
    181,
    185,
    191,
    234,
    246,
    249,
    251,
    263,
    267,
    269,
    270,
    276,
    282,
    283,
    284,
    285,
    288,
    291,
    293,
    295,
    296,
    297,
    300,
    308,
    310,
    311,
    312,
    314,
    317,
    318,
    321,
    323,
    324,
    332,
    334,
    336,
    338,
    356,
    361,
    362,
    365,
    373,
    374,
    375,
    377,
    378,
    379,
    380,
    381,
    382,
    384,
    385,
    386,
    387,
    388,
    389,
    390,
    397,
    398,
    400,
    402,
    405,
    409,
    415,
    454,
    466,
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
    "trunk_center": {
        "marker_names": ["left_shoulder", "right_shoulder", "left_hip", "right_hip"],
        "marker_weights": [0.25, 0.25, 0.25, 0.25],
    },
    "hips_center": {
        "marker_names": ["left_hip", "right_hip"],
        "marker_weights": [0.5, 0.5],
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

BODY_SEGMENT_NAMES = [
    "head",
    "trunk",
    "right_upper_arm",
    "left_upper_arm",
    "right_forearm",
    "left_forearm",
    "right_hand",
    "left_hand",
    "right_thigh",
    "left_thigh",
    "right_shin",
    "left_shin",
    "right_foot",
    "left_foot",
]


FULL_BODY_CENTER_OF_MASS_NAME = (
    "_full_body_center_of_mass"  # leading underscore to make it easier to find in the outliner
)

print(f"__name__: {__name__}")

if __name__ == "__main__" or __name__ == "<run_path>":
    # this is the part that actually runs the script
    argv = sys.argv
    create_rig_input = True

    print(f"Running script to create Blender file from freemocap session data from script {__file__}")
    try:
        # Session path
        # get session path as command line argument
        print(f"Received command line arguments: {argv}")
        argv = argv[argv.index("--") + 1 :]

        recording_path_input = Path(argv[0])
        blender_file_save_path_input = Path(argv[1])
        create_rig_input = bool(argv[2])
    except Exception as e:
        print(f"There was a problem loading command line arguments: {e}. Using hardcoded values instead.")

        if len(argv) == 0:
            ####
            # Change the path below (`recording_path_input`) to the path to your recording session folder
            ####
            recording_path_input = Path(
                r"C:\Users\jonma\freemocap_data\recording_sessions\session_2023-02-15_08_46_43_wud\recording_08_47_25_gmt-5_wud"
            )
            blender_file_save_path_input = Path(recording_path_input) / f"{Path(recording_path_input).name}_.blend"
            create_rig = True

    print(
        f"recording_path_input: {recording_path_input}, \n"
        f"blender_file_save_path_input: {blender_file_save_path_input}, \n"
        f"create_rig_input: {create_rig_input}"
    )

    main(
        recording_path=recording_path_input,
        blender_file_save_path=blender_file_save_path_input,
        mediapipe_empty_names=mediapipe_empty_names,
        create_rig=create_rig_input,
    )
