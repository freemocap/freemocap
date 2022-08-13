import sys
from pathlib import Path
from typing import Union

from PyQt6.QtGui import QFileSystemModel
from PyQt6.QtWidgets import QWidget, QTreeView, QVBoxLayout

from src.config.home_dir import get_freemocap_data_folder_path, get_session_folder_path
from src.gui.main.app_state.app_state import APP_STATE


class FileSystemViewWidget(QWidget):
    def __init__(self):
        super().__init__()
        appWidth = 800
        appHeight = 300
        self.setWindowTitle("File System Viewer")
        self.setGeometry(300, 300, appWidth, appHeight)

        self._file_system_model = QFileSystemModel()
        self._tree_view_widget = QTreeView()
        self._tree_view_widget.setModel(self._file_system_model)
        # self.tree.setColumnWidth(0, 250)
        self._tree_view_widget.setAlternatingRowColors(True)

        layout = QVBoxLayout()
        layout.addWidget(self._tree_view_widget)
        self.setLayout(layout)

    def set_session_path_as_root(self):
        session_path = get_session_folder_path(APP_STATE.session_id, create_folder=True)
        self._file_system_model.setRootPath(session_path)
        self._tree_view_widget.setRootIndex(self._file_system_model.index(session_path))
