from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class Welcome(QWidget):

    def __init__(self):
        super().__init__()
        # Holds the Camera Configuration Title
        container = QVBoxLayout()

        welcome_title_layout = QVBoxLayout()

        welcome_l1_title = QLabel("Welcome")
        welcome_l2_title = QLabel("to")
        welcome_l3_title = QLabel("FreeMoCap")

        welcome_title_layout.addWidget(welcome_l1_title)
        welcome_title_layout.addWidget(welcome_l2_title)
        welcome_title_layout.addWidget(welcome_l3_title)

        new_session_container = QHBoxLayout()
        new_session_button = QPushButton("Start New Session")
        new_session_container.addWidget(new_session_button)

