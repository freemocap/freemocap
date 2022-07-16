
import numpy as np
import matplotlib.pyplot as plt




def find_velocity_values_within_limit(skeleton_velocity_data, velocity_limit):
    """
    This function takes in a skeleton velocity data array and a limit and returns the indices of the values that are within the limit
    """
    indices = []
    for i in range(len(skeleton_velocity_data)):
        if abs(skeleton_velocity_data[i]) <= velocity_limit:
            indices.append(i+1) #add 1 to account for the difference in indices between the position and velocity data
    return indices

def find_matching_indices_in_lists(list_1,list_2,list_3,list_4):
    """
    This function takes in four lists and returns the indices of the values that are in all four lists
    """
    matching_values = [x for x in list_1 if x in list_2 and x in list_3 and x in list_4]

    return matching_values

def find_best_velocity_guess(skeleton_velocity_data, velocity_guess, iteration_range):
    """
    This function iterates over velocity data and tries to pare down to a single frame that has the closest velocity to 0 for all foot markers
    """

    right_heel_index = 30
    right_toe_index = 32
    left_heel_index = 29
    left_toe_index = 31

    skeleton_data_velocity_x_right_heel = skeleton_velocity_data[:,right_heel_index,0]
    skeleton_data_velocity_x_right_toe = skeleton_velocity_data[:,right_toe_index,0]
    skeleton_data_velocity_x_left_heel = skeleton_velocity_data[:,left_heel_index,0]
    skeleton_data_velocity_x_left_toe = skeleton_velocity_data[:,left_toe_index,0]

    #get a list of the frames where the velocity for that marker is within the velocity limit 
    right_heel_x_velocity_limits = find_velocity_values_within_limit(skeleton_data_velocity_x_right_heel, velocity_guess)
    right_toe_x_velocity_limits = find_velocity_values_within_limit(skeleton_data_velocity_x_right_toe, velocity_guess)
    left_heel_x_velocity_limits = find_velocity_values_within_limit(skeleton_data_velocity_x_left_heel, velocity_guess)
    left_toe_x_velocity_limits = find_velocity_values_within_limit(skeleton_data_velocity_x_left_toe, velocity_guess)

    #return a list of matching frame indices from the four lists generated above 
    matching_values = find_matching_indices_in_lists(right_heel_x_velocity_limits, right_toe_x_velocity_limits, left_heel_x_velocity_limits, left_toe_x_velocity_limits)
    matching_values = [x for x in matching_values if x>75]
    if len(matching_values) < 10:
        print(matching_values)
    if len(matching_values) > 1 and velocity_guess > 0:
        #if there are multiple matching values, decrease the guess a little bit and run the function again
        #  
        velocity_guess = velocity_guess - iteration_range


        print('Current Velocity Guess: ',velocity_guess, '\n','Number of Matching Frames: ', len(matching_values))
        matching_values, velocity_guess = find_best_velocity_guess(skeleton_velocity_data, velocity_guess, iteration_range)

        f = 2
    elif len(matching_values) == 0:
        #if there are no matching values (we decreased our guess too far), reset the guess to be a bit smaller and run the function again with smaller intervals between the guesses
        iteration_range = iteration_range/2
        matching_values, velocity_guess = find_best_velocity_guess(skeleton_velocity_data, velocity_guess + iteration_range*2, iteration_range)

        f = 2
    elif len(matching_values) == 1:
        print('Final Velocity Value: ',velocity_guess, '\n','Good Frame: ', matching_values)

    return matching_values, velocity_guess

def set_axes_ranges(plot_ax,skeleton_data,ax_range):

    mx = np.nanmean(skeleton_data[:,0])
    my = np.nanmean(skeleton_data[:,1])
    mz = np.nanmean(skeleton_data[:,2])

    plot_ax.set_xlim(mx-ax_range,mx+ax_range)
    plot_ax.set_ylim(my-ax_range,my+ax_range)
    plot_ax.set_zlim(mz-ax_range,mz+ax_range)     

def find_good_frame(skeleton_data, initial_velocity_guess, debug = False):

    print('Finding Good Frame')
    skeleton_velocity_data = np.diff(skeleton_data, axis=0)

    matching_values, velocity_guess = find_best_velocity_guess(skeleton_velocity_data, initial_velocity_guess, iteration_range=.1)

    good_frame = matching_values[0]

    if debug:

        figure = plt.figure()
        ax = figure.add_subplot(111, projection = '3d')

        ax.scatter(skeleton_data[good_frame,:,0], skeleton_data[good_frame,:,1], skeleton_data[good_frame,:,2], c='r', marker='o')

        set_axes_ranges(ax, skeleton_data[good_frame,:,:], 1000)

        plt.show()

    return good_frame
