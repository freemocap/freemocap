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
        ui_column_0 = layout.column(align=True)
        ui_column_0.prop(context.scene, 'fmc_session_config_path' )
        
        if context.scene.fmc_session_config_path : #once you set the config path
            configPath = Path(context.scene.fmc_session_config_path)
            ui_column_0.label(text=f'Session Config File: {configPath.name}') 
        else: 
            ui_column_0.label(text='-No Session Config Loaded-')
        ui_column_0.label(text='_______')
        
        #######################################################
        # UI_COLUMN_1  # The part of the panel where you load in the marker data
        ui_column_1 = self.layout.column(align=True)

        ui_column_1.operator('fmc.load_marker_empties',
            text='Load Marker Empties!',
            icon = 'ARMATURE_DATA')

        #######################################################
        # UI_COLUMN_2  # The part of the panel where you load in the videos
        ui_column_2= self.layout.column(align=True)

        ui_column_2.operator('fmc.load_nsynced_videos',
            text='Load nSynced Videos!',
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

