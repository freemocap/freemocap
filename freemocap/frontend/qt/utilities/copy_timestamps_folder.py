import logging
import shutil
from pathlib import Path
from typing import Union

logger = logging.getLogger(__name__)


def copy_directory_if_contains_timestamps(source_dir: Union[Path, str], destination_dir: Union[Path, str]) -> bool:
    source_path = Path(source_dir)
    destination_path = Path(destination_dir)

    # Check if the source directory exists
    if not source_path.is_dir():
        raise ValueError(f"{source_dir} is not a valid directory.")

    # Check if the directory contains a directory or file called 'timestamps'
    timestamps_path = source_path / "timestamps"
    if not timestamps_path.exists():
        logger.info(f"{source_dir} does not contain a 'timestamps' directory or file.")
        return False

    # Create the destination directory if it doesn't exist
    destination_path.mkdir(parents=True, exist_ok=True)

    if destination_path.stem == "timestamps":
        destination_path = destination_path.parent

    # Copy the 'timestamps' directory/file to the destination directory
    shutil.copytree(timestamps_path, destination_path / "timestamps", dirs_exist_ok=True)
    return True
