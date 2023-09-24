import io
import logging
import zipfile
from pathlib import Path

import requests

from freemocap.system.paths_and_filenames.file_and_folder_names import (
    FIGSHARE_TEST_ZIP_FILE_URL, FIGSHARE_SAMPLE_ZIP_FILE_URL, )
from freemocap.system.paths_and_filenames.path_getters import get_test_data_path, \
    get_sample_data_path

logger = logging.getLogger(__name__)


def data_folder_exists(data_path: str):
    if Path(data_path).exists() and not len(list(Path(data_path).iterdir())) == 0:
        logger.info(f"Data already exists at {data_path})")
        return True
    else:
        return False


def download_sample_data(overwrite: bool = False) -> str:
    save_path = get_sample_data_path()
    if not overwrite and data_folder_exists(save_path):
        logger.info(f"Sample data already exists at {save_path}. Skipping download.")
        return save_path

    logger.info(f"Downloading sample data from {FIGSHARE_SAMPLE_ZIP_FILE_URL} to {save_path}...")
    download_figshare_data(data_zip_file_url=FIGSHARE_SAMPLE_ZIP_FILE_URL,
                           save_path=save_path)
    return save_path


def download_test_data(overwrite: bool = False) -> str:
    save_path = get_test_data_path()
    if not overwrite and data_folder_exists(save_path):
        logger.info(f"Test data already exists at {save_path}. Skipping download.")
        return save_path

    logger.info(f"Downloading test data from {FIGSHARE_TEST_ZIP_FILE_URL} to {save_path}...")
    download_figshare_data(data_zip_file_url=FIGSHARE_TEST_ZIP_FILE_URL,
                           save_path=save_path)
    return save_path


def download_figshare_data(data_zip_file_url: str,
                           save_path: str):
    try:
        logger.info(f"Downloading sample data from {data_zip_file_url}...")

        r = requests.get(data_zip_file_url, stream=True, timeout=(5, 60))
        r.raise_for_status()  # Check if request was successful

        z = zipfile.ZipFile(io.BytesIO(r.content))
        save_path = Path(save_path)
        save_path.mkdir(parents=True, exist_ok=True)
        z.extractall(save_path)
        logger.info(f"FigShare data from {data_zip_file_url} extracted to {str(save_path)}")

    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
    except zipfile.BadZipFile as e:
        logger.error(f"Failed to unzip the file: {e}")
    except Exception as e:
        logger.error(f"Error during downloading data from {data_zip_file_url}: {e}")
        raise e


if __name__ == "__main__":
    sample_data_path_in = download_test_data()
    print(f"Sample data downloaded successfully to path: {str(sample_data_path_in)}")
