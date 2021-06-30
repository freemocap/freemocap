import bpy 
import numpy as np 
from ruamel.yaml import YAML
from pathlib import Path

class FMC_OT_loadMarkerEmpties(bpy.types.Operator): #setting the type as "FMC" for "OpenMoCap"
    """ Load marker data via FMC yaml config and place empties in Blender scene """
    bl_idname = "fmc.load_marker_empties"
    bl_label = "Load Marker Empties"
    bl_options = {'REGISTER', 'UNDO'}

    emptyType: bpy.props.StringProperty(
        name = 'Empty Type',
        description = 'Type of empty to draw at marker locations (just `plain axes` and `sphere` for now)',
        default = 'PLAIN_AXES',
    )

    emptySize: bpy.props.FloatProperty(
        name = 'Empty size',
        description = 'Size of the empty markers',
        default = .2,
        min = 0, soft_max =1,
    )

    def execute(self, context):
        configPath = Path(context.scene.fmc_session_config_path)
        config_yaml = YAML().load(configPath)
        sessionPath = Path(config_yaml['Paths']['sessionPath'])
        dataPath = sessionPath / 'outData' / 'saveData.npz'
        sessionData = np.load(str(dataPath))

        skel_fr_mar_dim = sessionData['skel_fr_mar_dim']
        
        startFr = 0
        numFrames = skel_fr_mar_dim.shape[0]-1
        

        #names of markers 
        skel_markerID = ["Nose", "Neck", "RShoulder", "RElbow", "RWrist", "LShoulder",
        "LElbow", "LWrist", "MidHip", "RHip", "RKnee", "RAnkle", "LHip", "LKnee",
        "LAnkle", "REye", "LEye", "REar", "LEar", "LBigToe", "LSmallToe", "LHeel",
        "RBigToe", "RSmallToe", "RHeel"]

        #%% _______________________________________________________________________
        # Skreleton data!
        print('Loading Skeleton Markers!')
        for marNum in range(len(skel_fr_mar_dim[startFr,:,0])):
            thisMarLoc = skel_fr_mar_dim[startFr,marNum,:]
            
            #these will define the size of teh body, hand, and face markers
            bms = self.emptySize
            hms = bms *.5
            fms = bms *.5

            emptyType = self.emptyType

            bpy.ops.object.empty_add(type=self.emptyType, align='WORLD', location=thisMarLoc, scale=(bms, bms, bms))
            thisMarker = context.active_object

            #get names of body markers from name array "skel_markerID" (and build hand and face names from there)
            if marNum < 25 :
                thisMarker.name = skel_markerID[marNum]
                thisMarker.scale = (bms, bms, bms)
            elif marNum < 46:                
                if marNum == 26: print('Loading Hands')                
                thisMarker.name = "HandR"
                thisMarker.scale=(hms, hms, hms)
            elif marNum < 67:
                thisMarker.name = "HandL" 
                thisMarker.scale=(hms, hms, hms)
            else:
                if marNum == 67: print('Loading Face')
                thisMarker.name = 'Face'
                thisMarker.scale=(fms, fms, fms)

            #loop through each frame (after the first [0th] frame) to set the keyframes for this marker
            for fr in range(1, numFrames):
                thisMarker.location = skel_fr_mar_dim[fr,marNum,:]
                thisMarker.keyframe_insert(data_path="location", frame=fr)
        return{'FINISHED'}        
