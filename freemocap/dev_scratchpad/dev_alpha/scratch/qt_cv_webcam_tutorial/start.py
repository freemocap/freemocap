from PyQt5.QtWidgets import QApplication

from models import Camera
from views import StartWindow

camera = Camera(0)
camera.initialize()

app = QApplication([])
start_window = StartWindow(camera)
start_window.show()
app.exit(app.exec_())