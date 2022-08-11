from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel

from src.gui.main.styled_widgets.page_title import PageTitle


class ViewingPanel:
    def __init__(self):
        self._frame = QFrame()
        self._frame.setFrameShape(QFrame.Shape.StyledPanel)
        self._layout = QVBoxLayout()
        self._frame.setLayout(self._layout)

        self._layout.addWidget(self._welcome_to_freemocap_title())

    @property
    def frame(self):
        return self._frame

    @property
    def layout(self):
        return self._layout

    def _welcome_to_freemocap_title(self):
        session_title = PageTitle(
            "Welcome  to  FreeMoCap! \n  \U00002728 \U0001F480 \U00002728 "
        )
        return session_title
