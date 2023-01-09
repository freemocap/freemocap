from old_src.gui.main.qt_utils.set_font_size import set_font_size
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel


class PanelSectionTitle(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        set_font_size(self, 12)
        self.setStyleSheet("weight: bold")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # self.setStyleSheet("padding-bottom: 5px")
