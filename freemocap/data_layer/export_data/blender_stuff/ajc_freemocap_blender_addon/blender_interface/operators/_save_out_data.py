import logging

import bpy

from ajc_freemocap_blender_addon.core_functions.freemocap_data_handler.operations.freemocap_empties_from_parent_object import \
    freemocap_empties_from_parent_object
from ajc_freemocap_blender_addon.core_functions.main_controller import MainController
from ajc_freemocap_blender_addon.data_models.parameter_models.load_parameters_config import load_default_parameters_config

logger = logging.getLogger(__name__)


class FMC_ADAPTER_save_data_to_disk(bpy.types.Operator):
    bl_idname = 'fmc_adapter._save_data_to_disk'
    bl_label = "Save Data to Disk"
    bl_options = {'REGISTER', 'UNDO_GROUPED'}

    def execute(self, context):
        fmc_adapter_tool = context.scene.fmc_adapter_properties
        recording_path = fmc_adapter_tool.recording_path
        if recording_path == "":
            logger.error("No recording path specified")
            return {'CANCELLED'}
        config = load_default_parameters_config()
        try:
            logger.info(f"Executing `main_controller.run_all() with config:{config}")
            controller = MainController(recording_path=recording_path,
                                        config=config)
            empties = freemocap_empties_from_parent_object(fmc_adapter_tool.data_parent_empty)
            controller.freemocap_data_handler.extract_data_from_empties(empties=empties)
            controller.save_data_to_disk()
        except Exception as e:
            logger.error(f"Failed to run main_controller.run_all() with config:{config}: `{e}`")
            logger.exception(e)
            return {'CANCELLED'}
        return {'FINISHED'}
