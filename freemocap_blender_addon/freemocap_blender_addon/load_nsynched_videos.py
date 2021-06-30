import bpy 
from ruamel.yaml import YAML
from pathlib import Path

class FMC_OT_loadVideos(bpy.types.Operator):
    """load in each of the nSynced Vidoes (n= numCams) as planes and place in 3d scene"""
    bl_idname = 'fmc.load_nsynced_videos'
    bl_label = "Load nSynched Videos"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        configPath = Path(context.scene.fmc_session_config_path)
        config_yaml = YAML().load(configPath)
        sessionPath = Path(config_yaml['Paths']['sessionPath'])
        vidFolderPath = sessionPath / 'SyncedVideos'
  
        # bpy.ops.import_image.to_plane(files=[{"name":"test6_01_21a_synced_Cam1.mp4"}], directory="C:\\Users\\jonma\\Dropbox\\GitKrakenRepos\\OpenMoCap\\Data\\test6_01_21a\\SyncedVideos\\", compositing_nodes=True, relative=False)
        iter = 0
        for thisVidPath in vidFolderPath.glob('*.mp4'): 
            iter+=1
            #create camera object on Z-axis pointing down at origin
            bpy.ops.object.camera_add(align='WORLD')
            thisCam = context.active_object
            thisCam.location = (iter*2,0,3)
            thisCam.rotation_euler = (0,0,0)
            thisCam.scale = (5, 5, 5)
            thisCam.name = 'Cam' + str(iter)
            
            # use 'images as planes' add on to load in the video files as planes 
            bpy.ops.import_image.to_plane(files=[{"name":thisVidPath.name}], directory=str(thisVidPath.parent), )
            thisVidPlane = context.active_object
            thisVidPlane.parent = thisCam #parent this image_plane to camera object
            thisVidPlane.location[2] -= 2 #bump it down a bit for aesthetics

            # context.active_object.location = (iter,iter,iter) #bump this image_plane over a bit so they don't over lap
            
            f=9
        return {'FINISHED'}