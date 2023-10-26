import logging
import math as m
from typing import Dict

import bpy

from ajc_freemocap_blender_addon.core_functions.mesh.create_mesh.create_mesh import create_mesh

logger = logging.getLogger(__name__)


def attach_mesh_to_rig(rig_name: str,
                       body_mesh_mode: str = "custom",
                       mesh_path: str = None,
                       empties: Dict[str, bpy.types.Object] = None,
                       ):
    try:
        rig = bpy.data.objects[rig_name]

        if body_mesh_mode == "file":

            mesh_from_file(mesh_path, rig)

        elif body_mesh_mode == "custom":
            if empties is None:
                logger.error(f"Must provide empties for custom body mesh")
                raise ValueError(f"Must provide empties for custom body mesh")

            create_mesh(rig=rig, empties=empties)

            # Deselect all
            bpy.ops.object.select_all(action='DESELECT')
            logger.success("Body mesh added successfully.")
            return rig

        else:
            logger.error(f"Invalid body_mesh_mode: {body_mesh_mode}")
            raise ValueError(f"Invalid body_mesh_mode: {body_mesh_mode}")
    except Exception as e:
        logger.error(f"Failed to attach mesh to rig: {type(e).__name__}: {e}")
        logger.exception(e)
        raise e


def create_custom_mesh_og(rig):
    # Change to edit mode
    bpy.ops.object.mode_set(mode='EDIT')
    ### Add cylinders and spheres for the major bones
    # Get the bone references to calculate the meshes locations and proportions
    spine = rig.data.edit_bones['spine']
    spine_001 = rig.data.edit_bones['spine.001']
    shoulder_R = rig.data.edit_bones['shoulder.R']
    shoulder_L = rig.data.edit_bones['shoulder.L']
    neck = rig.data.edit_bones['neck']
    hand_R = rig.data.edit_bones['hand.R']
    hand_L = rig.data.edit_bones['hand.L']
    thigh_R = rig.data.edit_bones['thigh.R']
    thigh_L = rig.data.edit_bones['thigh.L']
    shin_R = rig.data.edit_bones['shin.R']
    shin_L = rig.data.edit_bones['shin.L']
    foot_R = rig.data.edit_bones['foot.R']
    foot_L = rig.data.edit_bones['foot.L']
    # Calculate parameters of the different body meshes
    base_cylinder_radius = 0.05
    trunk_mesh_radius = base_cylinder_radius
    trunk_mesh_length = spine_001.tail[2] - spine.head[2] + 0.02
    trunk_mesh_location = (spine.head[0], spine.head[1], spine.head[2] + trunk_mesh_length / 2)
    neck_mesh_radius = base_cylinder_radius / 2
    neck_mesh_length = neck.length
    neck_mesh_location = (neck.head[0], neck.head[1], neck.head[2] + neck.length / 2)
    head_mesh_location = (neck.tail[0], neck.tail[1], neck.tail[2])
    head_mesh_radius = base_cylinder_radius * 2
    right_eye_mesh_location = (neck.tail[0] - 0.04, neck.tail[1] - head_mesh_radius, neck.tail[2] + 0.02)
    right_eye_mesh_radius = head_mesh_radius / 3
    left_eye_mesh_location = (neck.tail[0] + 0.04, neck.tail[1] - head_mesh_radius, neck.tail[2] + 0.02)
    left_eye_mesh_radius = head_mesh_radius / 3
    nose_mesh_location = (neck.tail[0], neck.tail[1] - head_mesh_radius, neck.tail[2] - 0.02)
    nose_mesh_radius = head_mesh_radius / 3.5
    right_arm_mesh_length = shoulder_R.tail[0] - hand_R.head[0]
    right_arm_mesh_location = (
        shoulder_R.tail[0] - right_arm_mesh_length / 2, shoulder_R.tail[1], shoulder_R.tail[2] - 0.02)
    right_arm_mesh_radius = base_cylinder_radius
    left_arm_mesh_length = hand_L.head[0] - shoulder_L.tail[0]
    left_arm_mesh_location = (
        shoulder_L.tail[0] + left_arm_mesh_length / 2, shoulder_L.tail[1], shoulder_L.tail[2] - 0.02)
    left_arm_mesh_radius = base_cylinder_radius
    right_hand_mesh_location = (hand_R.tail[0], hand_R.tail[1], hand_R.tail[2])
    right_hand_mesh_radius = base_cylinder_radius
    right_thumb_mesh_location = (hand_R.tail[0], hand_R.tail[1] - right_hand_mesh_radius, hand_R.tail[2])
    right_thumb_mesh_radius = right_hand_mesh_radius / 8
    left_hand_mesh_location = (hand_L.tail[0], hand_L.tail[1], hand_L.tail[2])
    left_hand_mesh_radius = base_cylinder_radius
    left_thumb_mesh_location = (hand_L.tail[0], hand_L.tail[1] - left_hand_mesh_radius, hand_L.tail[2])
    left_thumb_mesh_radius = right_hand_mesh_radius / 8
    right_leg_mesh_radius = thigh_R.head[2] - shin_R.tail[2]
    right_leg_mesh_location = (thigh_R.head[0], thigh_R.head[1], thigh_R.head[2] - right_leg_mesh_radius / 2)
    left_leg_mesh_radius = thigh_L.head[2] - shin_L.tail[2]
    left_leg_mesh_location = (thigh_L.head[0], thigh_L.head[1], thigh_L.head[2] - left_leg_mesh_radius / 2)
    right_foot_mesh_location = (foot_R.tail[0], foot_R.tail[1], foot_R.tail[2])
    left_foot_mesh_location = (foot_L.tail[0], foot_L.tail[1], foot_L.tail[2])
    # Create and append the body meshes to the list
    # Define the list that will contain the different meshes of the body
    body_meshes = []
    # Set basic cylinder properties
    cylinder_cuts = 20
    vertices = 16
    # Trunk
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=trunk_mesh_radius,
        depth=trunk_mesh_length,
        end_fill_type='NGON',
        calc_uvs=True,
        enter_editmode=False,
        align='WORLD',
        location=trunk_mesh_location,
        rotation=(0.0, 0.0, 0.0)
    )
    body_meshes.append(bpy.context.active_object)
    # Add subdivisions to the mesh so it bends properly
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.subdivide(number_cuts=cylinder_cuts)
    bpy.ops.object.mode_set(mode="OBJECT")
    # Neck
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=neck_mesh_radius,
        depth=neck_mesh_length,
        end_fill_type='NGON',
        calc_uvs=True,
        enter_editmode=False,
        align='WORLD',
        location=neck_mesh_location,
        rotation=(0.0, 0.0, 0.0)
    )
    body_meshes.append(bpy.context.active_object)
    # Add subdivisions to the mesh so it bends properly
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.subdivide(number_cuts=cylinder_cuts)
    bpy.ops.object.mode_set(mode="OBJECT")
    # Head
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=head_mesh_radius,
        enter_editmode=False,
        align='WORLD',
        location=head_mesh_location,
        scale=(1, 1.2, 1.2)
    )
    body_meshes.append(bpy.context.active_object)
    # Right Eye
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=right_eye_mesh_radius,
        enter_editmode=False,
        align='WORLD',
        location=right_eye_mesh_location,
        scale=(1, 1, 1)
    )
    body_meshes.append(bpy.context.active_object)
    # Left Eye
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=left_eye_mesh_radius,
        enter_editmode=False,
        align='WORLD',
        location=left_eye_mesh_location,
        scale=(1, 1, 1)
    )
    body_meshes.append(bpy.context.active_object)
    # Nose
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=nose_mesh_radius,
        enter_editmode=False,
        align='WORLD',
        location=nose_mesh_location,
        scale=(1, 1, 1)
    )
    body_meshes.append(bpy.context.active_object)
    # Right Arm
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=right_arm_mesh_radius,
        depth=right_arm_mesh_length,
        end_fill_type='NGON',
        calc_uvs=True,
        enter_editmode=False,
        align='WORLD',
        location=right_arm_mesh_location,
        rotation=(0.0, m.radians(90), 0.0)
    )
    body_meshes.append(bpy.context.active_object)
    # Add subdivisions to the mesh so it bends properly
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.subdivide(number_cuts=cylinder_cuts)
    bpy.ops.object.mode_set(mode="OBJECT")
    # Left Arm
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=left_arm_mesh_radius,
        depth=left_arm_mesh_length,
        end_fill_type='NGON',
        calc_uvs=True,
        enter_editmode=False,
        align='WORLD',
        location=left_arm_mesh_location,
        rotation=(0.0, m.radians(90), 0.0)
    )
    body_meshes.append(bpy.context.active_object)
    # Add subdivisions to the mesh so it bends properly
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.subdivide(number_cuts=cylinder_cuts)
    bpy.ops.object.mode_set(mode="OBJECT")
    # Right Hand
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=right_hand_mesh_radius,
        enter_editmode=False,
        align='WORLD',
        location=right_hand_mesh_location,
        scale=(1.4, 0.8, 0.5)
    )
    body_meshes.append(bpy.context.active_object)
    # Right Thumb
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=right_thumb_mesh_radius,
        enter_editmode=False,
        align='WORLD',
        location=right_thumb_mesh_location,
        scale=(1.0, 1.4, 1.0)
    )
    body_meshes.append(bpy.context.active_object)
    # Left Hand
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=left_hand_mesh_radius,
        enter_editmode=False,
        align='WORLD',
        location=left_hand_mesh_location,
        scale=(1.4, 0.8, 0.5)
    )
    body_meshes.append(bpy.context.active_object)
    # Left Thumb
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=left_thumb_mesh_radius,
        enter_editmode=False,
        align='WORLD',
        location=left_thumb_mesh_location,
        scale=(1.0, 1.4, 1.0)
    )
    body_meshes.append(bpy.context.active_object)
    # Right Leg
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=0.05,
        depth=right_leg_mesh_radius,
        end_fill_type='NGON',
        calc_uvs=True,
        enter_editmode=False,
        align='WORLD',
        location=right_leg_mesh_location,
        rotation=(0.0, 0.0, 0.0)
    )
    body_meshes.append(bpy.context.active_object)
    # Add subdivisions to the mesh so it bends properly
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.subdivide(number_cuts=cylinder_cuts)
    bpy.ops.object.mode_set(mode="OBJECT")
    # Left Leg
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=0.05,
        depth=left_leg_mesh_radius,
        end_fill_type='NGON',
        calc_uvs=True,
        enter_editmode=False,
        align='WORLD',
        location=left_leg_mesh_location,
        rotation=(0.0, 0.0, 0.0)
    )
    body_meshes.append(bpy.context.active_object)
    # Add subdivisions to the mesh so it bends properly
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.subdivide(number_cuts=cylinder_cuts)
    bpy.ops.object.mode_set(mode="OBJECT")
    # Right Foot
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=0.05,
        enter_editmode=False,
        align='WORLD',
        location=right_foot_mesh_location,
        scale=(1.0, 2.3, 1.2)
    )
    body_meshes.append(bpy.context.active_object)
    # Left Foot
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=0.05,
        enter_editmode=False,
        align='WORLD',
        location=left_foot_mesh_location,
        scale=(1.0, 2.3, 1.2)
    )
    body_meshes.append(bpy.context.active_object)
    ### Join all the body_meshes with the trunk mesh
    # Rename the trunk mesh to fmc_mesh
    body_meshes[0].name = "fmc_mesh"
    # Deselect all
    bpy.ops.object.select_all(action='DESELECT')
    # Select all body meshes
    for body_mesh in body_meshes:
        body_mesh.select_set(True)
    # Set fmc_mesh as active
    bpy.context.view_layer.objects.active = body_meshes[0]
    # Join the body meshes
    bpy.ops.object.join()
    ### Parent the fmc_mesh with the rig
    # Select the rig
    rig.select_set(True)
    # Set rig as active
    bpy.context.view_layer.objects.active = rig
    # Parent the mesh and the rig with automatic weights
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')


