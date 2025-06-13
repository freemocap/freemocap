import io
import logging
import zipfile
from pathlib import Path

import requests
from dataclasses import dataclass
from freemocap.system.paths_and_filenames.path_getters import get_recording_session_folder_path

logger = logging.getLogger(__name__)


# def get_sample_data_path(download_if_needed: bool = True) -> str: #NOTE - this function is mainly used in headlesses processes - do we need want to replicate/update/deprecate it?
#     sample_data_path = str(Path(get_recording_session_folder_path()) / FREEMOCAP_TEST_DATA_RECORDING_NAME)
#     if not Path(sample_data_path).exists():
#         if download_if_needed:
#             download_sample_data()
#         else:
#             raise Exception(f"Could not find sample data at {sample_data_path} (and `download_if_needed` is False)")

#     return sample_data_path



@dataclass 
class Sample:
    url: str

DATASETS = {
    "sample": Sample(url = "https://github.com/freemocap/skellysamples/releases/download/sample_data_v06_12_25/freemocap_sample_data.zip"),
    "test": Sample(url = "https://github.com/freemocap/skellysamples/releases/download/test_data_v06_09_25/freemocap_test_data.zip")
}

def get_dataset(key: str) -> Path:
    try:
        spec = DATASETS[key]
    except KeyError:
        raise ValueError(f"Unknown dataset '{key}'. Options: {list(DATASETS)}")

    return Path(download_data(spec.url))

def download_data(zip_file_url) -> str:
    try:
        logger.info(f"Downloading data from {zip_file_url}...")
        recording_session_folder_path = Path(get_recording_session_folder_path())
        recording_session_folder_path.mkdir(parents=True, exist_ok=True)
        r = requests.get(zip_file_url, stream=True, timeout=(5, 60))
        r.raise_for_status()

        z = zipfile.ZipFile(io.BytesIO(r.content))
        z.extractall(recording_session_folder_path)

        recording_name = {Path(p).parts[0] for p in z.namelist() if not p.endswith("/")} #gets name of recording (top-level folder in zip file)
        if len(recording_name) != 1:
            raise ValueError(f"{zip_file_url!r} contained {len(recording_name)} top-level entries: {recording_name}")

        data_path = recording_session_folder_path / recording_name.pop()
        logger.info(f"Data extracted to {str(data_path)}")
        return str(data_path)
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        raise e
    except zipfile.BadZipFile as e:
        logger.error(f"Failed to unzip the file: {e}")
        raise e
        
def download_test_data() -> str:
    """
    Downloads the test data zip file and extracts it to the recording session folder.
    Returns the path to the extracted data.
    """
    return download_data(DATASETS["test"].url)

def download_sample_data() -> str:
    """
    Downloads the sample data zip file and extracts it to the recording session folder.
    Returns the path to the extracted data.
    """
    return download_data(DATASETS["sample"].url)

if __name__ == "__main__":
    sample_data_path = download_sample_data()
    print(f"Sample data downloaded successfully to path: {str(sample_data_path)}")
