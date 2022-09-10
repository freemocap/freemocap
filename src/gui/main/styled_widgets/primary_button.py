from PyQt6.QtWidgets import QPushButton

active_primary_button_style_sheet = """
        QPushButton {
            background-color: #336e6d;
            color: #ffffff;
            border-radius: 4px;
            min-height: 24px;
            font-size: 16px;
        }
        QPushButton:hover {
            background-color: #365d5f;
        }
        """


# not_active_primary_button_style_sheet = """
#         QPushButton {
#             background-color: 'lightgrey';
#             color: #ffffff;
#             border-radius: 4px;
#             min-height: 32px;
#             max-width: 160px;
#             font-weight: 400;
#             font-size: 16px;
#         }
#         QPushButton:hover {
#             background-color: 'lightgrey';
#         }
#         """


class PrimaryButton(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setStyleSheet(active_primary_button_style_sheet)
