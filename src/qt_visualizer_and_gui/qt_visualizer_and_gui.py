import cv2
import pyqtgraph as pg
from pyqtgraph.dockarea.Dock import Dock
from pyqtgraph.dockarea.DockArea import DockArea
from pyqtgraph.Qt import QtWidgets


class QTVisualizerAndGui:
    def __init__(self):
        self.pyqtgraph_app = pg.mkQApp("FreeMoCap! :O ")
        self._dict_of_image_view_widgets = {}

    def setup_and_launch(self, cam_and_writer_response_list):
        print('beep')
        self._setup_main_window()
        self._setup_camera_views(cam_and_writer_response_list)
        self._display_app_window()
        print('boop')

    def _setup_main_window(self):
        """
        This is the main main window for the GUI.
        Its structure is based loosely on the 'Dock Widgets' example from `python -m pyqtgraph.examples`
        """
        self.main_window_widget = QtWidgets.QMainWindow()
        self.dock_area = DockArea()
        self.main_window_widget.setCentralWidget(self.dock_area)
        window_title_string = 'Main Window ;D'
        self.main_window_widget.setWindowTitle(window_title_string)

    def _display_app_window(self):
        self.main_window_widget.show()

    def close(self):
        self.main_window_widget.close()

    def update_camera_view(self, webcam_id, image_to_display):

        try:
            image_view_widget = self._dict_of_image_view_widgets[webcam_id]

        except KeyError:
            image_view_widget = self.create_camera_view(webcam_id)
        except Exception as e:
            raise e

        image_view_widget.setImage(
            cv2.cvtColor(cv2.rotate(image_to_display,
                                    cv2.ROTATE_90_COUNTERCLOCKWISE),
                         cv2.COLOR_BGR2RGB))

    def create_camera_view(self, webcam_id):
        image_view_widget = pg.ImageView()
        this_camera_dock = Dock('Camera ' + webcam_id)
        this_camera_dock.addWidget(image_view_widget)
        self.dock_area.addDock(this_camera_dock)

        return image_view_widget

    def _setup_camera_views(self, cam_and_writer_response_list):
        pass
