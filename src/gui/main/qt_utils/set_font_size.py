from PyQt6.QtWidgets import QLabel


def set_font_size(label_widget: QLabel, size: int):
    font = label_widget.font()
    font.setPointSize(size)
    label_widget.setFont(font)
