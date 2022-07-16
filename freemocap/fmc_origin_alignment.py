
import numpy as np
import matplotlib.pyplot as plt


from rich.progress import track


from freemocap import fmc_skeleton_data_holder


def create_vector(point1,point2): 
    """Put two points in, make a vector"""
    vector = point2 - point1
    return vector

def calculate_translation_distance(skeleton_right_heel):
    """Take in the right heel point, and calculate the distance between the right heel and the origin"""

    translation_distance = skeleton_right_heel - [0,0,0]
    return translation_distance 


def translate_skeleton_frame(rotated_skeleton_data_frame, translation_distance):
    """Take in a frame of rotated skeleton data, and apply the translation distance to each point in the skeleton"""

    translated_skeleton_frame = rotated_skeleton_data_frame - translation_distance
    return translated_skeleton_frame

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


def align_skeleton_with_origin(skeleton_data, skeleton_indices ,good_frame, debug = False):

    #skeleton_type_to_plot = session_info['skeleton_type']

    #save_file = this_freemocap_data_array_path/'{}_origin_aligned_skeleton_3D.npy'.format(skeleton_type_to_plot)

    origin = np.array([0, 0, 0])
    x_axis = np.array([1, 0, 0])
    y_axis = np.array([0, 1, 0])
    z_axis = np.array([0, 0, 1])

    x_vector = create_vector(origin,x_axis)
    y_vector = create_vector(origin,y_axis)
    z_vector = create_vector(origin,z_axis)

    #origin_normal = create_normal_vector(x_vector,y_vector) #create a normal vector to the origin (basically the z axis)
    origin_normal_unit_vector = z_vector  #note - this is kinda unncessary because the origin normal unit vector == original normal vector 

    num_frames = skeleton_data.shape[0]

    #Original Raw Data
    raw_skeleton_holder = fmc_skeleton_data_holder.SkeletonDataHolder(skeleton_data, skeleton_indices, good_frame)

    raw_good_frame_skeleton_data = raw_skeleton_holder.good_frame_skeleton_data
    raw_mid_hip_XYZ = raw_skeleton_holder.mid_hip_XYZ
    raw_spine_unit_vector = raw_skeleton_holder.spine_unit_vector

    #Translating Data
    mid_hip_translation_distance = calculate_translation_distance(raw_mid_hip_XYZ)
    hip_translated_skeleton_data = np.zeros(skeleton_data.shape)
    foot_translated_skeleton_data = hip_translated_skeleton_data.copy()

    for frame in track(range(num_frames), description = 'Translating Skeleton Hips to Origin'):
        hip_translated_skeleton_data[frame,:,:] = translate_skeleton_frame(skeleton_data[frame,:,:],mid_hip_translation_distance) #translate the skeleton data for each frame  

    hip_translated_skeleton_holder = fmc_skeleton_data_holder.SkeletonDataHolder(hip_translated_skeleton_data, skeleton_indices, good_frame)
    hip_translated_mid_foot_XYZ = hip_translated_skeleton_holder.mid_foot_XYZ

    mid_foot_translated_distance = calculate_translation_distance(hip_translated_mid_foot_XYZ)

    for frame in track (range(num_frames), description = 'Translating Skeleton Feet to Origin'):
        foot_translated_skeleton_data[frame,:,:] = translate_skeleton_frame(hip_translated_skeleton_data[frame,:,:],mid_foot_translated_distance)

    foot_translated_skeleton_holder = fmc_skeleton_data_holder.SkeletonDataHolder(foot_translated_skeleton_data, skeleton_indices, good_frame)
    foot_translated_good_frame_skeleton_data = foot_translated_skeleton_holder.good_frame_skeleton_data 

    foot_translated_mid_hip_XYZ = foot_translated_skeleton_holder.mid_hip_XYZ
    foot_translated_spine_unit_vector = foot_translated_skeleton_holder.spine_unit_vector

    foot_translated_heel_unit_vector = foot_translated_skeleton_holder.heel_unit_vector
    foot_translated_heel_vector_origin = foot_translated_skeleton_holder.heel_vector_origin

    #Rotating for +y alignment

    rotation_matrix_to_align_skeleton_with_positive_y = calculate_rotation_matrix(foot_translated_heel_unit_vector,-1*x_vector)

    y_aligned_skeleton_data = np.zeros(skeleton_data.shape)

    for frame in track(range(num_frames), description = 'Rotating Feet to Align with Positive Y'):
        y_aligned_skeleton_data [frame,:,:] = rotate_skeleton_frame(foot_translated_skeleton_data[frame,:,:],rotation_matrix_to_align_skeleton_with_positive_y)

    y_aligned_skeleton_holder = fmc_skeleton_data_holder.SkeletonDataHolder(y_aligned_skeleton_data, skeleton_indices, good_frame)
    y_aligned_good_frame_skeleton_data = y_aligned_skeleton_holder.good_frame_skeleton_data

    y_aligned_mid_hip_XYZ = y_aligned_skeleton_holder.mid_hip_XYZ
    y_aligned_spine_unit_vector = y_aligned_skeleton_holder.spine_unit_vector

    y_aligned_heel_unit_vector = y_aligned_skeleton_holder.heel_unit_vector
    y_aligned_heel_vector_origin = y_aligned_skeleton_holder.heel_vector_origin

    #Rotating for spine alignment

    spine_aligned_skeleton_data = np.zeros(skeleton_data.shape)

    rotation_matrix_to_align_spine = calculate_rotation_matrix(y_aligned_spine_unit_vector,origin_normal_unit_vector)

    for frame in track(range(num_frames), description = 'Rotating Spine to Align with Positive Z'):
        spine_aligned_skeleton_data [frame,:,:] = rotate_skeleton_frame(y_aligned_skeleton_data[frame,:,:],rotation_matrix_to_align_spine)

    spine_aligned_skeleton_holder = fmc_skeleton_data_holder.SkeletonDataHolder(spine_aligned_skeleton_data, skeleton_indices, good_frame)
    spine_aligned_good_frame_skeleton_data = spine_aligned_skeleton_holder.good_frame_skeleton_data

    spine_aligned_mid_hip_XYZ = spine_aligned_skeleton_holder.mid_hip_XYZ
    spine_aligned_spine_unit_vector = spine_aligned_skeleton_holder.spine_unit_vector

    spine_aligned_heel_unit_vector = spine_aligned_skeleton_holder.heel_unit_vector
    spine_aligned_heel_vector_origin = spine_aligned_skeleton_holder.heel_vector_origin




    if debug:
            def plot_origin_vectors(plot_ax,x_vector,y_vector,z_vector,origin):
                Zvector_X,Zvector_Y,Zvector_Z = zip(origin_normal_unit_vector*800)
                Xvector_X,Xvector_Y,Xvector_Z = zip(x_vector*800)
                Yvector_X,Yvector_Y,Yvector_Z = zip(y_vector*800)

                Origin_X,Origin_Y,Origin_Z = zip(origin)

                plot_ax.quiver(Origin_X,Origin_Y,Origin_Z,Zvector_X,Zvector_Y,Zvector_Z,arrow_length_ratio=0.1,color='b', label = 'Z-axis')
                plot_ax.quiver(Origin_X,Origin_Y,Origin_Z,Xvector_X,Xvector_Y,Xvector_Z,arrow_length_ratio=0.1,color='r', label = 'X-axis')
                plot_ax.quiver(Origin_X,Origin_Y,Origin_Z,Yvector_X,Yvector_Y,Yvector_Z,arrow_length_ratio=0.1,color='g', label = 'Y-axis')
            
            def set_axes_ranges(plot_ax,skeleton_data, ax_range):

                mx = np.nanmean(skeleton_data[:,0])
                my = np.nanmean(skeleton_data[:,1])
                mz = np.nanmean(skeleton_data[:,2])
            
                plot_ax.set_xlim(mx-ax_range,mx+ax_range)
                plot_ax.set_ylim(my-ax_range,my+ax_range)
                plot_ax.set_zlim(mz-ax_range,mz+ax_range)        

            def plot_spine_unit_vector(plot_ax,skeleton_data,skeleton_mid_hip_XYZ,skeleton_spine_unit_vector):

                skeleton_spine_unit_x, skeleton_spine_unit_y, skeleton_spine_unit_z = zip(skeleton_spine_unit_vector*800)

                plot_ax.quiver(skeleton_mid_hip_XYZ[0],skeleton_mid_hip_XYZ[1],skeleton_mid_hip_XYZ[2], skeleton_spine_unit_x,skeleton_spine_unit_y,skeleton_spine_unit_z,arrow_length_ratio=0.1,color='pink')

            def plot_heel_unit_vector(plot_ax,skeleton_heel_unit_vector, heel_vector_origin_XYZ):

                origin_heel_x, origin_heel_y, origin_heel_z = zip(heel_vector_origin_XYZ)

                skeleton_heel_unit_x, skeleton_heel_unit_y, skeleton_heel_unit_z = zip(skeleton_heel_unit_vector*500)

                plot_ax.quiver(origin_heel_x,origin_heel_y,origin_heel_z, skeleton_heel_unit_x,skeleton_heel_unit_y,skeleton_heel_unit_z,arrow_length_ratio=0.1,color='orange')

            
            figure = plt.figure()
            ax1 = figure.add_subplot(221,projection = '3d')
            ax2 = figure.add_subplot(222,projection = '3d')
            ax3 = figure.add_subplot(223,projection = '3d')
            ax4 = figure.add_subplot(224,projection = '3d')

            ax1.set_title('Original Skeleton')
            ax2.set_title('Skeleton Translated to Origin')
            ax3.set_title('Skeleton Rotated to Make +Y Forwards')
            ax4.set_title('Skeleton Rotated to Make +Z Up')

            ax_range = 1800

            set_axes_ranges(ax1,raw_good_frame_skeleton_data,ax_range)
            ax1.scatter(raw_good_frame_skeleton_data[:,0],raw_good_frame_skeleton_data[:,1],raw_good_frame_skeleton_data[:,2],c='r')
            plot_origin_vectors(ax1,x_vector,y_vector,z_vector,origin)
            plot_spine_unit_vector(ax1,raw_good_frame_skeleton_data,raw_mid_hip_XYZ,raw_spine_unit_vector)

            set_axes_ranges(ax2,foot_translated_good_frame_skeleton_data,ax_range)
            plot_origin_vectors(ax2,x_vector,y_vector,z_vector,origin)
            ax2.scatter(foot_translated_good_frame_skeleton_data[:,0],foot_translated_good_frame_skeleton_data[:,1],foot_translated_good_frame_skeleton_data[:,2],c='r')
            plot_heel_unit_vector(ax2,foot_translated_heel_unit_vector,foot_translated_heel_vector_origin)

            set_axes_ranges(ax3,y_aligned_good_frame_skeleton_data,ax_range)
            plot_origin_vectors(ax3,x_vector,y_vector,z_vector,origin)
            ax3.scatter(y_aligned_good_frame_skeleton_data[:,0],y_aligned_good_frame_skeleton_data[:,1],y_aligned_good_frame_skeleton_data[:,2],c='r')
            plot_heel_unit_vector(ax3,y_aligned_heel_unit_vector,y_aligned_heel_vector_origin)
            plot_spine_unit_vector(ax3,y_aligned_good_frame_skeleton_data,y_aligned_mid_hip_XYZ,y_aligned_spine_unit_vector)
            ax3.legend()

            set_axes_ranges(ax4,spine_aligned_good_frame_skeleton_data,ax_range)
            plot_origin_vectors(ax4,x_vector,y_vector,z_vector,origin)
            ax4.scatter(spine_aligned_good_frame_skeleton_data[:,0],spine_aligned_good_frame_skeleton_data[:,1],spine_aligned_good_frame_skeleton_data[:,2],c='r')
            plot_heel_unit_vector(ax4,spine_aligned_heel_unit_vector,spine_aligned_heel_vector_origin)
            plot_spine_unit_vector(ax4,spine_aligned_good_frame_skeleton_data,spine_aligned_mid_hip_XYZ,spine_aligned_spine_unit_vector)

            plt.show()
    
    return spine_aligned_skeleton_data

