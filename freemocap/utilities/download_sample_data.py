import io
import logging
import zipfile
from pathlib import Path

import requests
from freemocap.system.paths_and_filenames.path_getters import get_recording_session_folder_path
from pydantic import BaseModel

logger = logging.getLogger(__name__)

TEST_DATA_NAME = "test"
DOWNLOAD_SAMPLE_DATA_ACTION_NAME = "Download Sample Data (3 cameras, ~1000 frames)"

SAMPLE_DATA_NAME = "sample"
DOWNLOAD_TEST_DATA_ACTION_NAME = "Download Test Data (3 cameras, ~200 frames)"


class Dataset(BaseModel):
    url: str
    menu_label: str
    tooltip: str = (
        "Download this dataset to use in Freemocap. The sample data contains 3 cameras and ~1000 frames. The test data contains 3 cameras and ~200 frames."
    )


DATASETS = {
    SAMPLE_DATA_NAME: Dataset(
        url="https://github.com/freemocap/skellysamples/releases/download/sample_data_v06_12_25/freemocap_sample_data.zip",
        menu_label=DOWNLOAD_SAMPLE_DATA_ACTION_NAME,
    ),
    TEST_DATA_NAME: Dataset(
        url="https://github.com/freemocap/skellysamples/releases/download/test_data_v06_09_25/freemocap_test_data.zip",
        menu_label=DOWNLOAD_TEST_DATA_ACTION_NAME,
    ),
}


def download_and_extract_zip(zip_file_url) -> str:
    try:
        logger.info(f"Downloading data from {zip_file_url}...")
        recording_session_folder_path = Path(get_recording_session_folder_path())
        recording_session_folder_path.mkdir(parents=True, exist_ok=True)
        r = requests.get(zip_file_url, stream=True, timeout=(5, 60))
        r.raise_for_status()

        z = zipfile.ZipFile(io.BytesIO(r.content))
        z.extractall(recording_session_folder_path)

        recording_name = {
            Path(p).parts[0] for p in z.namelist() if not p.endswith("/")
        }  # gets name of recording (top-level folder in zip file)
        if len(recording_name) != 1:
            raise ValueError(f"{zip_file_url!r} contained {len(recording_name)} top-level entries: {recording_name}")

        data_path = recording_session_folder_path / recording_name.pop()
        logger.info("Data extracted successfully")
        return str(data_path)

    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        raise e
    except zipfile.BadZipFile as e:
        logger.error(f"Failed to unzip the file: {e}")
        raise e


def download_dataset(key: str) -> str:
    """
    Downloads the specified dataset zip file and extracts it to the recording session folder.
    Returns the path to the extracted data.
    """
    if key not in DATASETS:
        raise ValueError(f"Unknown dataset '{key}'. Options: {list(DATASETS)}")

    return download_and_extract_zip(DATASETS[key].url)


def download_test_data() -> str:
    """
    Downloads the test data zip file and extracts it to the recording session folder.
    Returns the path to the extracted data.
    """
    return download_dataset(TEST_DATA_NAME)


def download_sample_data() -> str:
    """
    Downloads the sample data zip file and extracts it to the recording session folder.
    Returns the path to the extracted data.
    """
    return download_dataset(SAMPLE_DATA_NAME)


def get_sample_data_path() -> Path:
    """
    Returns the path to the sample data folder.
    If the folder does not exist, it downloads the sample data.
    """
    sample_data_path = Path(get_recording_session_folder_path()) / "freemocap_sample_data"
    if not sample_data_path.exists():
        logger.info(f"Sample data not found at {sample_data_path}. Downloading...")
        download_sample_data()

    return sample_data_path


if __name__ == "__main__":
    sample_data_path = download_sample_data()
    print(f"Sample data downloaded successfully to path: {str(sample_data_path)}")
