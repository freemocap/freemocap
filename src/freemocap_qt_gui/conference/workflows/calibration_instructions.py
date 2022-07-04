from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class CalibrationInstructions(QWidget):

    def __init__(self):
        super().__init__()
        # Holds the Camera Configuration Title
        container = QVBoxLayout()

        instructions_title_layout = QVBoxLayout()
        instructions_title = QLabel("Spacial Positioning Calibration")
        instructions_title_layout.addWidget(instructions_title)

        description_layout = QVBoxLayout()
        description_1 = QLabel("Hold up the Curuko boards so all cameras can see every square. Don't have one? Get one here ")
        description_2 = QLabel("Note: You may need to adjust the cameras if you are having an issue")
        description_layout.addWidget(description_1)
        description_layout.addWidget(description_2)

        continue_button_layout = QHBoxLayout()
        continue_button = QPushButton("Continue")
        continue_button_layout.addWidget(continue_button)

        container.addLayout(instructions_title_layout)
        container.addLayout(description_layout)
        container.addLayout(continue_button_layout)

        self.setLayout(container)

