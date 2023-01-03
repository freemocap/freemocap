from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from old_src.gui.icis_conference_main.shared_widgets.primary_button import PrimaryButton


class RecordInstructions(QWidget):
    def __init__(self):
        super().__init__()
        self._record_button = PrimaryButton("Record")

        container = QVBoxLayout()
        container.addLayout(self._create_title_layout())
        container.addLayout(self._create_description_layout())
        container.addLayout(self._create_record_button_container())

        self.setLayout(container)

    @property
    def record(self):
        return self._record_button

    def _create_title_layout(self):
        instructions_title_layout = QVBoxLayout()
        instructions_title = QLabel("Start Recording")
        instructions_title_layout.addWidget(instructions_title)
        return instructions_title_layout

    def _create_description_layout(self):
        description_layout = QVBoxLayout()
        description_1 = QLabel(
            "Cameras are configured & calibrated. Hit the record button when you're ready! "
        )
        description_layout.addWidget(description_1)
        return description_layout

    def _create_record_button_container(self):
        continue_button_layout = QHBoxLayout()
        continue_button_layout.addWidget(self._record_button)
        return continue_button_layout
