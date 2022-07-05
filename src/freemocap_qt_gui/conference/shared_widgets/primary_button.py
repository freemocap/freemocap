from PyQt6.QtWidgets import QPushButton


class PrimaryButton(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setStyleSheet("""
        QPushButton {
            background-color: #336e6d;
            color: #ffffff;
            border-radius: 4px;
            min-height: 32px;
            max-width: 160px;
            font-weight: 400;
            font-size: 16px;
        }
        QPushButton:hover {
            background-color: #365d5f;
        }
        """)
