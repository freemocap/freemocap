import logging
from pathlib import Path
from typing import Union

from PyQt6 import QtCore
from PyQt6.QtCore import pyqtSlot, QFileSystemWatcher

from freemocap.gui.qt.style_sheet.compile_scss_to_css import compile_scss_to_css

logger = logging.getLogger(__name__)


class SCSSFileWatcher(QFileSystemWatcher):
    def __init__(self, path_to_scss_file: Union[str, Path], path_to_css_file: Union[str, Path], parent=None):
        super().__init__(parent)
        self.addPath(str(path_to_scss_file))
        self.parent = parent
        self.path_to_scss_file = str(path_to_scss_file)
        self.path_to_css_file = str(path_to_css_file)
        self.fileChanged.connect(self.file_changed)

    @pyqtSlot(str)
    def file_changed(self, path: str):
        logger.info(f"SCSS file changed: {path} - running compile_scss_to_css")

        try:
            compile_scss_to_css(self.path_to_scss_file, self.path_to_css_file)
            logger.info("SCSS compilation finished")
        except Exception as e:
            logger.error(f"Error in SCSS compilation: {e}")


if __name__ == "__main__":
    app = QtCore.QCoreApplication([])
    qt_file_system_watcher = SCSSFileWatcher(
        path_to_scss_file=Path(__file__).parent / "qt_style_sheet.scss",
        path_to_css_file=Path(__file__).parent / "qt_style_sheet.css",
    )
    print(f"watching directories - {qt_file_system_watcher.directories()})")
    print(f"watching files - {qt_file_system_watcher.files()})")
    app.exec()
    print("done!")
