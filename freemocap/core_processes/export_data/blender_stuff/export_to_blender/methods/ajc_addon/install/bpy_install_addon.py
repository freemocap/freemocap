import os
from pathlib import Path
import shutil
import tempfile
from typing import Union

INSTALL_ADDON_SCRIPT_PATH = __file__


def create_zip_from_folder(addon_folder_path: Union[Path, str]) -> str:
    try:
        addon_folder_path = Path(addon_folder_path)
        if not addon_folder_path.is_dir():
            raise FileNotFoundError(f"Addon folder path `{addon_folder_path}` does not exist!")
        # if not addon_folder_path.joinpath("__init__.py").is_file():
        #     raise FileNotFoundError(f"Addon folder path `{addon_folder_path}` does not contain an `__init__.py` file!")

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / addon_folder_path.name
            shutil.copytree(addon_folder_path, tmp_path)
            zip_path = addon_folder_path.parent / f"{addon_folder_path.name}.zip"
            shutil.make_archive(base_name=str(zip_path.with_suffix("")), format="zip", root_dir=tmp_path.parent)

        if not Path(zip_path).is_file():
            raise FileNotFoundError(f"Failed to create zip file at : {zip_path}")
    except Exception as e:
        print("Failed to create zip file at")
        print(e)
        raise e
    return str(zip_path)


def bpy_install_addon(addon_root_directory: str):
    """
    This gets called as a subprocess to install the addon to blender
    """
    import bpy

    addon_root_directory = Path(addon_root_directory)

    addon_name = Path(addon_root_directory).name

    print(f"\n\nInstalling blender addon named `{addon_name}` from root directory: `{addon_root_directory}`\n\n")
    zip_file_path = create_zip_from_folder(addon_folder_path=addon_root_directory)
    print(f"Created zip file at `{zip_file_path}`\n\n")

    print("\n\nInstalling addon from zip file...\n\n")
    bpy.ops.preferences.addon_install(overwrite=True, target="DEFAULT", filepath=zip_file_path)

    print("\n\nSaving user preferences...\n\n")
    bpy.ops.wm.save_userpref()
    # print(f"\n\nEnabling addon `{addon_name}`...\n\n")
    # bpy.ops.preferences.addon_enable(module=f'{addon_name}')
    #
    # installed_addons = bpy.context.preferences.addons.keys()
    # # Check if the addon name is in the list of installed addons
    #
    # if addon_name not in (bpy.context.preferences.addons.keys()):
    #     raise Exception(f"Failed to install `{addon_name}`!!")
    # else:
    #     print("SUCCESSFULLY INSTALLED `{addon_name}`!!")

    # Remove the temporary zipfile
    os.remove(zip_file_path)


if __name__ == "__main__":
    print(f"Running {__file__} as a subprocess to install the addon...")
    import sys

    # take in cli args split by --, so this is the first arg
    argument_variables = sys.argv
    argv = sys.argv[sys.argv.index("--") + 1:]
    addon_root_directory = argv[0]
    addon_name = argv[1]
    if not Path(addon_root_directory).exists():
        raise FileNotFoundError(f"Addon root directory `{addon_root_directory}` does not exist!")
    bpy_install_addon(addon_root_directory=addon_root_directory)
