import bpy
import mathutils

ORIGIN_LOCATION_PRE_RESET = (0, 0, 0)
ORIGIN_ROTATION_PRE_RESET = (0, 0, 0)


def add_hands_middle_empties():
    # Try checking if the hand middle empties have been already added
    try:
        right_hand_middle_name = bpy.data.objects['right_hand_middle'].name
        # Right Hand Middle Empty exists. Nothing is done
        print('Hand Middle Empties already added.')

    except:
        # Hand Middle Empties do not exist
        print('Adding Hand Middle Empties...')

        # Define the empties that serve as reference to locate the middle empties
        # middle_references = ['index', 'pinky']
        middle_references = ['hand_middle_finger_mcp', 'hand_ring_finger_mcp']

        # Add the empties
        bpy.ops.object.empty_add(type='ARROWS', align='WORLD', location=(0, 0, 0), scale=(0.1, 0.1, 0.1))
        right_hand_middle = bpy.context.active_object
        right_hand_middle.name = 'right_hand_middle'
        right_hand_middle.scale = (0.02, 0.02, 0.02)

        bpy.ops.object.empty_add(type='ARROWS', align='WORLD', location=(0, 0, 0), scale=(0.1, 0.1, 0.1))
        left_hand_middle = bpy.context.active_object
        left_hand_middle.name = 'left_hand_middle'
        left_hand_middle.scale = (0.02, 0.02, 0.02)

        # Copy the action data from the index fingers to have the base
        right_hand_middle.animation_data_create()
        right_hand_middle.animation_data.action = bpy.data.actions["right_" + middle_references[0] + "Action"].copy()
        right_hand_middle.animation_data.action.name = 'right_hand_middleAction'

        left_hand_middle.animation_data_create()
        left_hand_middle.animation_data.action = bpy.data.actions["left_" + middle_references[0] + "Action"].copy()
        left_hand_middle.animation_data.action.name = 'left_hand_middleAction'

        # Move the freemocap_origin_axes empty to the position and rotation previous to the Adjust Empties method ending
        origin = bpy.data.objects['freemocap_origin_axes']
        origin.location = ORIGIN_LOCATION_PRE_RESET
        origin.rotation_euler = ORIGIN_ROTATION_PRE_RESET

        # Select the new empties
        right_hand_middle.select_set(True)
        left_hand_middle.select_set(True)

        # Set the origin active in 3Dview
        bpy.context.view_layer.objects.active = bpy.data.objects['freemocap_origin_axes']
        # Parent selected empties to freemocap_origin_axes keeping transforms
        bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)

        # Reset the position and rotation of the origin
        origin.location = mathutils.Vector([0, 0, 0])
        origin.rotation_euler = mathutils.Vector([0, 0, 0])

        # Create a list with the new hand middle empties
        hand_middle_empties = [right_hand_middle, left_hand_middle]

        # Create a list of the hand sides
        hand_side = ['right', 'left']

        # Iterate through each frame and calculate the middle point between the index and pinky empty markers for each hand
        # Update the new hand middle empties position with that point
        for frame_index in range(0, len(EMPTY_POSITIONS['right_index']['x']) - 1):

            for side_index in range(0, 2):
                # Get the positions of the middle references
                ref0_position = mathutils.Vector(
                    [EMPTY_POSITIONS[hand_side[side_index] + '_' + middle_references[0]]['x'][frame_index],
                     EMPTY_POSITIONS[hand_side[side_index] + '_' + middle_references[0]]['y'][frame_index],
                     EMPTY_POSITIONS[hand_side[side_index] + '_' + middle_references[0]]['z'][frame_index]])
                ref1_position = mathutils.Vector(
                    [EMPTY_POSITIONS[hand_side[side_index] + '_' + middle_references[1]]['x'][frame_index],
                     EMPTY_POSITIONS[hand_side[side_index] + '_' + middle_references[1]]['y'][frame_index],
                     EMPTY_POSITIONS[hand_side[side_index] + '_' + middle_references[1]]['z'][frame_index]])

                # Get the new position of the middle empties
                hand_middle_position = ref0_position + (ref1_position - ref0_position) / 2

                # Update the action property of the middle empty
                hand_middle_empties[side_index].animation_data.action.fcurves[0].keyframe_points[frame_index].co[1] = \
                    hand_middle_position[0]
                hand_middle_empties[side_index].animation_data.action.fcurves[1].keyframe_points[frame_index].co[1] = \
                    hand_middle_position[1]
                hand_middle_empties[side_index].animation_data.action.fcurves[2].keyframe_points[frame_index].co[1] = \
                    hand_middle_position[2]

        print('Adding Hand Middle completed.')
