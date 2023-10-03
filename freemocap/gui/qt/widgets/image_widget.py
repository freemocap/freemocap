from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout


class ImageWidget(QWidget):
    def __init__(self, image_path: str, scaling_factor: float = 0.85):
        super().__init__()
        self.image = QImage(image_path)
        self.label = QLabel()
        self.label.setPixmap(QPixmap.fromImage(self.image))
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.label)
        self.setLayout(self.layout)
        self.scaling_factor = scaling_factor

    def resizeEvent(self, event):
        self.label.setPixmap(
            QPixmap.fromImage(self.image).scaled(self.size() * self.scaling_factor, Qt.AspectRatioMode.KeepAspectRatio)
        )
