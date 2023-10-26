import math as m
import time

import bpy
from bpy.types import Operator

from ajc_freemocap_blender_addon.core_functions.mesh.attach_mesh_to_rig import attach_mesh_to_rig
from ajc_freemocap_blender_addon.core_functions.empties.reorient_empties import reorient_empties
from ajc_freemocap_blender_addon.core_functions.rig.add_rig import add_rig

REORIENT_EMPTIES_EXECUTED = True

import logging

logger = logging.getLogger(__name__)


class FMC_ADAPTER_OT_add_body_mesh(Operator):
    bl_idname = 'fmc_adapter._add_body_mesh'
    bl_label = 'Freemocap Adapter - Add Body Mesh'
    bl_description = 'Add a body mesh to the rig. The mesh can be a file or a custom mesh made with basic shapes. This method first executes Add Empties and Add Rig(if no rig available)'
    bl_options = {'REGISTER', 'UNDO_GROUPED'}

    def execute(self, context):
        logger.info(f"Executing {__name__}...")
        scene = context.scene
        fmc_adapter_tool = scene.fmc_adapter_properties

        # Get start time
        start = time.time()

        # Reset the scene frame to the start
        current_frame = scene.frame_current
        scene.frame_set(scene.frame_start)

        if not REORIENT_EMPTIES_EXECUTED:
            logger.debug('Executing First Adjust Empties...')

            # Execute Adjust Empties first
            reorient_empties(z_align_ref_empty=fmc_adapter_tool.vertical_align_reference,
                             z_align_angle_offset=fmc_adapter_tool.vertical_align_angle_offset,
                             ground_ref_empty=fmc_adapter_tool.ground_align_reference,
                             z_translation_offset=fmc_adapter_tool.vertical_align_position_offset
                             )

        # Execute Add Rig if there is no rig in the scene
        try:
            root = bpy.data.objects['root']
        except:
            logger.debug('Executing Add Rig to have a rig for the mesh...')
            add_rig(use_limit_rotation=fmc_adapter_tool.use_limit_rotation)

        try:
            logger.debug('Executing Add Body Mesh...')
            attach_mesh_to_rig(body_mesh_mode=fmc_adapter_tool.body_mesh_mode)
        except Exception as e:
            logger.exception(f"Error while adding body mesh: {e}")
            return {'CANCELLED'}

        # Get end time and print execution time
        end = time.time()
        logger.debug('Finished. Execution time (s): ' + str(m.trunc((end - start) * 1000) / 1000))
        scene.frame_set(current_frame)  # set the frame back to what it was before we started
        return {'FINISHED'}
