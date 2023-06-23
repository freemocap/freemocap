from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QSlider, QWidget,QLabel,QHBoxLayout

class FrameCountSlider(QWidget):
    def __init__(self, num_frames:int):
        super().__init__()

        self._layout = QHBoxLayout()
        self.setLayout(self._layout)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMaximum(0)
        
        self.label = QLabel(str(self.slider.value()))
        self.slider.valueChanged.connect(lambda: self.label.setText(str(self.slider.value())))

        self._layout.addWidget(self.label)
        self._layout.addWidget(self.slider)

        self.set_slider_range(num_frames)


    def set_slider_range(self,num_frames):
        self.slider_max = num_frames - 1
        self.slider.setValue(0)
        self.slider.setMaximum(self.slider_max)

