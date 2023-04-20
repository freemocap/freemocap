import logging
import platform
from pathlib import Path
from typing import Union


logger = logging.getLogger(__name__)


def guess_blender_exe_path_from_path(base_path: Union[str, Path]) -> Path:
    blender_folder_path = [path for path in base_path.glob("Blender*")]
    if len(blender_folder_path) > 0:
        blender_exe_path = blender_folder_path[-1] / "blender.exe"
        return blender_exe_path


def get_best_guess_of_blender_path():
    if platform.system() == "Windows":

        base_path = Path("C:\Program Files\Blender Foundation")
        blender_exe_path = guess_blender_exe_path_from_path(base_path)

        if blender_exe_path is not None:
            if not blender_exe_path.is_file():
                base_path = Path(Path.home()) / "Blender Foundation"
                blender_exe_path = guess_blender_exe_path_from_path(base_path)

        if blender_exe_path is not None and blender_exe_path.is_file():
            logger.info(f"Windows machine detected - guessing that `blender` is installed at: {str(blender_exe_path)}")

            return str(blender_exe_path)
        else:
            logger.warning(
                f"Could not find `blender.exe` in the expected locations. Please located it manually (or install Blender, if it isn't installed)."
            )
            return None

    if platform.system() == "Darwin":

        blender_app_path = Path("/Applications/Blender.app")
        
        if blender_app_path.exists():
            logger.info(f"Mac machine detected - guessing that `blender` is installed at: {str(blender_app_path)}")

            blender_exe_path = blender_app_path / "Contents/MacOS/Blender"
            return str(blender_exe_path)
        else:
            logger.warning(
                f"Could not find `blender.exe` in the applications folder. Please located it manually (or install Blender, if it isn't installed)."
            )
            return None

    else:
        logger.info(f"Non-Windows/Mac machine detected - TODO - Test how this works on Linux")
        return None
