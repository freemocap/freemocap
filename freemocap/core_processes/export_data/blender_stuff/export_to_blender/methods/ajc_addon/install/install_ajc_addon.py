import inspect
import subprocess
from importlib.metadata import distribution
from pathlib import Path

from ajc27_freemocap_blender_addon.main import ajc27_run_as_main_function

from freemocap.core_processes.export_data.blender_stuff.export_to_blender.methods.ajc_addon.install.bpy_install_addon import (
    INSTALL_ADDON_SCRIPT_PATH,
)

FREEMOCAP_BLENDER_ADDON_PACKAGE_NAME = "ajc27_freemocap_blender_addon"


def get_package_path(package_name: str):
    try:
        package_dist = distribution(package_name)
        package_path = package_dist.locate_file("")
        return package_path
    except Exception:
        print(f"{package_name} not found.")
        return None


def install_ajc_addon(blender_exe_path: str, ajc_addon_main_file_path: str):
    addon_root_directory = Path(ajc_addon_main_file_path).parent
    addon_name = Path(addon_root_directory).name

    # Define your addon's name and root directory
    subprocess_command = [
        blender_exe_path,
        "--background",
        "--python",
        INSTALL_ADDON_SCRIPT_PATH,
        "--",
        addon_root_directory,
        addon_name,
    ]
    # use CLI to install the addon passing in the addon name and zip file path
    subprocess.run(subprocess_command)


if __name__ == "__main__":
    from freemocap.core_processes.export_data.blender_stuff.get_best_guess_of_blender_path import (
        get_best_guess_of_blender_path,
    )

    ajc_addon_main_file_path = inspect.getfile(ajc27_run_as_main_function)

    blender_path_in = get_best_guess_of_blender_path()

    install_ajc_addon(
        blender_exe_path=blender_path_in, ajc_addon_main_file_path=inspect.getfile(ajc27_run_as_main_function)
    )
    print("Done!")
