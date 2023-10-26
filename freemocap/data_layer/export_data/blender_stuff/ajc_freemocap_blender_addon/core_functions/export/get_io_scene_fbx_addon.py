import logging
import os
import zipfile
from importlib.machinery import SourceFileLoader
from pathlib import Path

import addon_utils
import bpy

logger = logging.getLogger(__name__)


def get_io_scene_fbx_addon():
    logger.info("Checking for io_scene_fbx addon...")

    # Your addon name and github repo lik
    addon_name = 'io_scene_fbx'
    github_url = 'https://github.com/Taremin/io_scene_fbx/archive/main.zip'
    # The addon directory where it should be in Blender
    addon_directory = str(Path(bpy.utils.script_path_user()) / 'addons')

    # Check if addon is installed
    addons = {os.path.basename(os.path.dirname(module.__file__)): module.__file__ for module in addon_utils.modules()}
    if addon_name not in addons:
        download_io_scene_fbx(addon_directory, addon_name, github_url)

    # At this point the addon is either installed already or we installed it
    addon_folder_path = os.path.dirname(addons.get(addon_name))

    # Import it
    try:
        logger.debug(f"Loading {addon_name} addon from {addon_folder_path} to test import")
        SourceFileLoader(addon_name, os.path.join(addon_folder_path, '__init__.py')).load_module()

        import io_scene_fbx.export_fbx_bin as export_fbx_bin

    except Exception as e:
        logger.error(f'Error loading {addon_name} addon: {str(e)}')
        raise
    logger.success(f'{addon_name} addon loaded')


def download_io_scene_fbx(addon_directory, addon_name, github_url):
    logger.info(f'{addon_name} addon not installed, installing from {github_url}')
    # Download the repo as a zip file
    response = requests.get(github_url)
    zip_path = os.path.join(addon_directory, f'{addon_name}.zip')
    # Save the zip file
    with open(zip_path, 'wb') as file:
        file.write(response.content)
    # Extract the zip file
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(addon_directory)
    # Remove the zip file
    Path(zip_path).unlink()
