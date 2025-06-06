from __future__ import annotations
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QSizePolicy
from PySide6.QtCore import Qt

class GroundPlaneCalibrationFailedDialog(QDialog):
    def __init__(self, message: str):
        super().__init__()
        self.setWindowTitle("Ground Plane Calibration Failed")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumSize(500, 200)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        # Entire dialog styling (includes title bar area)
        self.setStyleSheet("""
            QDialog {
                background-color: #ffe0dc; 
            }
            QLabel#titleLabel {
                font-weight: bold;
                font-size: 12pt;
                color: black;
            }
            QLabel#messageLabel {
                font-size: 10.5pt;
                color: black;
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Title
        title = QLabel("Ground Plane Calibration Failed")
        title.setObjectName("titleLabel")

        # Message
        message_label = QLabel(message)
        message_label.setObjectName("messageLabel")
        message_label.setWordWrap(True)
        message_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # OK Button
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)

        layout.addWidget(title)
        layout.addWidget(message_label)
        layout.addStretch(1)
        layout.addWidget(ok_button, alignment=Qt.AlignmentFlag.AlignRight)

        self.setLayout(layout)
