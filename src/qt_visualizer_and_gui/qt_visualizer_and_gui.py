import logging

import cv2
import pyqtgraph as pg
from pyqtgraph.dockarea.Dock import Dock
from pyqtgraph.dockarea.DockArea import DockArea
from pyqtgraph.Qt import QtWidgets

logger = logging.getLogger(__name__)

class QTVisualizerAndGui:
    def __init__(self):
        # https://pyqtgraph.readthedocs.io/en/latest/config_options.html
        pg.setConfigOptions(imageAxisOrder='row-major')
        self.pyqtgraph_app = pg.mkQApp("FreeMoCap! :O ")
        self._dict_of_camera_image_item_widgets = {}

    def setup_and_launch(self, cam_and_writer_response_list):
        print('beep')
        self._setup_main_window()
        self._setup_camera_views(cam_and_writer_response_list)
        self._display_app_window()
        print('boop')

    def _setup_main_window(self, window_width: int = 1000, window_height: int = 1000):
        """
        This is the main main window for the GUI.
        Its structure is based loosely on the 'Dock Widgets' example from `python -m pyqtgraph.examples`
        """
        self._main_window_widget = QtWidgets.QMainWindow()
        self._main_window_widget.resize(window_width, window_height)

        self._main_dock_area = DockArea()
        self._main_window_widget.setCentralWidget(self._main_dock_area)
        self._main_window_widget.setWindowTitle('Main Window ;D')

        self._camera_graphics_layout_window = pg.GraphicsLayoutWidget()
        self._camera_views_dock = Dock('Camera Views')
        self._camera_views_dock.addWidget(self._camera_graphics_layout_window)
        self._main_dock_area.addDock(self._camera_views_dock, position='top')

    def _display_app_window(self):
        self._main_window_widget.show()

    def close(self):
        self._main_window_widget.close()

    def update_camera_view_image(self, webcam_id, image_to_display):
        try:
            camera_image_item_widget = self._dict_of_camera_image_item_widgets[webcam_id]
        except Exception as e:
            logger.warning(f'Could not find ViewBoxWidget for camera {webcam_id}')
            raise e
        camera_image_item_widget.setImage(cv2.cvtColor(image_to_display, cv2.COLOR_BGR2RGB))


    def _setup_camera_views(self, cam_and_writer_response_list):
        for this_response in cam_and_writer_response_list:
            this_webcam_id = this_response.cv_cam.webcam_id_as_str
            self._dict_of_camera_image_item_widgets[this_webcam_id] = self._create_camera_view_widget(this_webcam_id)

    def _create_camera_view_widget(self, webcam_id):
        camera_view_box_widget = pg.ViewBox(invertY=True, lockAspect=True)
        camera_image_item = pg.ImageItem()
        camera_view_box_widget.addItem(camera_image_item)
        self._camera_graphics_layout_window.addItem(camera_view_box_widget)
        return camera_image_item
