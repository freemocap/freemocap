import logging
from pathlib import Path
from typing import Union

import toml

from freemocap.system.paths_and_files_names import (
    get_most_recent_recording_toml_path,
    SYNCHRONIZED_VIDEOS_FOLDER_NAME,
)

logger = logging.getLogger(__name__)


def save_most_recent_recording_path_as_toml(most_recent_recording_path: Union[str, Path]):
    """Save the most recent recording path to a toml file"""

    if Path(most_recent_recording_path).stem == SYNCHRONIZED_VIDEOS_FOLDER_NAME:
        most_recent_recording_path = Path(most_recent_recording_path).parent

    output_file_path = get_most_recent_recording_toml_path()

    logger.info(
        f"Saving most recent recording path {str(most_recent_recording_path)} to toml file: {str(output_file_path)}"
    )
    toml_dict = {}
    toml_dict["most_recent_recording_path"] = str(most_recent_recording_path)

    with open(str(output_file_path), "w") as toml_file:
        toml.dump(toml_dict, toml_file)
