
# from pathlib import Path
# import bpy

# def get_session_path(scene) -> Path:
#     abspath = bpy.path.abspath(scene.fmc_session_path) #absolute path to this omc session's data
#     pathStringParts = abspath.split('\\') #split the absolute path at the \\'s
#     scene.fmc_session_id = pathStringParts[-2] #the 2nd to last element is the 'sessionID'   
#     return Path(abspath)

# class IMPORT_SCENE_OT_session_config_load(bpy.types.Operator):
#     bl_idname = 'fmc.load_session_config'
#     bl_label = 'Load Session Config.yaml'

#     def execute(self, context):
#         #find congif.yaml file for this session 
#         import_path = get_session_path(context.scene)

#         iter = -1
#         for import_fpath in import_path.glob('*_config.yaml'):
#             iter +=1
#             assert iter < 1, 'Found Multiple *_config.yaml files, and thats not supposed to happen!'
#             bpy.types.Scene.fmc_session_path = import_fpath #path to the config gile
#             bpy.types.Scene.fmc_session_ID = import_fpath.name #name of the session 
#         return{'FINISHED'}

