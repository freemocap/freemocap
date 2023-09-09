from freemocap_web.core.mocap import Mocap
from freemocap.data_layer.export_data.blender_stuff.export_to_blender import export_to_blender
from freemocap.data_layer.export_data.blender_stuff.get_best_guess_of_blender_path import get_best_guess_of_blender_path
from freemocap.system.paths_and_filenames.path_getters import get_blender_file_path


def _export_active_recording_to_blender(mocap: Mocap):
    recording_path = mocap.Project.Folders.Root
    blender_file_path = get_blender_file_path(recording_path)
    export_to_blender(
        recording_folder_path=recording_path,
        blender_file_path=blender_file_path,
        blender_exe_path=get_best_guess_of_blender_path(),
        method="megascript_take2")
    return blender_file_path

    # if (
    #         mocap._controller_group_box.auto_open_in_blender_checked
    #         # or self._visualization_control_panel.open_in_blender_automatically_box_is_checked
    # ):
    #     if Path(mocap._active_recording_info_widget.active_recording_info.blender_file_path).exists():
    #         open_file(mocap._active_recording_info_widget.active_recording_info.blender_file_path)
    #     else:
    #         logger.error(
    #             "Blender file does not exist! Did something go wrong in the `export_to_blender` call above?"
    #         )