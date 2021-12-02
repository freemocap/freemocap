import bpy 
from pathlib import Path

#%% Build the User Interface panel
class VIEW3D_PT_freemocap(bpy.types.Panel): 
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "FreeMoCap"
    bl_label = "FMC_LoadSession"

    def draw(self,context):
        layout = self.layout

        #######################################################
        # UI_COLUMN_0 - The part of the panel where you specify the Session Folder        
        ui_set_session_path = layout.column(align=True)
        ui_set_session_path.prop(context.scene, 'fmc_session_path' )
        
        if context.scene.fmc_session_path : #once you set the config path            
            session_path = Path(context.scene.fmc_session_path)
            if session_path.is_dir():                #JSM NOTE - This is kinda sloppy, but I don't know how to alter the actual session path variable. I want there to be a way to enforce that the 'session_path' value points to the whole session folder, NOT a file within that folder
                ui_set_session_path.label(text=f'Session Path: {str(session_path)}') 
            else:
                ui_set_session_path.label(text=f'Session Path: {str(session_path.parent)}') 
        else: 
            ui_set_session_path.label(text='-No Session Config Loaded-')
        ui_set_session_path.label(text='_______')
        
        #######################################################
        
        ui_column_1 = self.layout.column(align=True)

        ui_column_1.operator('fmc.load_marker_empties',
            text='Load Marker Empties!',
            icon = 'EMPTY_AXIS')


        #######################################################
        
        ui_as_bones_button = self.layout.column(align=True)

        ui_as_bones_button.operator('fmc.load_raw_mocap_data_as_bones',
            text='Load raw mocap data as bones!',
            icon = 'GROUP_BONE')

        #######################################################
        
        ui_build_armature= self.layout.column(align=True)

        ui_build_armature.operator('fmc.build_armature_from_raw_mocap_data',
            text='build armature from raw mocap data',
            icon = 'ARMATURE_DATA')




        #######################################################
        ui_column_2= self.layout.column(align=True)

        ui_column_2.operator('fmc.load_nsynced_videos',
            text='Load nSynced Videos!!',
            icon = 'CAMERA_DATA')

        # properties_0 = ui_column_2.operator('fmc.load_session_data',
        #     text='Load FreeMoCap Session (Marshmallow Style!)',
        #     icon = 'VOLUME_DATA')
        # properties_0.bodyMar_size = 10
        # properties_0.faceMar_size = 10
        # properties_0.handMar_size = 10

        # properties_1 = ui_column_2.operator('fmc.load_session_data',
        #     text='Load FreeMoCap Session (Monkey Style)', 
        #     icon = 'MONKEY')
        # properties_1.meshType = 'monkey'


        #######################################################
        # UI_COLUMN_3  #The part of the panel where you click PLAY and whatnot
        ui_column_3 = self.layout.column(align=True)
        ui_column_3.prop(context.scene, 'frame_current', text='Current Frame#' )
        ui_column_3.operator('screen.animation_play', icon='PLAY')

