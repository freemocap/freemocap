# from -https://gist.github.com/peace098beat/db8ef7161508e6500ebe?permalink_comment_id=3542714#gistcomment-3542714

import sys

from PyQt6.QtWidgets import QMainWindow, QApplication


class MainWidget(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Drag and Drop")
        self.resize(720, 480)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        for f in files:
            print(f)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = MainWidget()
    ui.show()
    sys.exit(app.exec())
