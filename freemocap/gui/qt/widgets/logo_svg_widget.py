from PySide6.QtCore import Qt
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import QSizePolicy


class LogoSvgWidget(QSvgWidget):
    def __init__(self, image_path: str):
        super().__init__()
        self.load(image_path)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.renderer().setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
