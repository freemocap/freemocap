import sys

from PySide6.QtCore import QDir
from PySide6.QtGui import QFileSystemModel, QAction
from PySide6.QtWidgets import QTreeView, QFileIconProvider, QScroller, QApplication, QMenu


class DirectoryViewer(QTreeView):
    def __init__(self, root_path=None, no_custom=False, no_watch=False, parent=None):
        super().__init__(parent)

        self.model = QFileSystemModel()
        icon_provider = QFileIconProvider()
        self.model.setIconProvider(icon_provider)
        self.model.setRootPath("")
        if no_custom:
            self.model.setOption(QFileSystemModel.DontUseCustomDirectoryIcons)
        if no_watch:
            self.model.setOption(QFileSystemModel.DontWatchForChanges)
        self.setModel(self.model)
        if root_path:
            root_index = self.model.index(QDir.cleanPath(root_path))
            if root_index.isValid():
                self.setRootIndex(root_index)

        # Demonstrating look and feel features
        self.setAnimated(False)
        self.setIndentation(20)
        self.setSortingEnabled(True)
        availableSize = self.screen().availableGeometry().size()
        self.resize(availableSize / 2)
        self.setColumnWidth(0, int(self.width() / 3))

        # Make it flickable on touchscreens
        QScroller.grabGesture(self, QScroller.ScrollerGestureType.TouchGesture)

        self.setWindowTitle("Directory Viewer")

    def contextMenuEvent(self, event):
        contextMenu = QMenu(self)

        setRecordingAct = QAction("Set Active Recording", self)
        setRecordingAct.triggered.connect(self.set_active_recording)
        contextMenu.addAction(setRecordingAct)

        contextMenu.exec(event.globalPos())

    def set_active_recording(self):
        index = self.currentIndex()
        self.expand(index)

        # Change the color for the active recording using a stylesheet
        self.setStyleSheet("QTreeView::item:selected {background: red;}")

        # also color children of the active recording
        for index in self.get_children(index):  # noqa (do we want to reassign the index value while we're looping?)
            self.setStyleSheet("QTreeView::item:selected {background: pink;}")

        # Keep the parent directory expanded
        parent_index = self.model.parent(index)
        self.expand(parent_index)

        for i in range(self.model.rowCount(index)):
            self.expand(self.model.index(i, 0, index))

        # Collapse other directories
        self.collapse_siblings(index, parent_index)

    def collapse_siblings(self, index, parent_index):
        sibling = self.indexAbove(index)
        parent = self.model.filePath(parent_index)

        while sibling.isValid():
            if self.isExpanded(sibling) and self.model.filePath(sibling) != parent:
                self.collapse(sibling)
            sibling = self.indexAbove(sibling)

        sibling = self.indexBelow(index)
        while sibling.isValid():
            if self.isExpanded(sibling) and self.model.filePath(sibling) != parent:
                self.collapse(sibling)
            sibling = self.indexBelow(sibling)

    def get_children(self, parent_index):
        children = []
        for i in range(self.model.rowCount(parent_index)):
            child_index = self.model.index(i, 0, parent_index)
            children.append(child_index)
        return children


if __name__ == "__main__":
    app = QApplication([])
    viewer = DirectoryViewer()
    viewer.show()
    sys.exit(app.exec())
