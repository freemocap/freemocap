import os
import sys
from pathlib import Path
from typing import Union

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFileSystemModel
from PyQt6.QtWidgets import QWidget, QTreeView, QVBoxLayout, QMenu
from qtpy import QtGui

from src.config.home_dir import get_freemocap_data_folder_path, get_session_folder_path
from src.gui.main.app_state.app_state import APP_STATE

import logging

logger = logging.getLogger(__name__)


class FileSystemViewWidget(QWidget):
    load_session_folder_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.setWindowTitle("File System Viewer")
        # self.setGeometry(300, 300, appWidth, appHeight)

        self._file_system_model = QFileSystemModel()
        self._tree_view_widget = QTreeView()
        layout.addWidget(self._tree_view_widget)

        self._tree_view_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree_view_widget.customContextMenuRequested.connect(self._context_menu)
        self._tree_view_widget.doubleClicked.connect(self.open_file)

        self._tree_view_widget.setModel(self._file_system_model)
        # self.tree.setColumnWidth(0, 250)
        self._tree_view_widget.setAlternatingRowColors(True)
        self._tree_view_widget.resizeColumnToContents(1)

    def set_freemocap_data_path(self, freemocap_data_path: Union[str, Path]):
        self._freemocap_data_path = freemocap_data_path
        self.set_folder_as_root(self._freemocap_data_path)

    def set_folder_as_root(self, folder_path: Union[str, Path]):
        self._file_system_model.setRootPath(folder_path)
        self._tree_view_widget.setRootIndex(self._file_system_model.index(folder_path))

    def _context_menu(self):
        menu = QMenu()
        open = menu.addAction("Open file")
        open.triggered.connect(self.open_file)
        load_session = menu.addAction("Load session folder")
        load_session.triggered.connect(self.load_session_folder)

        cursor = QtGui.QCursor()
        menu.exec_(cursor.pos())

    def open_file(self):
        index = self._tree_view_widget.currentIndex()
        file_path = self._file_system_model.filePath(index)
        logger.info(f"Opening file from file_system_view_widget: {file_path}")
        os.startfile(file_path)

    def load_session_folder(self):
        index = self._tree_view_widget.currentIndex()
        file_path = Path(self._file_system_model.filePath(index))
        if file_path.is_file():
            file_path = Path(file_path).parent
        session_id = str(file_path.relative_to(self._freemocap_data_path))

        logger.info(f"Loading session - {session_id} - from file_system_view_widget")

        self.load_session_folder_signal.emit(str(session_id))
