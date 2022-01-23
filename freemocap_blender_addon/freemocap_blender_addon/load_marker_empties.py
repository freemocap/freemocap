import bpy 
import numpy as np 
from pathlib import Path

class FMC_OT_loadMarkerEmpties(bpy.types.Operator): #setting the type as "FMC" for "OpenMoCap"
    """ Load marker data via FMC yaml config and place empties in Blender scene """
    bl_idname = "fmc.load_marker_empties"
    bl_label = "Load Marker Empties"
    bl_options = {'REGISTER', 'UNDO'}

    emptyType: bpy.props.StringProperty(
        name = 'Empty Type',
        description = 'Type of empty to draw at marker locations (just `sphere` for now)',
        default = 'SPHERE',
    )

    emptySize: bpy.props.FloatProperty(
        name = 'Empty size',
        description = 'Size of the empty markers',
        default = .01,
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
        print('Loading Skeleton Markers!')
        face_iter = 0

        for marNum in range(len(mediapipe_skel_fr_mar_xyz[startFr,:,0])):
            
            
            
            thisMarLoc = mediapipe_skel_fr_mar_xyz[startFr,marNum,:]
            
            #these will define the size of teh body, hand, and face markers
            bms = self.emptySize
            hms = bms *.5
            fms = bms *.5

            emptyType = self.emptyType

            bpy.ops.object.empty_add(type=self.emptyType, align='WORLD', location=thisMarLoc, scale=(bms, bms, bms))
            thisMarker = context.active_object

            #get names of body markers from name array "skel_markerID" (and build hand and face names from there)
            if marNum < len(mediapipe_skel_marker_names) :
                thisMarker.name = mediapipe_skel_marker_names[marNum]
                thisMarker.scale = (bms, bms, bms)
            elif marNum < len(mediapipe_skel_marker_names) + 2*len(mediapipe_hand_marker_names):            
                
                if marNum <  len(mediapipe_skel_marker_names) +len(mediapipe_hand_marker_names):         
                    this_hand_prefix = 'right_hand_'
                    this_hand_prefix = 'right_hand_'
                    marker_num_offset = len(mediapipe_skel_marker_names)
                else:
                    this_hand_prefix = 'left_hand_'
                    marker_num_offset = len(mediapipe_skel_marker_names) + len(mediapipe_hand_marker_names)
                    
                try:
                    print('this hand marnum is ' + str(marNum-marker_num_offset))
                    thisMarker.name = this_hand_prefix + mediapipe_hand_marker_names[marNum-marker_num_offset]
                except:
                    print('something weired in hand town for marker num' + str(marNum))
                    f=9
                    
                thisMarker.scale=(hms, hms, hms)

            else:                
                thisMarker.name = 'face_'+str(face_iter).zfill(4)
                face_iter += 1
                thisMarker.scale=(fms, fms, fms)
  
            #loop through each frame (after the first [0th] frame) to set the keyframes for this marker
            for fr in range(1, numFrames):
                thisMarker.location = mediapipe_skel_fr_mar_xyz[fr,marNum,:]
                thisMarker.keyframe_insert(data_path="location", frame=fr)
            print('loaded marker: '+ thisMarker.name)
            
        print('Done!')    
        return{'FINISHED'}        

