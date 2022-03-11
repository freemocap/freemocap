import bpy 
import numpy as np 
from pathlib import Path

class FMC_OT_load_raw_mocap_data_as_bones(bpy.types.Operator): #setting the type as "FMC" for "FreeMoCap"
    """ Load marker data via FMC yaml config and place empties in Blender scene """
    bl_idname = "fmc.load_raw_mocap_data_as_bones"
    bl_label = "Load raw motion capture data as bones"
    bl_options = {'REGISTER', 'UNDO'}

    bone_size: bpy.props.FloatProperty(
        name = 'Bone size',
        description = 'Size of the bones',
        default = .2,
        min = 0, soft_max =1,
    )

    def execute(self, context):
        configPath = Path(context.scene.fmc_session_path)        
        sessionPath = configPath.parent
        
        try:
            openpose_3d_data_path = sessionPath / 'DataArrays' / 'openPoseSkel_3d.npy'
            openpose_skel_fr_mar_xyz = np.load(str(openpose_3d_data_path))
            #convert to meters
            openpose_skel_fr_mar_xyz = openpose_skel_fr_mar_xyz/1000
            #names of markers 
            openpose_skel_marker_names = ["Nose", "Neck", "RShoulder", "RElbow", "RWrist", "LShoulder",
            "LElbow", "LWrist", "MidHip", "RHip", "RKnee", "RAnkle", "LHip", "LKnee",
            "LAnkle", "REye", "LEye", "REar", "LEar", "LBigToe", "LSmallToe", "LHeel",
            "RBigToe", "RSmallToe", "RHeel"]
            openpose_bool = True
        except:
            openpose_bool = False
            print('No OpenPose Data Found')

        try:
            mediapipe_3d_data_path = sessionPath / 'DataArrays' / 'mediapipeSkel_3d.npy'
            mediapipe_skel_fr_mar_xyz = np.load(str(mediapipe_3d_data_path))
            #convert to meters
            mediapipe_skel_fr_mar_xyz = mediapipe_skel_fr_mar_xyz/1000
            #names of markers 
            mediapipe_skel_marker_names = [ "nose",
                                           
                                            "left_eye_inner",
                                            "left_eye",
                                            "left_eye_outer",
                                           
                                            "right_eye_inner",
                                            "right_eye",
                                            "right_eye_outer",
                                           
                                            "left_ear",
                                            "right_ear",
                                           
                                            "mouth_left",
                                            "mouth_right",
                                           
                                            "left_shoulder",
                                            "right_shoulder",
                                           
                                            "left_elbow",
                                            "right_elbow",
                                           
                                            "left_wrist",
                                            "right_wrist",
                                           
                                            "left_pinky",
                                            "right_pinky",
                                            
                                            "left_index",
                                            "right_index",
                                            
                                            "left_thumb",
                                            "right_thumb",
                                            
                                            "left_hip",
                                            "right_hip",
                                            
                                            "left_knee",
                                            "right_knee",
                                            
                                            "left_ankle",
                                            "right_ankle",
                                            
                                            "left_heel",
                                            "right_heel",
                                            
                                            "left_foot_index",
                                            "right_foot_index",   
                                            ]
            mediapipe_hand_marker_names = ["wrist",
                                           "thumb_cmc",
                                           "thumb_mcp",
                                           "thumb_ip",
                                           "thumb_tip",
                                           
                                           "index_finger_cmc",
                                           "index_finger_mcp",
                                           "index_finger_ip",
                                           "index_finger_tip",
                                           
                                           "middle_finger_cmc",
                                           "middle_finger_mcp",
                                           "middle_finger_ip",
                                           "middle_finger_tip",
                                                                                      
                                           "ring_finger_cmc",
                                           "ring_finger_mcp",
                                           "ring_finger_ip",
                                           "ring_finger_tip",
                                           
                                           "pinky_cmc",
                                           "pinky_mcp",
                                           "pinky_ip",
                                           "pinky_tip",
                                           
                                           
                                            ]
            mediapipe_bool = True
        except:
            mediapipe_bool = False
            print('No mediapipe Data Found')

        
        startFr = 0
        numFrames = mediapipe_skel_fr_mar_xyz.shape[0]-1
        
        bpy.context.scene.frame_end = numFrames
        
        #%% _______________________________________________________________________
        # Skreleton data!
        print('Loading raw motion capture data as bones!')
        face_iter = 0

        # for marNum in range(len(mediapipe_skel_fr_mar_xyz[startFr,:,0])): #all dottos
        for marNum in range(len(mediapipe_skel_marker_names)): #only the body                            
            
            thisMarLoc = mediapipe_skel_fr_mar_xyz[startFr,marNum,:]
            
            #these will define the size of the body, hand, and face markers
            bms = self.bone_size
            hms = bms *.5
            fms = bms *.5

            

            bpy.ops.object.armature_add(align='WORLD', location=thisMarLoc, scale=(bms, bms, bms))
            this_bone = context.active_object

            
            if marNum < len(mediapipe_skel_marker_names) : #body 
                this_bone.name = mediapipe_skel_marker_names[marNum]
                this_bone.scale = (bms, bms, bms)
                
            elif marNum < len(mediapipe_skel_marker_names) + 2*len(mediapipe_hand_marker_names): #hands
                
                if marNum <  len(mediapipe_skel_marker_names) +len(mediapipe_hand_marker_names):         
                    this_hand_prefix = 'right_hand_'
                    this_hand_prefix = 'right_hand_'
                    marker_num_offset = len(mediapipe_skel_marker_names)
                else:
                    this_hand_prefix = 'left_hand_'
                    marker_num_offset = len(mediapipe_skel_marker_names) + len(mediapipe_hand_marker_names)
                    
                this_bone.name = this_hand_prefix + mediapipe_hand_marker_names[marNum-marker_num_offset]
                    
                this_bone.scale=(hms, hms, hms)

            else:  #face
                this_bone.name = 'face_'+str(face_iter).zfill(4)
                face_iter += 1
                this_bone.scale=(fms, fms, fms)
  
            #loop through each frame (after the first [0th] frame) to set the keyframes for this marker
            for fr in range(1, numFrames):
                this_bone.location = mediapipe_skel_fr_mar_xyz[fr,marNum,:]
                this_bone.keyframe_insert(data_path="location", frame=fr)
            print('loaded marker: '+ this_bone.name)
            
        print('Done!')    
        return{'FINISHED'}        

