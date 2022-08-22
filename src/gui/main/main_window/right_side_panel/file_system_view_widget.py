import os
import sys
from pathlib import Path
from typing import Union

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFileSystemModel
from PyQt6.QtWidgets import QWidget, QTreeView, QVBoxLayout, QMenu
from qtpy import QtGui

from src.config.home_dir import get_freemocap_data_folder_path, get_session_folder_path
from src.gui.main.app_state.app_state import APP_STATE


class FileSystemViewWidget(QWidget):
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

    def set_session_path_as_root(self):
        freemocap_data_folder_path = get_freemocap_data_folder_path(create_folder=False)
        session_path = get_session_folder_path(APP_STATE.session_id, create_folder=True)
        self._file_system_model.setRootPath(freemocap_data_folder_path)
        self._tree_view_widget.setRootIndex(self._file_system_model.index(session_path))

    def _context_menu(self):
        menu = QMenu()
        open = menu.addAction("Open file")
        open.triggered.connect(self.open_file)

        cursor = QtGui.QCursor()
        menu.exec_(cursor.pos())

    def open_file(self):
        index = self._tree_view_widget.currentIndex()
        file_path = self._file_system_model.filePath(index)
        os.startfile(file_path)
