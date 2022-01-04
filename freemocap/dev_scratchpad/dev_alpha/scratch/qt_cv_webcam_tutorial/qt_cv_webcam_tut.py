# from - https://www.pythonforthelab.com/blog/step-by-step-guide-to-building-a-gui/
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget

def button_pressed():
    print('button done been pressed')

app = QApplication([])
main_window  = QMainWindow()
central_widget = QWidget()

button_1 = QPushButton("test1", central_widget)
button_1.clicked.connect(button_pressed)

button_2 = QPushButton("test2", central_widget)
button_2.clicked.connect(button_pressed)

layout = QVBoxLayout(central_widget)
layout.addWidget(button_2)
layout.addWidget(button_1)

main_window.setCentralWidget(central_widget)

main_window.show()

app.exit(app.exec_())