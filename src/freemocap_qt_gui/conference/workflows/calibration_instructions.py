from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class CalibrationInstructions(QWidget):

    def __init__(self):
        super().__init__()
        self._continue_button = QPushButton("Continue")

        container = QVBoxLayout()
        container.addLayout(self._create_title_layout())
        container.addLayout(self._create_description_layout())
        container.addLayout(self._create_continue_button_container())

        self.setLayout(container)

    @property
    def continue_button(self):
        return self._continue_button

    def _create_title_layout(self):
        instructions_title_layout = QVBoxLayout()
        instructions_title = QLabel("Spacial Positioning Calibration")
        instructions_title_layout.addWidget(instructions_title)
        return instructions_title_layout

    def _create_description_layout(self):
        description_layout = QVBoxLayout()
        description_1 = QLabel("Hold up the Charuko boards so all cameras can see every square. Don't have one? Get one here ")
        description_2 = QLabel("Note: You may need to adjust the cameras if you are having an issue")
        description_layout.addWidget(description_1)
        description_layout.addWidget(description_2)
        return description_layout

    def _create_continue_button_container(self):
        continue_button_layout = QHBoxLayout()
        continue_button_layout.addWidget(self._continue_button)
        return continue_button_layout
