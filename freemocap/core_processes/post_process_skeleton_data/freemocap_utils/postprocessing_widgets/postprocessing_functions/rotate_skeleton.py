
import numpy as np
from rich.progress import track

def create_vector(point1,point2): 
    """Put two points in, make a vector"""
    vector = point2 - point1
    return vector

def calculate_unit_vector(vector): 
    """Take in a vector, make it a unit vector"""
    unit_vector = vector/np.linalg.norm(vector)
    return unit_vector

def calculate_shoulder_center_XYZ_coordinates(single_frame_skeleton_data,left_shoulder_index,right_shoulder_index ):
    """Take in the left and right shoulder indices, and calculate the shoulder center point"""
    left_shoulder_point = single_frame_skeleton_data[left_shoulder_index,:]
    right_shoulder_point = single_frame_skeleton_data[right_shoulder_index,:]
    shoulder_center_XYZ_coordinates = (left_shoulder_point + right_shoulder_point)/2
    
    return shoulder_center_XYZ_coordinates


def calculate_mid_hip_XYZ_coordinates(single_frame_skeleton_data,left_hip_index,right_hip_index):
    """Take in the left and right hip indices, and calculate the mid hip point"""
    left_hip_point = single_frame_skeleton_data[left_hip_index,:]
    right_hip_point = single_frame_skeleton_data[right_hip_index,:]
    mid_hip_XYZ_coordinates = (left_hip_point + right_hip_point)/2

    return mid_hip_XYZ_coordinates

def calculate_mid_foot_XYZ_coordinate(single_frame_skeleton_data,left_heel_index,right_heel_index,):
    """Take in the primary and secondary foot indices, and calculate the mid foot point"""
    right_foot_point = single_frame_skeleton_data[right_heel_index,:]
    left_foot_point = single_frame_skeleton_data[left_heel_index,:]
    mid_foot_XYZ_coordinates = (right_foot_point + left_foot_point)/2

    return mid_foot_XYZ_coordinates


def translate_skeleton_frame(rotated_skeleton_data_frame, translation_distance):
    """Take in a frame of rotated skeleton data, and apply the translation distance to each point in the skeleton"""

    translated_skeleton_frame = rotated_skeleton_data_frame - translation_distance
    return translated_skeleton_frame

def translate_skeleton_to_origin(point_to_translate, original_skeleton_data):
    num_frames = original_skeleton_data.shape[0]

    translated_skeleton_data = np.zeros(original_skeleton_data.shape)

    for frame in track (range(num_frames), description = 'Translating Skeleton'):
        translated_skeleton_data[frame,:,:] = translate_skeleton_frame(original_skeleton_data[frame,:,:],point_to_translate)

    return translated_skeleton_data

def calculate_skewed_symmetric_cross_product(cross_product_vector):
    #needed in the calculate_rotation_matrix function 
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

def rotate_skeleton_to_vector(reference_vector:np.ndarray, vector_to_rotate_to:np.ndarray, original_skeleton_np_array:np.ndarray) -> np.ndarray:
    """ 
    Find the rotation matrix needed to rotate the 'reference vector' to match the 'vector_to_rotate_to', and 
    rotate the entire skeleton with that matrix.

        Input: 
            Reference Vector: The vector on the skeleton that you want to rotate/base the rotation matrix on 
            Vector_to_rotate_to: The vector that you want to align the skeleton too (i.e. the x-axis/y-axis etc.)
            Original skeleton data: The freemocap data you want to rotate
        Output:
            rotated_skeleton_data: A numpy data array of your rotated skeleton

    """

    num_frames = original_skeleton_np_array.shape[0]
    reference_unit_vector = calculate_unit_vector(reference_vector)
    rotation_matrix = calculate_rotation_matrix(reference_unit_vector, vector_to_rotate_to)

    rotated_skeleton_data_array = np.zeros(original_skeleton_np_array.shape)
    for frame in track(range(num_frames), description = 'Rotating Skeleton'):
        rotated_skeleton_data_array [frame,:,:] = rotate_skeleton_frame(original_skeleton_np_array[frame,:,:],rotation_matrix)

    return rotated_skeleton_data_array






def align_skeleton_with_origin(skeleton_data:np.ndarray, skeleton_indices:list, good_frame:int) -> np.ndarray:

    """
    Takes in freemocap skeleton data and translates the skeleton to the origin, and then rotates the data 
    so that the skeleton is facing the +y direction and standing in the +z direction

    Input:
        skeleton data: a 3D numpy array of skeleton data in freemocap format
        skeleton indices: a list of joints being tracked by mediapipe/your 2d pose estimator
        good frame: the frame that you want to base the rotation on (can be entered manually, 
                    or use the 'good_frame_finder.py' to calculate it)
        debug: If 'True', display a plot of the raw data and the 3 main alignment stages

    Output:
        spine aligned skeleton data: a 3d numpy array of the origin aligned data in freemocap format 
    """
    left_shoulder_index = skeleton_indices.index('left_shoulder')
    right_shoulder_index = skeleton_indices.index('right_shoulder')

    left_hip_index = skeleton_indices.index('left_hip')
    right_hip_index = skeleton_indices.index('right_hip')

    left_heel_index = skeleton_indices.index('left_heel')
    right_heel_index = skeleton_indices.index('right_heel')
    
    origin = np.array([0, 0, 0])
    x_axis = np.array([1, 0, 0])
    y_axis = np.array([0, 1, 0])
    z_axis = np.array([0, 0, 1])

    x_vector = create_vector(origin,x_axis)
    y_vector = create_vector(origin,y_axis)
    z_vector = create_vector(origin,z_axis)


    ## Translate the data such that the midpoint between the two feet is at the origin 
    hip_translated_mid_foot_XYZ = calculate_mid_foot_XYZ_coordinate(skeleton_data[good_frame,:,:],left_heel_index, right_heel_index)
    foot_translated_skeleton_data = translate_skeleton_to_origin(hip_translated_mid_foot_XYZ,skeleton_data)

    # Rotate the skeleton to face the +y direction
    heel_vector_origin = foot_translated_skeleton_data[good_frame,right_heel_index,:]
    heel_vector = create_vector(heel_vector_origin ,foot_translated_skeleton_data[good_frame,left_heel_index,:])


    y_aligned_skeleton_data = rotate_skeleton_to_vector(heel_vector,-1*x_vector,foot_translated_skeleton_data)

    #Rotating the skeleton so that the spine is aligned with +z
    y_aligned_mid_hip_XYZ = calculate_mid_hip_XYZ_coordinates(y_aligned_skeleton_data[good_frame,:,:],left_hip_index,right_hip_index)
    y_aligned_mid_shoulder_XYZ = calculate_shoulder_center_XYZ_coordinates(y_aligned_skeleton_data[good_frame,:,:], left_shoulder_index, right_shoulder_index)
    y_aligned_spine_vector = create_vector(y_aligned_mid_hip_XYZ,y_aligned_mid_shoulder_XYZ)
    
    spine_aligned_skeleton_data = rotate_skeleton_to_vector(y_aligned_spine_vector,z_vector,y_aligned_skeleton_data)

    return spine_aligned_skeleton_data, y_aligned_skeleton_data, foot_translated_skeleton_data