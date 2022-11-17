import numpy as np


def find_velocity_values_within_limit(skeleton_velocity_data, velocity_limit):
    """
    This function takes in a skeleton velocity data array and a limit and returns the indices of the values that are within the limit
    """
    indices = []
    for i in range(len(skeleton_velocity_data)):
        if abs(skeleton_velocity_data[i]) <= velocity_limit:
            indices.append(
                i + 1
            )  # add 1 to account for the difference in indices between the position and velocity data
    return indices


# %%


def find_matching_indices_in_lists(list_1, list_2, list_3, list_4):
    """
    This function takes in four lists and returns the indices of the values that are in all four lists
    """
    matching_values = [x for x in list_1 if x in list_2 and x in list_3 and x in list_4]

    return matching_values


# %%


def find_best_velocity_guess(
    skeleton_velocity_data, skeleton_indices, velocity_guess, iteration_range
):
    """
    This function iterates over velocity data and tries to pare down to a single frame that has the closest velocity to 0 for all foot markers
    """

    print(f"Velocity guess: {velocity_guess}, iteration range: {iteration_range}")

    right_heel_index = skeleton_indices.index("right_heel")
    right_toe_index = skeleton_indices.index("right_foot_index")
    left_heel_index = skeleton_indices.index("left_heel")
    left_toe_index = skeleton_indices.index("left_foot_index")

    skeleton_data_velocity_x_right_heel = skeleton_velocity_data[:, right_heel_index, 0]
    skeleton_data_velocity_x_right_toe = skeleton_velocity_data[:, right_toe_index, 0]
    skeleton_data_velocity_x_left_heel = skeleton_velocity_data[:, left_heel_index, 0]
    skeleton_data_velocity_x_left_toe = skeleton_velocity_data[:, left_toe_index, 0]

    print(
        f"sum nan right heel: {np.sum(np.isnan(skeleton_data_velocity_x_right_heel))}, "
        f"\nsum nan right toe: {np.sum(np.isnan(skeleton_data_velocity_x_right_toe))}, "
        f"\nsum nan left heel: {np.sum(np.isnan(skeleton_data_velocity_x_left_heel))}, "
        f"\nsum nan left toe: {np.sum(np.isnan(skeleton_data_velocity_x_left_toe))}, "
        f"\nnum frames: {len(skeleton_data_velocity_x_right_heel)}"
    )

    # get a list of the frames where the velocity for that marker is within the velocity limit
    right_heel_x_velocity_limits = find_velocity_values_within_limit(
        skeleton_data_velocity_x_right_heel, velocity_guess
    )
    right_toe_x_velocity_limits = find_velocity_values_within_limit(
        skeleton_data_velocity_x_right_toe, velocity_guess
    )
    left_heel_x_velocity_limits = find_velocity_values_within_limit(
        skeleton_data_velocity_x_left_heel, velocity_guess
    )
    left_toe_x_velocity_limits = find_velocity_values_within_limit(
        skeleton_data_velocity_x_left_toe, velocity_guess
    )

    # return a list of matching frame indices from the four lists generated above
    matching_values = find_matching_indices_in_lists(
        right_heel_x_velocity_limits,
        right_toe_x_velocity_limits,
        left_heel_x_velocity_limits,
        left_toe_x_velocity_limits,
    )
    matching_values = [x for x in matching_values if x > 75]

    # print(matching_values)
    if len(matching_values) > 1 and velocity_guess > 0:
        # if there are multiple matching values, decrease the guess a little bit and calculate_center_of_mass the function again
        #
        velocity_guess = velocity_guess - iteration_range
        print(
            "Current Velocity Guess:",
            velocity_guess,
            "| Number of Possible Frames:",
            len(matching_values),
            "| Possible Frames:",
            matching_values,
        )
        matching_values, velocity_guess = find_best_velocity_guess(
            skeleton_velocity_data, skeleton_indices, velocity_guess, iteration_range
        )

        f = 2
    elif len(matching_values) == 0:
        # if there are no matching values (we decreased our guess too far), reset the guess to be a bit smaller and calculate_center_of_mass the function again with smaller intervals between the guesses
        iteration_range = iteration_range / 2
        matching_values, velocity_guess = find_best_velocity_guess(
            skeleton_velocity_data,
            skeleton_indices,
            velocity_guess + iteration_range * 2,
            iteration_range,
        )

        f = 2
    elif len(matching_values) == 1:
        print("Good Frame:", matching_values, "| Final Velocity Guess:", velocity_guess)

    return matching_values, velocity_guess


def find_good_frame_recursive_guess_method(
    skeleton_data, skeleton_indices: list, initial_velocity_guess: float,
):
    """
    Finds a frame (called the good frame) where the velocity of both feet are closest to 0

    Input:
        skeleton data: a 3D numpy array of skeleton data in freemocap format
        skeleton indices: a list of joints being tracked by mediapipe/your 2d pose estimator
        initial velocity guess: just a starting guess for the optimizer. Can adjust if you're not getting the results you want
        debug: plots and displays the calculated good frame if True
    """

    skeleton_velocity_data = np.diff(skeleton_data, axis=0)
    print("finding best velocity guess...")
    matching_values, velocity_guess = find_best_velocity_guess(
        skeleton_velocity_data,
        skeleton_indices,
        initial_velocity_guess,
        iteration_range=0.1,
    )
    print(f"Return values: {matching_values}")
    good_frame = matching_values[0]

    return good_frame