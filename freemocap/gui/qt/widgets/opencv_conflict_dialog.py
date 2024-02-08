import logging
import subprocess
import sys
import threading
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QDialog, QPushButton, QLabel, QHBoxLayout, QFrame

from freemocap.gui.qt.utilities.save_and_load_gui_state import GuiState
from freemocap.utilities.fix_opencv_conflict import fix_opencv_conflict

logger = logging.getLogger(__name__)


class OpencvConflictDialog(QDialog):
    def __init__(self, gui_state: GuiState, kill_thread_event: threading.Event, parent=None) -> None:
        super().__init__(parent=parent)
        self.gui_state = gui_state
        self.kill_thread_event = kill_thread_event

        self.setMinimumSize(600, 300)

        self.setWindowTitle("Conflicting OpenCV Versions Found")

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        version_conflict_message = (
            "Opencv-python and opencv-contrib-python are both installed in your current environment, "
            "which will prevent you from being able to calibrate multiple cameras.\n\n"
            "Choosing `Fix OpenCV version conflict` will remove the existing OpenCV versions and install opencv-contrib-python. "
            "It will also close Freemocap to make the changes take affect, but everything will work when restarted. \n\n"
            "If you choose not to fix the conflict, you will need to manually install opencv-contrib-python and restart Freemocap "
            "in order for multi camera calibration to work."
        )
        welcome_text_label = QLabel(version_conflict_message)
        welcome_text_label.setWordWrap(True)
        welcome_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(welcome_text_label, 1)

        self.frame = QFrame()
        self.frame.setFrameShape(QFrame.Shape.HLine)
        self.frame.setFrameShadow(QFrame.Shadow.Sunken)
        self._layout.addWidget(self.frame)

        single_camera_recording_doc_link_string = '&#10132; <a href="https://github.com/pypa/pip/pull/10837" style="color: #333333;">Pip pull request that would resolve this issue</a>'
        single_camera_doc_link = QLabel(single_camera_recording_doc_link_string)
        single_camera_doc_link.setOpenExternalLinks(True)
        self._layout.addWidget(single_camera_doc_link)

        button_box = QHBoxLayout()

        fix_opencv_button = QPushButton("Recommended: Fix OpenCV conflict")
        fix_opencv_button.clicked.connect(self.fix_conflict_and_close)
        button_box.addWidget(fix_opencv_button)

        continue_unchanged_button = QPushButton("Continue without fixing conflict")
        continue_unchanged_button.setObjectName("continue_unchanged_button")
        continue_unchanged_button.clicked.connect(self.accept)
        button_box.addWidget(continue_unchanged_button)

        self._layout.addLayout(button_box)

    def fix_conflict_and_close(self):
        try:
            fix_opencv_conflict()
            logger.info("Successfully fixed opencv conflict, closing GUI")
        except subprocess.CalledProcessError:
            logger.error(
                "Failed to fix opencv conflict, please uninstall all opencv versions and run `pip install opencv-contrib-python==4.8.*` manually"
            )
            sys.exit(1)
        finally:
            sys.exit(0)
