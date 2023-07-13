import logging
from copy import copy
from pathlib import Path
from typing import Union, Callable

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFileSystemModel
from PyQt6.QtWidgets import QLabel, QMenu, QTreeView, QVBoxLayout, QWidget, QPushButton
from qtpy import QtGui

from freemocap.system.open_file import open_file
from freemocap.system.paths_and_filenames.path_getters import get_recording_session_folder_path

logger = logging.getLogger(__name__)


class DirectoryViewWidget(QWidget):
    new_active_recording_selected_signal = pyqtSignal(str)

    def __init__(self, top_level_folder_path: Union[str, Path], get_active_recording_info_callable: Callable):
        self._root_folder = None
        logger.info("Creating QtDirectoryViewWidget")
        super().__init__()
        self._minimum_width = 300
        self.setMinimumWidth(self._minimum_width)

        self._top_level_folder_path = top_level_folder_path
        self._get_active_recording_info_callable = get_active_recording_info_callable

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._file_system_model = QFileSystemModel()

        self._tree_view_widget = QTreeView()
        self._tree_view_widget.setHeaderHidden(False)

        self._layout.addWidget(self._tree_view_widget)

        self._tree_view_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree_view_widget.customContextMenuRequested.connect(self._context_menu)
        self._tree_view_widget.doubleClicked.connect(self._open_file)

        self._tree_view_widget.setModel(self._file_system_model)

        self._tree_view_widget.setAlternatingRowColors(True)
        self._tree_view_widget.setColumnWidth(0, 250)

        if self._top_level_folder_path is not None:
            self.set_folder_as_root(self._top_level_folder_path)

        self._show_freemocap_data_folder_button = QPushButton("Show FreeMoCap Data Folder")
        self._show_freemocap_data_folder_button.clicked.connect(
            lambda: self.set_folder_as_root(self._top_level_folder_path)
        )

        self._layout.addWidget(self._show_freemocap_data_folder_button)

        self._path_label = QLabel(str(self._top_level_folder_path))
        self._layout.addWidget(self._path_label)

    def expand_directory_to_path(self, path: Union[str, Path], collapse_other_directories: bool = True):
        if collapse_other_directories:
            logger.debug("Collapsing other directories")
            self._tree_view_widget.collapseAll()
        logger.debug(f"Expanding directory at  path: {str(path)}")
        og_index = self._file_system_model.index(str(path))
        self._tree_view_widget.expand(og_index)

        parent_path = copy(path)
        while Path(self._file_system_model.rootPath()) in Path(parent_path).parents:
            parent_path = Path(parent_path).parent
            index = self._file_system_model.index(str(parent_path))
            logger.debug(f"Expanding parent directory at  path: {str(parent_path)}")
            self._tree_view_widget.expand(index)

        self._tree_view_widget.scrollTo(og_index)

    def set_folder_as_root(self, folder_path: Union[str, Path]):
        logger.info(f"Setting root folder to {str(folder_path)}")
        self._root_folder = folder_path
        self._tree_view_widget.setWindowTitle(str(folder_path))
        self._file_system_model.setRootPath(str(folder_path))
        self._tree_view_widget.setRootIndex(self._file_system_model.index(str(folder_path)))
        self._tree_view_widget.setColumnWidth(0, int(self._minimum_width * 0.9))

    def _context_menu(self):
        menu = QMenu()
        open = menu.addAction("Open file")
        open.triggered.connect(self._open_file)

        set_as_active_recording = menu.addAction("Set as Active Recording folder")
        set_as_active_recording.triggered.connect(self._set_recording_as_active)

        go_to_parent_directory = menu.addAction("Go to parent directory")
        go_to_parent_directory.triggered.connect(self._go_to_parent_directory)

        cursor = QtGui.QCursor()
        menu.exec(cursor.pos())

    def _open_file(self):
        index = self._tree_view_widget.currentIndex()
        file_path = self._file_system_model.filePath(index)
        logger.info(f"Opening file from file_system_view_widget: {file_path}")
        open_file(file_path)

    def _set_recording_as_active(self):
        index = self._tree_view_widget.currentIndex()
        file_path = Path(self._file_system_model.filePath(index))
        logger.info(f"Setting {file_path} as 'Active Recording' folder")
        self.new_active_recording_selected_signal.emit(str(file_path))

    def _go_to_parent_directory(self):
        logger.debug(f"Setting parent directory as root: {Path(self._root_folder).parent}")
        self.set_folder_as_root(Path(self._root_folder).parent)
        self.expand_directory_to_path(self._root_folder, collapse_other_directories=False)

    def set_path_as_index(self, path: Union[str, Path]):
        logger.info(f"Setting current index to : {str(path)}")
        self._tree_view_widget.setCurrentIndex(self._file_system_model.index(str(path)))

    def handle_new_active_recording_selected(self) -> None:
        current_recording_info = self._get_active_recording_info_callable()
        if current_recording_info is None:
            # self.set_folder_as_root(self._top_level_folder_path)
            self._show_freemocap_data_folder_button.hide()
            self.expand_directory_to_path(get_recording_session_folder_path())
            return

        # self.set_folder_as_root(current_recording_info.path)
        self._tree_view_widget.setCurrentIndex(self._file_system_model.index(str(current_recording_info.path)))

        if current_recording_info.annotated_videos_folder_path is not None:
            self.expand_directory_to_path(current_recording_info.annotated_videos_folder_path)
        elif current_recording_info.synchronized_videos_folder_path is not None:
            self.expand_directory_to_path(current_recording_info.synchronized_videos_folder_path)
        else:
            self.expand_directory_to_path(current_recording_info.path)


if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    directory_view_widget = DirectoryViewWidget(top_level_folder_path=Path.home())

    directory_view_widget.show()

    # index = directory_view_widget.expand_directory_to_path(Path.home() / ".atom")
    directory_view_widget.expand_directory_to_path(Path.home() / "Downloads")

    sys.exit(app.exec())
