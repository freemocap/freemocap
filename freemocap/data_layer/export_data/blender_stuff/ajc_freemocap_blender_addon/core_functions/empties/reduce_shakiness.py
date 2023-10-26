import math as m

from ajc_freemocap_blender_addon.core_functions.empties.update_empty_positions import get_empty_positions, \
    update_empty_velocities, \
    EMPTY_POSITIONS, EMPTY_VELOCITIES


def reduce_shakiness(recording_fps: float = 30):
    print('fps: ' + str(recording_fps))
    # Update the empty positions dictionary
    get_empty_positions()

    # Update the empty speeds dictionary
    update_empty_velocities(recording_fps)

    # Get the time of each frame in seconds
    seconds_per_frame = 1 / recording_fps

    # for f in range(150, 157):
    #     empty_speed         = empty_speeds['left_wrist']['speed'][f-1]
    #     acceleration        = (empty_speed - empty_speeds['left_wrist']['speed'][f-2]) / seconds_per_frame
    #     print('left_wrist frame ' + str(f) + ' speed: ' + str(empty_speed) + ' acceleration: ' + str(acceleration))

    # for f in range(1160, 1180):
    #     empty_speed         = empty_speeds['right_wrist']['speed'][f-1]
    #     acceleration        = (empty_speed - empty_speeds['right_wrist']['speed'][f-2]) / seconds_per_frame
    #     print('right_wrist frame ' + str(f) + ' speed: ' + str(empty_speed) + ' acceleration: ' + str(acceleration))

    for empty in EMPTY_POSITIONS:
        for frame_index in range(1, len(EMPTY_VELOCITIES[empty]['speed']) - 2):
            empty_speed = EMPTY_VELOCITIES[empty]['speed'][frame_index]
            acceleration = (empty_speed - EMPTY_VELOCITIES[empty]['speed'][frame_index - 1]) / seconds_per_frame

            if acceleration > 10:

                # Get the empty position
                empty_position = mathutils.Vector(
                    [EMPTY_POSITIONS[empty]['x'][frame_index], EMPTY_POSITIONS[empty]['y'][frame_index],
                     EMPTY_POSITIONS[empty]['z'][frame_index]])
                # Get the empty position in the previous frame
                empty_position_prev = mathutils.Vector(
                    [EMPTY_POSITIONS[empty]['x'][frame_index - 1], EMPTY_POSITIONS[empty]['y'][frame_index - 1],
                     EMPTY_POSITIONS[empty]['z'][frame_index - 1]])
                # Get the empty position in the next frame
                empty_position_next = mathutils.Vector(
                    [EMPTY_POSITIONS[empty]['x'][frame_index + 1], EMPTY_POSITIONS[empty]['y'][frame_index + 1],
                     EMPTY_POSITIONS[empty]['z'][frame_index + 1]])

                # Get the direction vector of the empty in the current frame
                empty_direction = empty_position - empty_position_prev

                # Get the direction vector of the empty in the next current
                empty_direction_next = empty_position_next - empty_position

                # Get the addition of the direction vectors
                direction_addition = empty_direction + empty_direction_next

                # Get the the direction addition length
                direction_addition_length = m.dist((0, 0, 0), direction_addition)

                # If the distance is less than the threshold then the current position of the empty is considered a shake
                if direction_addition_length < 0.02:
                    print(empty + ":" + str(frame_index + 1) + ": shake")

                # print(empty_position)
                # print(empty_position_prev)
                # print(empty_direction)
                # print(empty_direction_next)
                # print(direction_addition)
                # print(m.dist((0,0,0), direction_addition))
                # print('right_wrist frame ' + str(frame_index + 1) + ' speed: ' + str(empty_speed) + ' acceleration: ' + str(acceleration))
