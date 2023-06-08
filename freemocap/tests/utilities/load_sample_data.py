import io
import logging

import requests
import zipfile
from pathlib import Path

from freemocap.system.paths_and_filenames.file_and_folder_names import (
    FIGSHARE_SAMPLE_DATA_FILE_NAME,
    FIGSHARE_ZIP_FILE_URL,
)
from freemocap.system.paths_and_filenames.path_getters import get_recording_session_folder_path

logger = logging.getLogger(__name__)

# TODO - some of the naming in this file is inconsistent with the rest of the codebase. Needs fixed at some point. Also I think a lot of the `find_..` functions should be in a different file?


def load_sample_data(sample_data_zip_file_url: str = FIGSHARE_ZIP_FILE_URL) -> str:
    try:
        logger.info(f"Downloading sample data from {sample_data_zip_file_url}...")

        recording_session_folder_path = Path(get_recording_session_folder_path())
        recording_session_folder_path.mkdir(parents=True, exist_ok=True)

        r = requests.get(FIGSHARE_ZIP_FILE_URL, stream=True)
        r.raise_for_status()  # Check if request was successful

        z = zipfile.ZipFile(io.BytesIO(r.content))
        z.extractall(recording_session_folder_path)

        figshare_sample_data_path = recording_session_folder_path / FIGSHARE_SAMPLE_DATA_FILE_NAME
        logger.info(f"Sample data extracted to {str(figshare_sample_data_path)}")
        return str(figshare_sample_data_path)

    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
    except zipfile.BadZipFile as e:
        logger.error(f"Failed to unzip the file: {e}")


if __name__ == "__main__":
    sample_data_path = load_sample_data()
    print(f"Sample data downloaded successfully to path: {str(sample_data_path)}")
