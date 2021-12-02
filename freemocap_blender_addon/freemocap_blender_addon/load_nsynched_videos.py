import bpy 
import pickle

from pathlib import Path

class FMC_OT_loadVideos(bpy.types.Operator):
    """load in each of the nSynced Vidoes (n= numCams) as planes and place in 3d scene"""
    bl_idname = 'fmc.load_nsynced_videos'
    bl_label = "Load nSynched Videos"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        session_path = Path(context.scene.fmc_session_path)
                         
        if not session_path.is_dir():
            session_path = session_path.parent
        
         
        camera_calibration_pickle_path = session_path / (session_path.name + '_calibration.pickle')
        
        vidFolderPath = session_path / 'SyncedVideos'
        
           

        with open(camera_calibration_pickle_path, 'rb') as camera_calib_pickle:
            camera_calibration_dict = pickle.load(camera_calib_pickle)
  
        camera_translations = []
        camera_rotations = []
        for this_cam_calib_info in camera_calibration_dict:
            camera_translations.append(this_cam_calib_info['translation'])
            camera_rotations.append(this_cam_calib_info['rotation'])
        
 
        
        for vid_number, thisVidPath, in enumerate(vidFolderPath.glob('*.mp4')): 
            
            this_camera_tx = camera_translations[vid_number][0]/1000 #convert to meters from millimeters
            this_camera_ty = camera_translations[vid_number][1]/1000
            this_camera_tz = camera_translations[vid_number][2]/1000
            
            this_camera_rx = camera_rotations[vid_number][0]
            this_camera_ry = camera_rotations[vid_number][1]
            this_camera_rz = camera_rotations[vid_number][2]
            
            #create camera object on Z-axis pointing down at origin
            bpy.ops.object.camera_add(align='WORLD')
            thisCam = context.active_object
            thisCam.location = (this_camera_tx,this_camera_ty,this_camera_tz)
            thisCam.rotation_euler = (this_camera_rx, this_camera_ry, this_camera_rz)
            # thisCam.scale = (5, 5, 5)
            thisCam.name = 'Cam' + str(iter)
            
            # use 'images as planes' add on to load in the video files as planes 
            bpy.ops.import_image.to_plane(files=[{"name":thisVidPath.name}], directory=str(thisVidPath.parent), )
            thisVidPlane = context.active_object
            thisVidPlane.parent = thisCam #parent this image_plane to camera object
            thisVidPlane.location[2] -= 2 #bump it down a bit for aesthetics

            # context.active_object.location = (iter,iter,iter) #bump this image_plane over a bit so they don't over lap
            
        return {'FINISHED'}