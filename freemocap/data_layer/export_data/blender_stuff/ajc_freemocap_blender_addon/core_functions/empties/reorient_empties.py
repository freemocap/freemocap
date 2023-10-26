import math as m
from typing import Dict

import bpy
import mathutils

from ajc_freemocap_blender_addon.core_functions.empties.translate_empty_and_its_children import translate_empty_and_its_children


def reorient_empties(empties: Dict[str, bpy.types.Object],
                     z_align_ref_empty: str,
                     z_align_angle_offset: float,
                     ground_ref_empty: str,
                     z_translation_offset: float,
                     correct_fingers_empties: bool,
                     parent_object: bpy.types.Object):
    # Reference to the global adjust_empties_executed variable
    global REORIENT_EMPTIES_EXECUTED
    # Reference to the global origin location and rotation pre reset variables
    global ORIGIN_LOCATION_PRE_RESET
    global ORIGIN_ROTATION_PRE_RESET

    # Get the scene context
    scene = bpy.context.scene

    # Play and stop the animation in case the first frame empties are in a strange position
    bpy.ops.screen.animation_play()
    bpy.ops.screen.animation_cancel()

    # unparent empties
    empties_list = []
    for child in parent_object.children:
        empties_list.append(child)
        child.parent = None

    ### Move freemocap_origin_axes to the hips_center empty and rotate it so the ###
    ### z axis intersects the trunk_center empty and the x axis intersects the left_hip empty ###
    body_origin = parent_object

    hips_center = empties['hips_center']
    left_hip = empties['left_hip']

    # Move origin to hips_center
    body_origin.location = hips_center.location

    # Rotate origin in the xy plane so its x axis crosses the vertical projection of left_hip
    # Obtain left_hip location
    left_hip_location = left_hip.location

    # Calculate left_hip xy coordinates from origin location
    left_hip_x_from_origin = left_hip_location[0] - body_origin.location[0]
    left_hip_y_from_origin = left_hip_location[1] - body_origin.location[1]

    # Calculate angle from origin x axis to projection of left_hip on xy plane. It will depend if left_hip_x_from_origin is positive or negative
    left_hip_xy_angle_prev = m.atan(left_hip_y_from_origin / left_hip_x_from_origin)
    left_hip_xy_angle = left_hip_xy_angle_prev if left_hip_x_from_origin >= 0 else m.radians(
        180) + left_hip_xy_angle_prev

    # Rotate origin around the z axis to point at left_hip
    body_origin.rotation_euler[2] = left_hip_xy_angle

    # Calculate left_hip z position from origin
    left_hip_z_from_origin = left_hip_location[2] - body_origin.location[2]

    # left_hip_z_from_origin = abs(left_hip_location[2]) - abs(origin.location[2])
    # Calculate angle from origin local x axis to the position of left_hip on origin xz plane
    left_hip_xz_angle = m.atan(
        left_hip_z_from_origin / m.sqrt(m.pow(left_hip_x_from_origin, 2) + m.pow(left_hip_y_from_origin, 2)))

    # Rotate origin around the local y axis to point at left_hip. The angle is multiplied by -1 because is the origin that is rotating
    body_origin.rotation_euler.rotate_axis("Y", left_hip_xz_angle * -1)

    ### Calculate angle in the local yz plane to rotate origin so its z axis crosses the z_align_empty ###
    ### Preferably the trunk_center or left_knee ###
    # Get the z_align_empty object
    z_align_empty = empties[z_align_ref_empty]
    # Get z_align_empty location from origin
    z_align_empty_loc_from_origin = z_align_empty.location - body_origin.location
    # Get the vector distance
    z_align_empty_from_origin_dist = z_align_empty_loc_from_origin.length
    # Get the location vector normalized
    z_align_empty_loc_from_origin_norm = z_align_empty_loc_from_origin.normalized()
    # Rotate the normalized vector with the current origin rotation
    # Get the matrix of origin euler rotation
    origin_rot_matrix = body_origin.rotation_euler.to_matrix()
    # Rotate the trunk center location normalized vector by the origin rotation matrix
    z_align_empty_loc_from_origin_norm_rot = z_align_empty_loc_from_origin_norm @ origin_rot_matrix
    # Calculate rotation angle of the trunk center on the origin local yz plane using the rotated normalized vector
    z_align_empty_yz_rot_angle = m.atan(
        z_align_empty_loc_from_origin_norm_rot[1] / z_align_empty_loc_from_origin_norm_rot[2])

    # Rotate the origin on its local yz plane. The angle is multiply by -1 because its the origin that is rotating
    body_origin.rotation_euler.rotate_axis("X", (z_align_empty_yz_rot_angle + m.radians(z_align_angle_offset)) * -1)

    ### Move the origin along its local z axis to place it at an imaginary "capture ground plane" ###
    ### Preferable be placed at a heel or foot_index level ###
    # Get the ground reference empty object
    ground_empty = empties[ground_ref_empty]
    # Get ground_empty location from origin
    ground_empty_loc_from_origin = ground_empty.location - body_origin.location
    # Get the vector distance
    ground_empty_from_origin_dist = ground_empty_loc_from_origin.length

    # Get the location vector normalized
    ground_empty_loc_from_origin_norm = ground_empty_loc_from_origin.normalized()
    # Rotate the normalized vector with the current origin rotation
    # Get the matrix of origin euler rotation
    origin_rot_matrix = body_origin.rotation_euler.to_matrix()
    # Rotate the ground empty location normalized vector by the origin rotation matrix
    ground_empty_loc_from_origin_norm_rot = ground_empty_loc_from_origin_norm @ origin_rot_matrix

    # Calculate the ground empty z position in the origin local axis
    ground_empty_z_in_local_origin = ground_empty_from_origin_dist * ground_empty_loc_from_origin_norm_rot[2]

    ### Move the origin along its local z axis to align it to the ground_empty empty ###

    # Create the translation vector in the origin local axis
    origin_translation_vector = mathutils.Vector([0, 0, (ground_empty_z_in_local_origin + z_translation_offset)])
    # Invert the origin rotation matrix so it converts from local to global space
    origin_rot_matrix.invert()
    # Rotate the origin translation vector with the inversed rotation matrix
    origin_translation_vector_global = origin_translation_vector @ origin_rot_matrix

    # Translate the origin using the translation_vector_global
    body_origin.location += origin_translation_vector_global

    # Save the body_origin world matrix
    ORIGIN_LOCATION_PRE_RESET = (body_origin.location[0], body_origin.location[1], body_origin.location[2])
    ORIGIN_ROTATION_PRE_RESET = (
        body_origin.rotation_euler[0], body_origin.rotation_euler[1], body_origin.rotation_euler[2])

    # Deselect all
    bpy.ops.object.select_all(action='DESELECT')

    # ### Reparent all the capture empties to the origin  ###
    for empty in empties_list:
        empty.select_set(True)

    # Set the origin active in 3Dview
    bpy.context.view_layer.objects.active = body_origin
    # Parent selected empties to origin keeping transforms
    bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)
    # Reset origin transformation to world origin
    body_origin.location = mathutils.Vector([0, 0, 0])
    body_origin.rotation_euler = mathutils.Vector([0, 0, 0])

    # Deselect all objects
    for object in bpy.data.objects:
        object.select_set(False)

    # Adjust the position of the finger tracking empties. Move right_hand_wrist (and all its child empties) to match the right_wrist position
    if correct_fingers_empties:
        hand_side = ['right', 'left']

        # Iterate through each scene frame and calculate the position delta from x_hand_wrist to x_wrist and move all the fingers empties by that delta
        for frame in range(scene.frame_start, scene.frame_end):
            # Set scene frame
            scene.frame_set(frame)

            for side in hand_side:
                hand_empties = empties['hands'][side]
                body_wrist_empty = empties[side + '_wrist']
                hand_wrist_empty = hand_empties[side + '_hand_wrist']
                # Get the position delta
                position_delta = body_wrist_empty.location - hand_wrist_empty.location

                # Translate the hand_wrist empty and its children by the position delta
                translate_empty_and_its_children(empty_name=side + '_hand_wrist',
                                                 frame_index=frame,
                                                 delta=position_delta, )

    # Deselect all objects
    bpy.ops.object.select_all(action='DESELECT')
    parent_object.select_set(True)

    # Change the adjust_empties_executed variable
    REORIENT_EMPTIES_EXECUTED = True


def clean_existing_freemocap_stuff():
    ### Delete sphere meshes ###
    for object in bpy.data.objects:
        if "sphere" in object.name:
            bpy.data.objects.remove(object, do_unlink=True)
    ### Unparent empties from freemocap_origin_axes ###
    for object in bpy.data.objects:
        if object.type == "EMPTY" and object.name != "freemocap_origin_axes" and object.name != "world_origin":
            object.parent = None
