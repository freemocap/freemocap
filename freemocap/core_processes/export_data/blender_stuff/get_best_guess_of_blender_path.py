import logging
import platform
from pathlib import Path
from typing import Union
from packaging import version

logger = logging.getLogger(__name__)


def guess_blender_exe_path_from_path(base_path: Union[str, Path]) -> Path:
    blender_folder_paths = sorted(
        [path for path in base_path.rglob("Blender 3*") if "blender.exe" in (p.name for p in path.iterdir())],
        key=lambda x: version.parse(x.name.split()[-1]),
        reverse=True
    )
    if blender_folder_paths:
        blender_exe_path = blender_folder_paths[0] / "blender.exe"
        if blender_exe_path.is_file():
            return blender_exe_path
    return None


def get_best_guess_of_blender_path():
    if platform.system() == "Windows":
        paths_to_check = [
            Path(r"C:\Program Files\Blender Foundation"),
            Path(Path.home()) / "Blender Foundation"
        ]

        found_paths = []
        for base_path in paths_to_check:
            blender_exe_path = guess_blender_exe_path_from_path(base_path)
            if blender_exe_path is not None and blender_exe_path.is_file():
                found_paths.append((version.parse(blender_exe_path.parent.name.split()[-1]), blender_exe_path))

        if found_paths:
            highest_version_path = max(found_paths, key=lambda x: x[0])[1]
            logger.info(
                f"Windows machine detected - highest version of `blender` found at: {str(highest_version_path)}")
            return str(highest_version_path)
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
