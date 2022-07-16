
import numpy as np




class SkeletonDataHolder:
    def __init__(self, skeleton_data, skeleton_indices_list,good_frame):
        self.skeleton_data = skeleton_data
        self.skeleton_indices_list = skeleton_indices_list

    
        self.set_indices_as_properties(skeleton_indices_list)
        self.good_frame_skeleton_data = self.get_good_frame_of_data(good_frame,skeleton_data)
        self.run_joint_finder_calculations()
        self.run_vector_calculations()    
       

    def run_joint_finder_calculations(self):
        self.mid_hip_XYZ = self.calculate_mid_hip_XYZ_coordinates(self.good_frame_skeleton_data, self.left_hip_index,self.right_hip_index)
        self.mid_foot_XYZ = self.calculate_mid_foot_XYZ_coordinate(self.good_frame_skeleton_data, self.left_heel_index, self.right_heel_index)
        self.shoulder_center_XYZ = self.calculate_shoulder_center_XYZ_coordinates(self.good_frame_skeleton_data, self.left_shoulder_index, self.right_shoulder_index)

    def run_vector_calculations(self):
        self.spine_vector, self.spine_unit_vector = self.calculate_spine_vector_and_unit_vector(self.good_frame_skeleton_data, self.mid_hip_XYZ, self.shoulder_center_XYZ)


        self.heel_vector_origin = self.good_frame_skeleton_data[self.right_heel_index,:]
        self.heel_vector = self.create_vector(self.heel_vector_origin ,self.good_frame_skeleton_data[self.left_heel_index,:])

        self.heel_unit_vector = self.create_unit_vector(self.heel_vector)

    def set_indices_as_properties(self, indices_list):
        self.left_hip_index = indices_list.index('left_hip')
        self.right_hip_index = indices_list.index('right_hip')

        self.left_shoulder_index = indices_list.index('left_shoulder')
        self.right_shoulder_index = indices_list.index('right_shoulder')

        self.left_toe_index = indices_list.index('left_foot_index')
        self.right_toe_index = indices_list.index('right_foot_index')
        self.left_heel_index = indices_list.index('left_heel')
        self.right_heel_index = indices_list.index('right_heel')

    def get_good_frame_of_data(self,good_frame,skeleton_data):
        """Take in a good frame, and return the base frame"""
        good_frame_skeleton_data = skeleton_data[good_frame,:,:]
        return good_frame_skeleton_data

    def create_vector(self,point1,point2): 
        """Put two points in, make a vector"""
        vector = point2 - point1
        return vector

    def create_normal_vector(self,vector1,vector2): 
        """Put two vectors in, make a normal vector"""
        normal_vector = np.cross(vector1,vector2)
        return normal_vector

    def create_unit_vector(self,vector): 
        """Take in a vector, make it a unit vector"""
        unit_vector = vector/np.linalg.norm(vector)
        return unit_vector
    
    def calculate_normal_vector_to_foot(self,heel_one_index, toe_one_index, heel_two_index, skeleton_data):
        foot_one_vector = self.create_vector(skeleton_data[heel_one_index,:],skeleton_data[toe_one_index,:])
        heel_vector = self.create_vector(skeleton_data[heel_one_index,:],skeleton_data[heel_two_index,:])

        foot_normal_vector =  self.create_normal_vector(heel_vector,foot_one_vector)

        return foot_normal_vector, foot_one_vector, heel_vector

    def calculate_shoulder_center_XYZ_coordinates(self, skeleton_data,left_shoulder_index,right_shoulder_index ):
        """Take in the left and right shoulder indices, and calculate the shoulder center point"""
        left_shoulder_point = skeleton_data[left_shoulder_index,:]
        right_shoulder_point = skeleton_data[right_shoulder_index,:]
        shoulder_center_XYZ_coordinates = (left_shoulder_point + right_shoulder_point)/2
        
        return shoulder_center_XYZ_coordinates

    def calculate_mid_hip_XYZ_coordinates(self,skeleton_data,left_hip_index,right_hip_index):
        """Take in the left and right hip indices, and calculate the mid hip point"""
        left_hip_point = skeleton_data[left_hip_index,:]
        right_hip_point = skeleton_data[right_hip_index,:]
        mid_hip_XYZ_coordinates = (left_hip_point + right_hip_point)/2
        
        return mid_hip_XYZ_coordinates

    def calculate_spine_vector_and_unit_vector(self,skeleton_data,mid_hip_XYZ, mid_shoulder_XYZ):
        spine_vector = self.create_vector(mid_hip_XYZ,mid_shoulder_XYZ)
        spine_unit_vector = self.create_unit_vector(spine_vector)
        return spine_vector, spine_unit_vector

    def calculate_mid_foot_XYZ_coordinate(self, skeleton_data, right_heel_index, left_heel_index):
        """Take in the primary and secondary foot indices, and calculate the mid foot point"""
        right_foot_point = skeleton_data[right_heel_index,:]
        left_foot_point = skeleton_data[left_heel_index,:]
        mid_foot_XYZ_coordinates = (right_foot_point + left_foot_point)/2
        
        return mid_foot_XYZ_coordinates