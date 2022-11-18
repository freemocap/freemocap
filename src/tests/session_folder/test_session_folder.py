from pathlib import Path
from typing import Union
from unittest import TestCase

import cv2

from src.config.home_dir import (
    SYNCHRONIZED_VIDEOS_FOLDER_NAME,
    OUTPUT_DATA_FOLDER_NAME,
    MEDIAPIPE_2D_NPY_FILE_NAME,
)


class SessionFolderTestCase(TestCase):
    pass
    # def __init__(self, session_folder_path: Union[str, Path]):
    #     super().__init__()
    #     self._session_folder_path = session_folder_path
    #
    #     # test folder structure
    #     self._get_folder_names()
    #     self._test_folders_exist()
    #
    # def _get_folder_names(self):
    #
    #     self._synchronized_videos_folder = (
    #         self._session_folder_path / SYNCHRONIZED_VIDEOS_FOLDER_NAME
    #     )
    #     self._output_data_folder = self._session_folder_path / OUTPUT_DATA_FOLDER_NAME
    #
    #     # handle pre-alpha names
    #     if not self._synchronized_videos_folder.exists():
    #         self._synchronized_videos_folder = (
    #             self._session_folder_path / "SyncedVideos"
    #         )
    #
    #     if not self._output_data_folder.exists():
    #         self._output_data_folder = self._session_folder_path / "DataArrays"
    #
    # def _test_folders_exist(self):
    #     self.assertTrue(self._synchronized_videos_folder.exists())
    #     self.assertTrue(self._output_data_folder.exists())
    #
