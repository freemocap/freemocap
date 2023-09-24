from pathlib import Path
from typing import Union

from PyQt6.QtWidgets import QWidget


def apply_css_style_sheet(qt_widget: QWidget, path_to_css_file: Union[str, Path]):
    with open(path_to_css_file, "r") as css_file:
        css_string = css_file.read()
        qt_widget.setStyleSheet(css_string)
