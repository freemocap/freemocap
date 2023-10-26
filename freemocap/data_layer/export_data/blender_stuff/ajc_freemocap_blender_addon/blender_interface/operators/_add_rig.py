import logging
import math as m
import time

from bpy.types import Operator

from ajc_freemocap_blender_addon.blender_interface.operators._add_body_mesh import REORIENT_EMPTIES_EXECUTED
from ajc_freemocap_blender_addon.core_functions.empties.reorient_empties import reorient_empties
from ajc_freemocap_blender_addon.core_functions.freemocap_data_handler.operations.freemocap_empties_from_parent_object import \
    freemocap_empties_from_parent_object
from ajc_freemocap_blender_addon.core_functions.rig.add_rig import add_rig

logger = logging.getLogger(__name__)


class FMC_ADAPTER_OT_add_rig(Operator):
    bl_idname = 'fmc_adapter._add_rig'
    bl_label = 'Freemocap Adapter - Add Rig'
    bl_description = 'Add a Rig to the capture empties. The method sets the rig rest pose as a TPose'
    bl_options = {'REGISTER', 'UNDO_GROUPED'}

    def execute(self, context):
        logger.info(f"Executing {__name__}...")
        scene = context.scene
        fmc_adapter_tool = scene.fmc_adapter_properties
        parent_empty = fmc_adapter_tool.data_parent_empty
        empties = freemocap_empties_from_parent_object(parent_empty)
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
                             z_translation_offset=fmc_adapter_tool.vertical_align_position_offset,
                             empties=empties,
                             parent_object=parent_empty,
                             correct_fingers_empties=fmc_adapter_tool.correct_fingers_empties,
                             )

        logger.debug('Executing Add Rig...')

        rig = add_rig(empties=empties,
                      bone_length_method=fmc_adapter_tool.bone_length_method,
                      keep_symmetry=fmc_adapter_tool.keep_symmetry,
                      add_fingers_constraints=fmc_adapter_tool.add_fingers_constraints,
                      use_limit_rotation=fmc_adapter_tool.use_limit_rotation)

        # Get end time and print execution time
        end = time.time()
        logger.debug('Finished. Execution time (s): ' + str(m.trunc((end - start) * 1000) / 1000))
        scene.frame_set(current_frame)  # set the frame back to what it was before we started
        return {'FINISHED'}
