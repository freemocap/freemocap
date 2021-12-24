from PyQt5.QtWidgets import QMainWindow, QWidget, QPushButton, QVBoxLayout, QApplication

from pyqtgraph import ImageView

import numpy as np

class StartWindow(QMainWindow):
    def __init__(self, camera):
        super().__init__()
        self.camera = camera
        self.central_widget = QWidget()
        self.acquire_frame = QPushButton('Acquire Frame', self.central_widget)
        self.start_movie = QPushButton('Start Movie', self.central_widget)
        self.image_view = ImageView()

        self.layout = QVBoxLayout(self.central_widget)
        self.layout.addWidget(self.image_view)
        self.layout.addWidget(self.acquire_frame)
        self.layout.addWidget(self.start_movie)
        self.setCentralWidget(self.central_widget)

        self.acquire_frame.clicked.connect(self.update_image)
    
    def button_clicked(self):
        print('botton clicnked')

    def update_image(self):
        frame = self.camera.get_frame()
        self.image_view.setImage(frame.T)
        print('Maximum in frame: {}, Minimum in frame: {}'.format(np.max(frame), np.min(frame)))


if __name__ == '__main__':
    app  = QApplication([])
    window = StartWindow()
    window.show()
    app.exit(app.exec_())