def mesh_from_file(mesh_path, rig):
    try:
        bpy.ops.import_mesh.ply(filepath=mesh_path)
    except Exception as e:
        logger.error(f"Could not find body_mesh file at {mesh_path}, Error: `{e}`")
        raise FileNotFoundError("Could not find body_mesh file ")
    # Get reference to the rig
    # Get the rig z dimension
    rig_z_dimension = rig.dimensions.z
    # Get the body_mesh z dimension
    body_mesh = bpy.data.objects['body_mesh']
    body_mesh_z_dimension = body_mesh.dimensions.z
    # Calculate the proportion between the rig and the body_mesh
    rig_to_body_mesh = rig_z_dimension / body_mesh_z_dimension
    # Scale the mesh by the rig and body_mesh proportion multiplied by a scale factor
    body_mesh.scale = (rig_to_body_mesh * 1.04, rig_to_body_mesh * 1.04, rig_to_body_mesh * 1.04)
    # Apply transformations to body_mesh (scale must be (1, 1, 1) so it doesn't fail on send2ue export
    # Deselect all
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = body_mesh
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    ### Parent the body_mesh with the rig
    # Select the body_mesh
    body_mesh.select_set(True)
    # Select the rig
    rig.select_set(True)
    # Set rig as active
    bpy.context.view_layer.objects.active = rig
    # Parent the body_mesh and the rig with automatic weights
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
