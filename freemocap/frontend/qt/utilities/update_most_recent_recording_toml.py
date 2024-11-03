import logging

import toml

from freemocap.data_layer.recording_models.recording_info_model import RecordingInfoModel
from freemocap.system.paths_and_filenames.path_getters import get_most_recent_recording_toml_path

logger = logging.getLogger(__name__)


def update_most_recent_recording_toml(recording_info_model: RecordingInfoModel):
    """Save the most recent recording path to a toml file"""

    output_file_path = get_most_recent_recording_toml_path()

    logger.info(
        f"Saving most recent recording path {str(recording_info_model.path)} to toml file: {str(output_file_path)}"
    )
    toml_dict = {}
    toml_dict["most_recent_recording_path"] = str(recording_info_model.path)
    toml_dict["recording_status"] = recording_info_model.status_check

    with open(str(output_file_path), "w") as toml_file:
        toml.dump(toml_dict, toml_file)
