import logging
import platform
from pathlib import Path
from typing import Union, Optional

logger = logging.getLogger(__name__)


def guess_blender_exe_path_from_path(base_path: Union[str, Path]) -> Optional[Path]:
    base_path = Path(base_path)
    try:
        blender_folder_paths = [path for path in base_path.rglob("blender.exe")]
    except OSError:
        logger.info(f"Unable to access: {str(base_path)}")
        return

    if blender_folder_paths:

        if len(blender_folder_paths) == 0:
            return None

        best_guess = blender_folder_paths[-1]

        return best_guess


def get_best_guess_of_blender_path():
    if platform.system() == "Windows":
        # check all lettered drives and the user's home directory
        paths_to_check = [
            Path(f"{letter}:/Program Files/Blender Foundation") for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        ]

        paths_to_check.append(Path.home() / "Blender Foundation")

        for base_path in paths_to_check:
            blender_exe_path = guess_blender_exe_path_from_path(base_path)
            if blender_exe_path is not None and blender_exe_path.is_file():
                logger.info(f"Found `blender.exe` at: {str(blender_exe_path)}")

                return str(blender_exe_path)
        else:
            logger.warning(
                "Could not find `blender.exe` in the expected locations. Please locate it manually (or install Blender, if it isn't installed)."
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
                "Could not find Blender executable in the applications folder. Please locate it manually (or install Blender, if it isn't installed)."
            )
            return None

    if platform.system() == "Linux":
        blender_path_list = [
            Path("/usr/bin"),
            Path("/usr/sbin"),
            Path("/usr/local/bin"),
            Path("/usr/local/sbin"),
            Path("/bin"),
            Path("/sbin"),
            Path("/snap/bin"),
        ]
        for path in blender_path_list:
            blender_path = path / "blender"
            if blender_path.exists():
                logger.info(f"Linux machine detected - guessing that `blender` is installed at: {str(blender_path)}")

                return str(blender_path)

        logger.info(
            "Could not find Blender executable in bin. Please locate it manually (or install Blender, if it isn't installed)."
        )
        return None

    else:
        logger.info("Machine system not detected, please locate Blender path manually.")
        return None


if __name__ == "__main__":
    print(f" blender path: {get_best_guess_of_blender_path()}")
