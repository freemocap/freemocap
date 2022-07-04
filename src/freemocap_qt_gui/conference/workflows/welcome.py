from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class Welcome(QWidget):

    def __init__(self):
        super().__init__()

        self._new_session_button = QPushButton("Start New Session")

        container = QVBoxLayout()
        container.addLayout(self._create_title_layout())
        container.addLayout(self._create_new_session_button())

        self.setLayout(container)

    @property
    def new_session(self):
        return self._new_session_button

    def _create_title_layout(self):
        welcome_title_layout = QVBoxLayout()

        welcome_l1_title = QLabel("Welcome")
        welcome_l2_title = QLabel("to")
        welcome_l3_title = QLabel("FreeMoCap")

        welcome_title_layout.addWidget(welcome_l1_title)
        welcome_title_layout.addWidget(welcome_l2_title)
        welcome_title_layout.addWidget(welcome_l3_title)

        return welcome_title_layout

    def _create_new_session_button(self):
        new_session_container = QHBoxLayout()
        new_session_container.addWidget(self._new_session_button)
        return new_session_container

