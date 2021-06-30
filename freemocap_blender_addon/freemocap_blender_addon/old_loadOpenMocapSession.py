import bpy
import numpy as np
from mathutils import Matrix, Vector, Euler
import pathlib 

class OMC_OT_loadOpenMoCapSession(bpy.types.Operator): #setting the type as "OMC" for "OpenMoCap"
    """ Load data from an OpenMoCap(OMC) recording session into Blender """
    bl_idname = "omc.load_session_data"
    bl_label = "Load Session Data"
    bl_options = {'REGISTER', 'UNDO'}

    charucoMar_size: bpy.props.FloatProperty(
        name = 'Charuco Marker Size',
        description="Radius of the Charuco Marker Spheres",
        default = .2,
        min = 0, soft_max = 1,
    )
    
    dlcMar_size: bpy.props.FloatProperty(
        name = 'DLC Marker Size',
        description="Radius of the DLC Marker Spheres",
        default = .3,
        min = 0, soft_max = 1,
    )

    bodyMar_size: bpy.props.FloatProperty(
        name = 'Skeleton Body Marker Size',
        description="Radius of the Skeleton Body Marker Spheres",
        default = .2,
        min = 0, soft_max = 1,
    )

    faceMar_size: bpy.props.FloatProperty(
        name = 'Skeleton Face Marker Size',
        description="Radius of the Skeleton Face Marker Spheres",
        default = .15,
        min = 0, soft_max = 1,
    )

    handMar_size: bpy.props.FloatProperty(
        name = 'Skeleton Hand Marker Size',
        description="Radius of the Skeleton Hand Marker Spheres",
        default = .2,
        min = 0, soft_max = 1,
    )

    meshType: bpy.props.StringProperty(
        name = 'Marker Mesh Type',
        description = 'Type of mesh to draw at marker locations (just `sphere` and `monkey` for now)',
        default = 'uv_sphere',
    )

    def execute(self, context):
        """Load in data from an OpenMoCap recording session and place all 3D points as spheres in the 3D Viewport"""
        C = bpy.context
        D = bpy.data

        # #%% Nuke it all 
        # bpy.ops.object.select_all(action='SELECT') #select all
        # bpy.ops.object.delete(use_global=False) #delete everything 

        # try:
        #     bpy.ops.outliner.select_all(action='SELECT')
        #     bpy.ops.outliner.delete(hierarchy=True)
        # except:
        #     pass

        #%% _______________________________________________________________________
        #  Load in data

        loadedData  = np.load(r"C:\Users\jonma\Dropbox\GitKrakenRepos\OpenMoCap\Data\test6_01_21a\outData\saveData.npz")
        skel_fr_mar_dim = loadedData['skel_fr_mar_dim'] #OpenPose skeleton data
        dlcPts_fr_mar_dim = loadedData['dlcPts_fr_mar_dim']
        charucoCorners_pt_XYZ = loadedData['charucoCornersXYZ']

        startFr = 0
        numFrames = skel_fr_mar_dim.shape[0]-1

        #names of markers 
        skel_markerID = ["Nose", "Neck", "RShoulder", "RElbow", "RWrist", "LShoulder",
        "LElbow", "LWrist", "MidHip", "RHip", "RKnee", "RAnkle", "LHip", "LKnee",
        "LAnkle", "REye", "LEye", "REar", "LEar", "LBigToe", "LSmallToe", "LHeel",
        "RBigToe", "RSmallToe", "RHeel"]

        #%% create spheres at marker locations

        #%% _______________________________________________________________________
        #Charuco grid!
        charucoCollectionName = 'CharucoBoard'
        # charColl = eby.create_collection(charucoCollectionName)
        # assert charColl.name == charucoCollectionName, 'Charuco Collection name doesnt match. Did it already exist when you tried to make it? If so, Blender would make a new one called `thing.001` or something' 

        # C.scene.collection.children.link(charColl) #link the newly created collection to the Blender Scene (so it will show up in the outliner)

        print('Loading Charuco Markers')
        for marNum in range(len(charucoCorners_pt_XYZ[:,0])):
            thisMarLoc = charucoCorners_pt_XYZ[marNum,:]
            ms =   self.charucoMar_size

            if self.meshType == 'uv_sphere':
                bpy.ops.mesh.primitive_uv_sphere_add(align='WORLD', location=thisMarLoc, scale=(ms, ms, ms))            
            elif self.meshType == 'monkey':
                bpy.ops.mesh.primitive_monkey_add(align='WORLD', location=thisMarLoc, scale=(ms, ms, ms))
                
            thisMarker = C.active_object

            # eby.move_object_to_collection(thisMarker, charColl)

        #%% _______________________________________________________________________
        # Deeplabcut (DLC) data!
        dlcCollectionName = 'DLC'
        # dlcColl = eby.create_collection(dlcCollectionName)
        # assert dlcColl.name == dlcCollectionName, 'Charuco Collection name doesnt match. Did it already exist when you tried to make it? If so, Blender would make a new one called `thing.001` or something' 

        # C.scene.collection.children.link(charColl) #link the newly created collection to the Blender Scene (so it will show up in the outliner)
        
        print('Loading DLC Markers')
        for marNum in range(len(dlcPts_fr_mar_dim[0,:,0])):
            thisMarLoc = dlcPts_fr_mar_dim[0,marNum,:]
            ms = self.dlcMar_size
            
            if self.meshType == 'uv_sphere':
                bpy.ops.mesh.primitive_uv_sphere_add(align='WORLD', location=thisMarLoc, scale=(ms, ms, ms))            
            elif self.meshType == 'monkey':
                bpy.ops.mesh.primitive_monkey_add(align='WORLD', location=thisMarLoc, scale=(ms, ms, ms))
            
            thisMarker = C.active_object
            # eby.move_object_to_collection(thisMarker, dlcColl)

            #loop through each frame (after the first [0th] frame) to set the keyframes for this marker
            for fr in range(1, numFrames):
                thisMarker.location = dlcPts_fr_mar_dim[fr,marNum,:]
                thisMarker.keyframe_insert(data_path="location", frame=fr)



        #%% _______________________________________________________________________
        # Skreleton data!
        skelCollectionName = 'skel'
        # skelColl = eby.create_collection(skelCollectionName)
        # assert skelColl.name == skelCollectionName, 'Charuco Collection name doesnt match. Did it already exist when you tried to make it? If so, Blender would make a new one called `thing.001` or something' 

        # C.scene.collection.children.link(charColl) #link the newly created collection to the Blender Scene (so it will show up in the outliner)
        print('Loading Skeleton Markers!')
        for marNum in range(len(skel_fr_mar_dim[startFr,:,0])):
            thisMarLoc = skel_fr_mar_dim[startFr,marNum,:]
            
            #these will define the size of teh body, hand, and face markers
            bms = self.bodyMar_size
            hms = self.handMar_size
            fms = self.faceMar_size

            if self.meshType == 'uv_sphere':
                bpy.ops.object.armature_add(align='WORLD', location=thisMarLoc)            
            elif self.meshType == 'monkey':
                bpy.ops.mesh.primitive_monkey_add(align='WORLD', location=thisMarLoc)
            
            thisMarker = C.active_object

            # eby.move_object_to_collection(thisMarker, skelColl)
            
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

