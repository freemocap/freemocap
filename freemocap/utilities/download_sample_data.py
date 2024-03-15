import io
import logging
import zipfile
from pathlib import Path

import requests

from freemocap.system.paths_and_filenames.file_and_folder_names import (
    FREEMOCAP_TEST_DATA_RECORDING_NAME,
    FIGSHARE_TEST_ZIP_FILE_URL,
)
from freemocap.system.paths_and_filenames.path_getters import get_recording_session_folder_path

logger = logging.getLogger(__name__)


def get_sample_data_path(download_if_needed: bool = True) -> str:
    sample_data_path = str(Path(get_recording_session_folder_path()) / FREEMOCAP_TEST_DATA_RECORDING_NAME)
    if not Path(sample_data_path).exists():
        if download_if_needed:
            download_sample_data()
        else:
            raise Exception(f"Could not find sample data at {sample_data_path} (and `download_if_needed` is False)")

    return sample_data_path


def download_sample_data(sample_data_zip_file_url: str = FIGSHARE_TEST_ZIP_FILE_URL) -> str:
    try:
        logger.info(f"Downloading sample data from {sample_data_zip_file_url}...")

        recording_session_folder_path = Path(get_recording_session_folder_path())
        recording_session_folder_path.mkdir(parents=True, exist_ok=True)

        r = requests.get(sample_data_zip_file_url, stream=True, timeout=(5, 60))
        r.raise_for_status()  # Check if request was successful

        z = zipfile.ZipFile(io.BytesIO(r.content))
        z.extractall(recording_session_folder_path)

        figshare_sample_data_path = recording_session_folder_path / FREEMOCAP_TEST_DATA_RECORDING_NAME
        logger.info(f"Sample data extracted to {str(figshare_sample_data_path)}")
        return str(figshare_sample_data_path)

    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        raise e
    except zipfile.BadZipFile as e:
        logger.error(f"Failed to unzip the file: {e}")
        raise e


if __name__ == "__main__":
    sample_data_path = download_sample_data()
    print(f"Sample data downloaded successfully to path: {str(sample_data_path)}")
