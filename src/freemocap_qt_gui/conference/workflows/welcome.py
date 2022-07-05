from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget, QGridLayout, QSpacerItem

from src.freemocap_qt_gui.conference.qt_utils.set_font_size import set_font_size
from src.freemocap_qt_gui.conference.shared_widgets.primary_button import PrimaryButton


class Welcome(QWidget):

    def __init__(self):
        super().__init__()

        self._new_session_button = PrimaryButton("Start New Session")

        container = QVBoxLayout()
        # container.addLayout(self._create_logo())
        container.addLayout(self._create_title_layout())
        container.addLayout(self._create_new_session_button())

        self.setLayout(container)

    @property
    def new_session(self):
        return self._new_session_button

    def _create_title_layout(self):
        welcome_title_layout = QVBoxLayout()

        welcome_l1_title = QLabel("Welcome to FreeMoCap")

        set_font_size(welcome_l1_title, 30)
        welcome_title_layout.addWidget(welcome_l1_title)
        welcome_l1_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return welcome_title_layout

    def _create_new_session_button(self):
        new_session_container = QHBoxLayout()
        new_session_container.addWidget(self._new_session_button)
        return new_session_container
    #
    # def _create_logo(self):
    #     grid = QGridLayout()
    #     label = QLabel()
    #     pixmap = QPixmap('../images/skelly-3-4-22.png')
    #     label.setPixmap(pixmap)
    #     grid.addWidget(label, 1, 1)
    #     return grid
