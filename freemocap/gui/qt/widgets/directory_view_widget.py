import logging
from copy import copy
from pathlib import Path
from typing import Union, Callable

from PyQt6.QtGui import QFileSystemModel
from PyQt6.QtWidgets import QLabel, QMenu, QTreeView, QVBoxLayout, QWidget, QPushButton
from qtpy import QtGui

from freemocap.system.paths_and_files_names import get_recording_session_folder_path
from freemocap.system.start_file import open_file

logger = logging.getLogger(__name__)


class DirectoryViewWidget(QWidget):
    def __init__(self, top_level_folder_path: Union[str, Path], get_active_recording_info_callable: Callable):
        logger.info("Creating QtDirectoryViewWidget")
        super().__init__()
        self._minimum_width = 300
        self.setMinimumWidth(self._minimum_width)

        self._top_level_folder_path = top_level_folder_path
        self._get_active_recording_info_callable = get_active_recording_info_callable

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._show_freemocap_data_folder_button = QPushButton("Show FreeMoCap Data Folder")
        self._show_freemocap_data_folder_button.clicked.connect(
            lambda: self.set_folder_as_root(self._top_level_folder_path)
        )
        self._show_freemocap_data_folder_button.hide()
        self._layout.addWidget(self._show_freemocap_data_folder_button)

        self._path_label = QLabel(str(self._top_level_folder_path))
        self._layout.addWidget(self._path_label)
        self._file_system_model = QFileSystemModel()
        self._tree_view_widget = QTreeView()

        self._layout.addWidget(self._tree_view_widget)

        # self._tree_view_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree_view_widget.customContextMenuRequested.connect(self._context_menu)
        self._tree_view_widget.doubleClicked.connect(self.open_file)

        self._tree_view_widget.setModel(self._file_system_model)

        self._tree_view_widget.setAlternatingRowColors(True)
        self._tree_view_widget.resizeColumnToContents(1)

        if self._top_level_folder_path is not None:
            self.set_folder_as_root(self._top_level_folder_path)

    def expand_directory_to_path(self, directory_path: Union[str, Path], collapse_other_directories: bool = True):
        if collapse_other_directories:
            logger.debug("Collapsing other directories")
            self._tree_view_widget.collapseAll()
        logger.debug(f"Expanding directory at  path: {str(directory_path)}")
        og_index = self._file_system_model.index(str(directory_path))
        self._tree_view_widget.expand(og_index)

        parent_path = copy(directory_path)
        while Path(self._file_system_model.rootPath()) in Path(parent_path).parents:
            parent_path = Path(parent_path).parent
            index = self._file_system_model.index(str(parent_path))
            logger.debug(f"Expanding parent directory at  path: {str(parent_path)}")
            self._tree_view_widget.expand(index)

        self._tree_view_widget.scrollTo(og_index)

    def set_folder_as_root(self, folder_path: Union[str, Path]):
        logger.info(f"Setting root folder to {str(folder_path)}")
        self._tree_view_widget.setWindowTitle(str(folder_path))
        self._file_system_model.setRootPath(str(folder_path))
        self._tree_view_widget.setRootIndex(self._file_system_model.index(str(folder_path)))
        self._tree_view_widget.setColumnWidth(0, int(self._minimum_width * 0.9))

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
        open_file(file_path)

    def set_path_as_index(self, path: Union[str, Path]):
        logger.info(f"Setting current index to : {str(path)}")
        self._tree_view_widget.setCurrentIndex(self._file_system_model.index(str(path)))

    def handle_new_active_recording_selected(self) -> None:
        current_recording_info = self._get_active_recording_info_callable()
        if current_recording_info is None:
            self.set_folder_as_root(self._top_level_folder_path)
            self._show_freemocap_data_folder_button.hide()
            self.expand_directory_to_path(get_recording_session_folder_path())
            return

        self.set_folder_as_root(current_recording_info.path)
        self._show_freemocap_data_folder_button.show()
        synchronized_videos_path = current_recording_info.synchronized_videos_folder_path
        if synchronized_videos_path is not None:
            self.expand_directory_to_path(synchronized_videos_path)
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
