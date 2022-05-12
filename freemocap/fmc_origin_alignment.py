
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path 
from rich.progress import track 

def align_skeleton_with_origin(session, mediapipe_skeleton_data_XYZ, good_clean_frame_number):

    #skeleton_data_path = session.dataArrayPath/'mediaPipeSkel_3d_smoothed.npy'
    debug = False
    right_heel_index = 30
    right_toe_index = 32
    left_heel_index = 29
    left_toe_index = 31

    num_pose_joints = 33

    primary_foot_indices = [left_heel_index,left_toe_index]
    secondary_foot_index = [right_heel_index]
    num_frames = session.numFrames
    base_frame = good_clean_frame_number #just changing the variable names to work with the code I wrote 
    ## functions used in getting a matrix
    def create_vector(point1,point2): 
        """Put two points in, make a vector [point1,point2]"""
        vector = point2 - point1
        return vector

    def create_normal_vector(vector1,vector2): 
        """Put two vectors in, make a normal vector"""
        normal_vector = np.cross(vector1,vector2)
        return normal_vector

    def create_unit_vector(vector): 
        """Take in a vector, make it a unit vector"""
        unit_vector = vector/np.linalg.norm(vector)
        return unit_vector

    def calculate_skewed_symmetric_cross_product(cross_product_vector):
        skew_symmetric_cross_product = np.array([[0, -cross_product_vector[2], cross_product_vector[1]],
                                                [cross_product_vector[2], 0, -cross_product_vector[0]],
                                                [-cross_product_vector[1], cross_product_vector[0], 0]])
        return skew_symmetric_cross_product

    def calculate_rotation_matrix(vector1,vector2):
        """Put in two vectors to calculate the rotation matrix between those two vectors"""
        #based on the code found here: https://math.stackexchange.com/questions/180418/calculate-rotation-matrix-to-align-vector-a-to-vector-b-in-3d"""
        identity_matrix = np.identity(3)
        vector_cross_product = np.cross(vector1,vector2)
        vector_dot_product = np.dot(vector1,vector2)
        skew_symmetric_cross_product = calculate_skewed_symmetric_cross_product(vector_cross_product)
        rotation_matrix  = identity_matrix + skew_symmetric_cross_product + (np.dot(skew_symmetric_cross_product,skew_symmetric_cross_product))*(1 - vector_dot_product)/(np.linalg.norm(vector_cross_product)**2)
        return rotation_matrix

    def rotate_point(point,rotation_matrix):
        rotated_point = np.dot(rotation_matrix,point)
        return rotated_point

    def rotate_skeleton_frame(this_frame_aligned_skeleton_data, rotation_matrix):
        """Take in a frame of skeleton data, and apply the rotation matrix to each point in the skeleton"""
        this_frame_rotated_skeleton = np.zeros(this_frame_aligned_skeleton_data.shape)  #initialize the array to hold the rotated skeleton data for this frame
        num_tracked_points = this_frame_aligned_skeleton_data.shape[0]
        for i in range(num_tracked_points):
            this_frame_rotated_skeleton[i,:] = rotate_point(this_frame_aligned_skeleton_data[i,:],rotation_matrix)
        return this_frame_rotated_skeleton

    def calculate_translation_distance(skeleton_right_heel):
        """Take in the right heel point, and calculate the distance between the right heel and the origin"""
        translation_distance = skeleton_right_heel - [0,0,0]
        return translation_distance 

    def translate_skeleton_frame(rotated_skeleton_data_frame, translation_distance):
        """Take in a frame of rotated skeleton data, and apply the translation distance to each point in the skeleton"""
        translated_skeleton_frame = rotated_skeleton_data_frame - translation_distance
        return translated_skeleton_frame

    def calculate_normal_vector_to_foot(heel_one_index, toe_one_index, heel_two_index, skeleton_data):
        foot_one_vector = create_vector(skeleton_data[heel_one_index,:],skeleton_data[toe_one_index,:])
        heel_vector = create_vector(skeleton_data[heel_one_index,:],skeleton_data[heel_two_index,:])
        foot_normal_vector =  create_normal_vector(heel_vector,foot_one_vector)
        return foot_normal_vector, foot_one_vector, heel_vector

    ##Create the Origin ---------------------------------------------------------------
    origin = np.array([0, 0, 0])
    x_axis = np.array([1, 0, 0])
    y_axis = np.array([0, 1, 0])
    z_axis = np.array([0, 0, 1])

    x_vector = create_vector(origin,x_axis)
    y_vector = create_vector(origin,y_axis)
    z_vector = create_vector(origin,z_axis)

    origin_normal_unit_vector = z_vector

    ##Get the unrotated skeleton data ------------------------------------------------
    base_frame_skeleton_data = mediapipe_skeleton_data_XYZ[base_frame,:,:]
    base_frame_normal_vector_to_foot,base_frame_left_foot_vector,base_frame_heel_vector = calculate_normal_vector_to_foot(left_heel_index,left_toe_index,right_heel_index,base_frame_skeleton_data)

    ##SKELETON TRANSLATION---------------------
    translation_distance = calculate_translation_distance(base_frame_skeleton_data[primary_foot_indices[0],:])
    translated_skeleton_data = np.zeros(mediapipe_skeleton_data_XYZ.shape)
    
    for frame in track(range(num_frames), description= 'Translating Skeleton to Origin'):
        translated_skeleton_data[frame,:,:] = translate_skeleton_frame(mediapipe_skeleton_data_XYZ[frame,:,:],translation_distance) #translate the skeleton data for each frame  


    
    ##SKELETON +Z-AXIS ROTATION/ALIGNMENT---------------------
    translated_base_frame_skeleton_data = translated_skeleton_data[base_frame,:,:] 
    translated_normal_vector_to_left_foot, translated_left_foot_vector, translated_heel_vector = calculate_normal_vector_to_foot(primary_foot_indices[0],primary_foot_indices[1], secondary_foot_index[0],translated_base_frame_skeleton_data)
    unit_translated_normal_vector_to_left_foot = create_unit_vector(translated_normal_vector_to_left_foot)

    rotation_matrix = calculate_rotation_matrix(unit_translated_normal_vector_to_left_foot,origin_normal_unit_vector)

    translated_and_rotated_skeleton_data = np.zeros(mediapipe_skeleton_data_XYZ.shape) #create an array to hold the rotated skeleton data

    for frame in track(range(num_frames), description= 'Rotating Skeleton to Align With +Z'): #rotate the skeleton on each frame 
        translated_and_rotated_skeleton_data[frame,:,:] = rotate_skeleton_frame(translated_skeleton_data[frame,:,:],rotation_matrix)

    ##SKELETON +Y-AXIS ALIGNMENT---------------------

    translated_and_rotated_base_frame_skeleton_data = translated_and_rotated_skeleton_data[base_frame,:,:]
    translated_and_rotated_normal_vector_to_left_foot, translated_and_rotated_left_foot_vector, translated_and_rated_heel_vector  = calculate_normal_vector_to_foot(primary_foot_indices[0],primary_foot_indices[1], secondary_foot_index[0],translated_and_rotated_base_frame_skeleton_data)
    
    unit_translated_and_rotated_normal_vector_to_left_foot = create_unit_vector(translated_and_rotated_normal_vector_to_left_foot)

    translated_and_rotated_heel_vector_for_y_axis_rotation = create_vector(translated_and_rotated_skeleton_data[base_frame,right_heel_index,:],translated_and_rotated_skeleton_data[base_frame,left_heel_index,:])
    unit_translated_and_rotated_heel_vector = create_unit_vector(translated_and_rotated_heel_vector_for_y_axis_rotation)

    rotation_matrix_to_align_skeleton_with_positive_y = calculate_rotation_matrix(unit_translated_and_rotated_heel_vector,-1*x_vector)

    
    origin_aligned_skeleton_data = np.zeros(mediapipe_skeleton_data_XYZ.shape)

    for frame in track(range(num_frames),description= 'Rotating Skeleton to Align With +Y'):
        origin_aligned_skeleton_data[frame,:,:] = rotate_skeleton_frame(translated_and_rotated_skeleton_data[frame,:,:],rotation_matrix_to_align_skeleton_with_positive_y)

    origin_aligned_base_frame_skeleton_data = origin_aligned_skeleton_data[base_frame,:,:]
    origin_aligned_normal_vector_to_left_foot, origin_aligned_left_foot_vector, origin_aligned_heel_vector = calculate_normal_vector_to_foot(primary_foot_indices[0],primary_foot_indices[1], secondary_foot_index[0],origin_aligned_base_frame_skeleton_data)



    if debug:

        def plot_origin_vectors(plot_ax,x_vector,y_vector,z_vector,origin):
            Zvector_X,Zvector_Y,Zvector_Z = zip(origin_normal_unit_vector*800)
            Xvector_X,Xvector_Y,Xvector_Z = zip(x_vector*800)
            Yvector_X,Yvector_Y,Yvector_Z = zip(y_vector*800)

            Origin_X,Origin_Y,Origin_Z = zip(origin)

            plot_ax.quiver(Origin_X,Origin_Y,Origin_Z,Zvector_X,Zvector_Y,Zvector_Z,arrow_length_ratio=0.1,color='b', label = 'Z-axis')
            plot_ax.quiver(Origin_X,Origin_Y,Origin_Z,Xvector_X,Xvector_Y,Xvector_Z,arrow_length_ratio=0.1,color='r', label = 'X-axis')
            plot_ax.quiver(Origin_X,Origin_Y,Origin_Z,Yvector_X,Yvector_Y,Yvector_Z,arrow_length_ratio=0.1,color='g', label = 'Y-axis')

        def calculate_COM(skeleton_data):
            COM_XYZ = np.nanmean(skeleton_data,axis=0)
            return COM_XYZ

        def calculate_COM_ground_projection_y(center_of_mass_XYZ, skeleton_data):
            projection_distance = center_of_mass_XYZ[1] - skeleton_data[right_heel_index,1]
            COM_ground_projected_XYZ = center_of_mass_XYZ - projection_distance*np.array([0,1,0])

            return COM_ground_projected_XYZ

        def calculate_COM_ground_projection_z(center_of_mass_XYZ, skeleton_data):
            projection_distance = center_of_mass_XYZ[2] - skeleton_data[right_heel_index,2]
            COM_ground_projected_XYZ = center_of_mass_XYZ - projection_distance*np.array([0,0,1])
            
            return COM_ground_projected_XYZ


        def plot_normal_unit_vector_to_foot(normal_vector_to_foot, origin_foot_index, skeleton_data,plot_ax):

            normal_vector_to_foot_unit_vector = create_unit_vector(normal_vector_to_foot)

            normal_vector_to_foot_X,normal_vector_to_foot_Y,normal_vector_to_foot_Z = zip(normal_vector_to_foot_unit_vector*800)
            plot_ax.quiver(skeleton_data[origin_foot_index,0],skeleton_data[origin_foot_index,1],skeleton_data[origin_foot_index,2],normal_vector_to_foot_X,normal_vector_to_foot_Y,normal_vector_to_foot_Z,arrow_length_ratio=0.1,color='pink')

        def set_axes_ranges(plot_ax,skeleton_data, ax_range):

            mx = np.nanmean(skeleton_data[:,0])
            my = np.nanmean(skeleton_data[:,1])
            mz = np.nanmean(skeleton_data[:,2])
        
            plot_ax.set_xlim(mx-ax_range,mx+ax_range)
            plot_ax.set_ylim(my-ax_range,my+ax_range)
            plot_ax.set_zlim(mz-ax_range,mz+ax_range)

        def plot_COM_point_and_projection(plot_ax,COM_XYZ,COM_ground_projected_XYZ):

            plot_ax.scatter(COM_XYZ[0],COM_XYZ[1],COM_XYZ[2],color='b')
            plot_ax.scatter(COM_ground_projected_XYZ[0],COM_ground_projected_XYZ[1],COM_ground_projected_XYZ[2], color = 'b')
            plot_ax.plot([COM_XYZ[0],COM_ground_projected_XYZ[0]],[COM_XYZ[1],COM_ground_projected_XYZ[1]],[COM_XYZ[2],COM_ground_projected_XYZ[2]],color='b', alpha = .5)

        figure = plt.figure()
        ax1 = figure.add_subplot(221,projection = '3d')
        ax2 = figure.add_subplot(222,projection = '3d')
        ax3 = figure.add_subplot(223,projection = '3d')
        ax4 = figure.add_subplot(224,projection = '3d')

        ax1.set_title('Original Skeleton')
        ax2.set_title('Skeleton Translated to Origin')
        ax3.set_title('Skeleton Rotated to Make +Z Up')
        ax4.set_title('Skeleton Rotated to Make +Y Forwards')

        ax_range = 1800


        set_axes_ranges(ax1,base_frame_skeleton_data,ax_range)
        set_axes_ranges(ax2,translated_base_frame_skeleton_data,ax_range)
        set_axes_ranges(ax3,translated_and_rotated_base_frame_skeleton_data,ax_range)
        set_axes_ranges(ax4,origin_aligned_base_frame_skeleton_data,ax_range)


        ax1.scatter(base_frame_skeleton_data[:,0],base_frame_skeleton_data[:,1],base_frame_skeleton_data[:,2],c='r')
        plot_origin_vectors(ax1,x_vector,y_vector,z_vector,origin)

        original_COM_XYZ = calculate_COM(base_frame_skeleton_data[0:num_pose_joints,:])
        original_COM_XYZ_ground_projection = calculate_COM_ground_projection_y(original_COM_XYZ,base_frame_skeleton_data)

        plot_COM_point_and_projection(ax1,original_COM_XYZ,original_COM_XYZ_ground_projection)
        plot_normal_unit_vector_to_foot(base_frame_normal_vector_to_foot,primary_foot_indices[0],base_frame_skeleton_data,ax1)

        ax2.scatter(translated_base_frame_skeleton_data[:,0],translated_base_frame_skeleton_data[:,1],translated_base_frame_skeleton_data[:,2],c='g')
        plot_origin_vectors(ax2,x_vector,y_vector,z_vector,origin)

        translated_COM_XYZ = calculate_COM(translated_base_frame_skeleton_data[0:num_pose_joints,:])
        translated_COM_XYZ_ground_projection = calculate_COM_ground_projection_y(translated_COM_XYZ,translated_base_frame_skeleton_data)

        plot_COM_point_and_projection(ax2,translated_COM_XYZ,translated_COM_XYZ_ground_projection)
        plot_normal_unit_vector_to_foot(translated_normal_vector_to_left_foot,primary_foot_indices[0],translated_base_frame_skeleton_data,ax2)

        
        ax3.scatter(translated_and_rotated_base_frame_skeleton_data[:,0],translated_and_rotated_base_frame_skeleton_data[:,1],translated_and_rotated_base_frame_skeleton_data[:,2],c='orange')
        plot_origin_vectors(ax3,x_vector,y_vector,z_vector,origin)

        z_rotated_COM_XYZ = calculate_COM(translated_and_rotated_base_frame_skeleton_data[0:num_pose_joints,:])
        z_rotated_COM_XYZ_ground_projection = calculate_COM_ground_projection_z(z_rotated_COM_XYZ,translated_and_rotated_base_frame_skeleton_data)

        plot_COM_point_and_projection(ax3,z_rotated_COM_XYZ,z_rotated_COM_XYZ_ground_projection)
        plot_normal_unit_vector_to_foot(translated_and_rotated_normal_vector_to_left_foot,primary_foot_indices[0],translated_and_rotated_base_frame_skeleton_data,ax3)
        # ax3.quiver(rotated_right_heel_x,rotated_right_heel_y,rotated_right_heel_z,rotated_foot_x,rotated_foot_y,rotated_foot_z,arrow_length_ratio=0.1,color='pink')
        # ax3.quiver(rotated_right_heel_x,rotated_right_heel_y,rotated_right_heel_z,rotated_left_heel_x,rotated_left_heel_y,rotated_left_heel_z,arrow_length_ratio=0.1,color='pink')

        ax4.scatter(origin_aligned_base_frame_skeleton_data[:,0],origin_aligned_base_frame_skeleton_data[:,1],origin_aligned_base_frame_skeleton_data[:,2],c='purple')
        plot_origin_vectors(ax4,x_vector,y_vector,z_vector,origin)

        origin_aligned_COM_XYZ = calculate_COM(origin_aligned_base_frame_skeleton_data[0:num_pose_joints,:])
        origin_aligned_COM_XYZ_ground_projection = calculate_COM_ground_projection_z(origin_aligned_COM_XYZ,origin_aligned_base_frame_skeleton_data)
        
        plot_COM_point_and_projection(ax4,origin_aligned_COM_XYZ,origin_aligned_COM_XYZ_ground_projection)
        plot_normal_unit_vector_to_foot(origin_aligned_normal_vector_to_left_foot,left_heel_index,origin_aligned_base_frame_skeleton_data,ax4)
        # ax4.quiver(origin_aligned_right_heel_x,origin_aligned_right_heel_y,origin_aligned_right_heel_z,origin_aligned_left_heel_x,origin_aligned_left_heel_y,origin_aligned_left_heel_z,arrow_length_ratio=0.1,color='pink')
    
        ax1.legend()
        ax2.legend()
        ax3.legend()
        plt.show()


    return origin_aligned_skeleton_data













    







