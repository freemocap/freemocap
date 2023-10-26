from typing import Dict, Tuple

import bpy

from ajc_freemocap_blender_addon.core_functions.mesh.create_mesh.helpers.create_bone_stick import create_bone_mesh
from ajc_freemocap_blender_addon.core_functions.mesh.create_mesh.helpers.make_bone_mesh import make_bone_mesh
from ajc_freemocap_blender_addon.core_functions.mesh.create_mesh.helpers.put_sphere_at_location import put_sphere_mesh_at_location
from ajc_freemocap_blender_addon.data_models.mediapipe_names.mediapipe_heirarchy import MEDIAPIPE_HIERARCHY


def create_skeleton_segment_object(child_name: str,
                                   child_empty: bpy.types.Object,
                                   parent_empty: bpy.types.Object,
                                   parent_name: str):
    pass


def put_bone_meshes_on_empties(empties: Dict[str, bpy.types.Object]):
    all_empties = {}
    for component in empties.values():
        all_empties.update(component)
        if component == empties["hands"]:
            for hand_component in component.values():
                all_empties.update(hand_component)
        if component == empties["other"]:
            for other_component in component.values():
                all_empties.update(other_component)

    for parent_empty_name in MEDIAPIPE_HIERARCHY.keys():
        color, squish_scale = get_bone_mesh_color_and_squish(parent_empty_name)

        for child_name in MEDIAPIPE_HIERARCHY[parent_empty_name]["children"]:
            # segment length is the distance between the parent and child empty
            segment_length = (all_empties[child_name].location - all_empties[parent_empty_name].location).length

            bone_mesh = make_bone_mesh(name=f"{parent_empty_name}_bone_mesh",
                                       length=segment_length,
                                       squish_scale=squish_scale,
                                       joint_color=color,
                                       cone_color=color,
                                       axis_visible=False
                                       )
            location_constraint = bone_mesh.constraints.new(type="COPY_LOCATION")
            location_constraint.target = all_empties[parent_empty_name]

            track_to_constraint = bone_mesh.constraints.new(type="DAMPED_TRACK")
            track_to_constraint.target = all_empties[child_name]
            track_to_constraint.track_axis = "TRACK_Z"


def put_spheres_on_empties(empties: Dict[str, bpy.types.Object]):
    meshes = []

    components = {}
    components["body"] = empties["body"]
    components["right_hand"] = empties["hands"]["right"]
    components["left_hand"] = empties["hands"]["left"]
    components["other"] = {}
    for other_name, other_component_dict in empties["other"].items():
        for name, empty in other_component_dict.items():
            components["other"][name] = empty

    for component_name, component_dict in components.items():
        emission_strength = 1.0

        color, emission_strength, sphere_scale = get_segment_settings(component_name, emission_strength)

        for empty_name, empty in component_dict.items():
            bpy.ops.object.mode_set(mode="OBJECT")
            sphere_mesh = put_sphere_mesh_at_location(name=empty_name,
                                                      location=empty.location,
                                                      sphere_scale=sphere_scale,
                                                      color=color,
                                                      emission_strength=emission_strength)

            bpy.ops.object.mode_set(mode="OBJECT")
            sphere_mesh = bpy.context.active_object
            constraint = sphere_mesh.constraints.new(type="COPY_LOCATION")
            constraint.target = empty

    return meshes


def get_bone_mesh_color_and_squish(parent_empty_name: str) -> Tuple[str, Tuple[float, float, float]]:
    squish_scale = (.8, 1, 1)
    if not "hand" in parent_empty_name:

        if "right" in parent_empty_name:
            color = "#FF0000"
        elif "left" in parent_empty_name:
            color = "#0000FF"
        else:
            color = "#610088"
            squish_scale = (1.0, 1.0, 1.0)

    else:
        if "right" in parent_empty_name:
            color = "#9f0000"

        elif "left" in parent_empty_name:
            color = "#00b630"

        else:
            raise ValueError(f"All hand bones must have 'right' or 'left' in their name, not {parent_empty_name}")
    return color, squish_scale


def get_segment_settings(component_name, emission_strength):
    if component_name == "body":
        if "right" in component_name:
            color = "#FF0000"
        elif "left" in component_name:
            color = "#0000FF"
        else:
            color = "#610088"
        sphere_scale = .025
    elif component_name == "left_hand":
        color = "#00b630"
        sphere_scale = .01
    elif component_name == "right_hand":
        color = "#9f0000"
        sphere_scale = .01
    elif component_name == "other":
        color = "#FF00FF"
        sphere_scale = .04
        emission_strength = 100
    return color, emission_strength, sphere_scale
