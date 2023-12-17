import sys

from PySide6.QtCore import QDir
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem, QFileIconProvider, QApplication, QFileSystemModel

from freemocap.system.paths_and_filenames.path_getters import get_freemocap_data_folder_path


class DirectoryTreeViewWidget(QTreeWidget):
    def __init__(self, root_path=get_freemocap_data_folder_path(), parent=None):
        super().__init__(parent)
        self.header().close()

        self.populate_tree(root_path)
        self.setAnimated(False)

        # Other setup code...

    def populate_tree(self, root_path):
        fs_model = QFileSystemModel()
        fs_model.setRootPath(root_path)
        root_idx = fs_model.index(QDir.cleanPath(root_path))

        self.add_items(self, root_idx, fs_model)

    def add_items(self, parent_widget, parent_index, fs_model):
        for i in range(fs_model.rowCount(parent_index)):
            index = fs_model.index(i, 0, parent_index)
            text = fs_model.fileName(index)
            item = QTreeWidgetItem(parent_widget, [text])

            # Set icon
            icon_provider = QFileIconProvider()
            icon = icon_provider.icon(fs_model.fileInfo(index))
            item.setIcon(0, icon)

            if fs_model.isDir(index):
                self.add_items(item, index, fs_model)



if __name__ == "__main__":
    app = QApplication([])
    viewer = DirectoryTreeViewWidget()
    viewer.show()
    sys.exit(app.exec())
