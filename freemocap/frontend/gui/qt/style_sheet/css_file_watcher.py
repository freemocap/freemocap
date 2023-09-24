import logging
from pathlib import Path
from typing import Union

from PyQt6 import QtCore
from PyQt6.QtCore import pyqtSlot, QFileSystemWatcher

logger = logging.getLogger(__name__)


class CSSFileWatcher(QFileSystemWatcher):
    def __init__(self, path_to_css_file: Union[str, Path], parent=None):
        super().__init__(parent)
        self.addPath(str(path_to_css_file))
        self.parent = parent
        self.fileChanged.connect(self.file_changed)

    @pyqtSlot(str)
    def file_changed(self, path: str):
        logger.info(f"CSS file changed: {path} - updating MainWindow stylesheet")

        try:
            with open(path, "r") as css_file:
                logger.info(f"Reading CSS file from: {path}")
                css_string = css_file.read()
                logger.info(f"Setting stylesheet for {self.parent}")
                self.parent.setStyleSheet(css_string)
        except Exception as e:
            logger.error(f"Error setting stylesheet: {e}")


if __name__ == "__main__":
    app = QtCore.QCoreApplication([])
    qt_file_system_watcher = CSSFileWatcher(path_to_css_file=Path(__file__).parent / "qt_style_sheet.css")
    print(f"watching directories - {qt_file_system_watcher.directories()})")
    print(f"watching files - {qt_file_system_watcher.files()})")
    app.exec()
    print("done!")
