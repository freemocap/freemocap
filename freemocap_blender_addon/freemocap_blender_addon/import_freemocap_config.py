
import pathlib
import bpy

def mass_import_path(scene) -> pathlib.Path:
    abspath = bpy.path.abspath(scene.fmc_session_path) #absolute path to this omc session's data
    pathStringParts = abspath.split('\\') #split the absolute path at the \\'s
    scene.fmc_session_id = pathStringParts[-2] #the 2nd to last element is the 'sessionID'   
    return pathlib.Path(abspath)

class IMPORT_SCENE_OT_session_config_load(bpy.types.Operator):
    bl_idname = 'fmc.load_session_config'
    bl_label = 'Load Session Config.yaml'

    def execute(self, context):
        #find congif.yaml file for this session 
        import_path = mass_import_path(context.scene)

        iter = -1
        for import_fpath in import_path.glob('*_config.yaml'):
            iter +=1
            assert iter < 1, 'Found Multiple *_config.yaml files, and thats not supposed to happen!'
            bpy.types.Scene.fmc_session_config_path = import_fpath #path to the config gile
            bpy.types.Scene.fmc_session_config_fname = import_fpath.name #name of the config file 
        return{'FINISHED'}

class IMPORT_SCENE_OT_obj_reload(bpy.types.Operator):
    bl_idname = 'fmc.obj_reload'
    bl_label = 'ReLoad Mass-imported OBJs'

    def execute(self, context): 
        active_object = context.object

        #store wht we ant to remember
        fmc_session_config_fname = active_object.fmc_session_config_fname
        matrix_world = active_object.matrix_world.copy()

        #remove obj from scene
        for collection in list(active_object.users_collection):
            collection.objects.unlink(active_object)

        if active_object.users == 0:
            bpy.data.objects.remove(active_object)        
        del active_object

        #load obj file
        import_path = mass_import_path(context.scene)
        import_fpath = import_path / omc_session_config_fname        
        bpy.ops.import_scene.obj(filepath=str(import_fpath))        

        #restore what we remembered
        for imported_ob in context.selected_objects:
            imported_ob.omc_session_config_fname = import_fpath.name
            imported_ob.matrix_world = matrix_world

        return('FINSHED')
