import sys

from PyQt6.QtGui import QFileSystemModel
from PyQt6.QtWidgets import QWidget, QTreeView, QVBoxLayout

from src.config.home_dir import get_freemocap_data_folder_path


class FileSystemViewWidget(QWidget):
    def __init__(self):
        super().__init__()
        appWidth = 800
        appHeight = 300
        self.setWindowTitle("File System Viewer")
        self.setGeometry(300, 300, appWidth, appHeight)

        freemocap_data_path = get_freemocap_data_folder_path(create_folder=False)
        self._file_system_model = QFileSystemModel()
        self._file_system_model.setRootPath(freemocap_data_path)
        self._tree_view_widget = QTreeView()
        self._tree_view_widget.setModel(self._file_system_model)
        self._tree_view_widget.setRootIndex(
            self._file_system_model.index(freemocap_data_path)
        )
        # self.tree.setColumnWidth(0, 250)
        self._tree_view_widget.setAlternatingRowColors(True)

        layout = QVBoxLayout()
        layout.addWidget(self._tree_view_widget)
        self.setLayout(layout)
