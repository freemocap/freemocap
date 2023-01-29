import cv2
import numpy as np
import pyqtgraph as pg
import pyqtgraph.opengl as gl
from pyqtgraph.Qt import QtWidgets
from pyqtgraph.dockarea.Dock import Dock
from pyqtgraph.dockarea.DockArea import DockArea

from src.core_processes.capture_volume_calibration.calibration_dataclasses import (
    CameraCalibrationData,
)


class CalibrationDiagnosticsVisualizer:
    def __init__(self):
        # dummy data to initialize subplots
        self.reprojection_error_all = np.empty(0)
        self.reprojection_error_current_best = np.empty(0)
        self.image_point_original = np.empty(0)
        self.image_point_remapped = np.empty(0)

        # create icis_conference_main app and window
        self.pyqtgraph_app = pg.mkQApp("DockArea Example")
        self.main_window_widget = QtWidgets.QMainWindow()
        self.dock_area = DockArea()
        self.main_window_widget.setCentralWidget(self.dock_area)
        self.main_window_widget.resize(1000, 500)
        self.main_window_widget.setWindowTitle("Lens Distortion Calibration Diagnostics (pyqtgraph)")

        # create widget/dock for image subplot (based on `GraphicsItems - ImageItem - video` example `python -m pyqtgraph.examples`)
        self.image_view_widget = pg.ImageView()

        self.undistorted_image_dock = Dock("Undistorted Image")
        self.undistorted_image_dock.addWidget(self.image_view_widget)
        self.dock_area.addDock(self.undistorted_image_dock)

        # create widget/dock for reprojection error subplot
        self.reprojection_error_plot_widget = pg.PlotWidget(title="Reprojection Error")
        self.reprojection_error_plot_widget.setLabel("left", "Reprojection Error", units="pixels")
        self.reprojection_error_plot_widget.setLabel("bottom", "Time", units="Frame#")
        self.reprojection_error_plot_widget.setYRange(0, 2)
        self.reprojection_error_plot_widget.addLegend()
        self.reprojection_error_all_line = self.reprojection_error_plot_widget.plot(
            self.reprojection_error_all,
            pen=(255, 0, 128),
            name="reprojection error- all",
        )
        self.reprojection_error_current_best_line = self.reprojection_error_plot_widget.plot(
            self.reprojection_error_current_best, name="current best"
        )

        self.reprojection_error_dock = Dock("Reprojection Error")
        self.reprojection_error_dock.addWidget(self.reprojection_error_plot_widget)
        self.dock_area.addDock(self.reprojection_error_dock, position="right")

        # create widget/dock lens distortion remapping subplot
        self.image_point_remapping_plot_widget = pg.PlotWidget(title="Image Point Remapping")
        self.image_point_remapping_plot_widget.setLabel("left", "Y-position", units="pixels")
        self.image_point_remapping_plot_widget.setLabel("bottom", "X-position", units="pixels")
        self.image_point_remapping_plot_widget.addLegend()

        self.image_point_original_dottos = self.image_point_remapping_plot_widget.plot(
            self.image_point_original,
            self.image_point_original,
            pen=None,
            symbol="o",
            symbolBrush=None,
            symbolPen=(150, 150, 150),
            name="image points - original",
        )
        self.image_point_remapped_dottos = self.image_point_remapping_plot_widget.plot(
            self.image_point_remapped,
            self.image_point_remapped,
            symbol="+",
            pen=None,
            symbolBrush=None,
            symbolPen=(50, 150, 210),
            name="image points - remapped",
        )
        self.image_point_remapping_plot_dock = Dock("Image Point Remapping")
        self.image_point_remapping_plot_dock.addWidget(self.image_point_remapping_plot_widget)
        self.dock_area.addDock(self.image_point_remapping_plot_dock)

        ###########
        # create widget/dock opengl 3d plot for charuco dottos
        self.opengl_3d_plot_widget = gl.GLViewWidget()
        self.opengl_grid_item = gl.GLGridItem()
        self.opengl_3d_plot_widget.addItem(self.opengl_grid_item)

        # create XYZ axes
        x_axis_line_array = np.array([[0, 0, 0], [1, 0, 0]])
        y_axis_line_array = np.array([[0, 0, 0], [0, 1, 0]])
        z_axis_line_array = np.array([[0, 0, 0], [0, 0, 1]])

        self.origin_x_axis_gl_lineplot_item = gl.GLLinePlotItem(
            pos=x_axis_line_array, color=(1, 0, 0, 1), width=1.0, antialias=True
        )
        self.origin_y_axis_gl_lineplot_item = gl.GLLinePlotItem(
            pos=y_axis_line_array, color=(0, 1, 0, 1), width=1.0, antialias=True
        )
        self.origin_z_axis_gl_lineplot_item = gl.GLLinePlotItem(
            pos=z_axis_line_array, color=(0, 0, 1, 1), width=1.0, antialias=True
        )
        self.opengl_3d_plot_widget.addItem(self.origin_x_axis_gl_lineplot_item)
        self.opengl_3d_plot_widget.addItem(self.origin_y_axis_gl_lineplot_item)
        self.opengl_3d_plot_widget.addItem(self.origin_z_axis_gl_lineplot_item)

        self.opengl_charuco_scatter_item = gl.GLScatterPlotItem(pos=(0, 0, 0), color=(1, 0, 1), size=1, pxMode=False)

        self.opengl_3d_plot_dock = Dock("Image Point Remapping")
        self.opengl_3d_plot_dock.addWidget(self.opengl_3d_plot_widget)
        self.dock_area.addDock(self.opengl_3d_plot_dock, "right", self.image_point_remapping_plot_dock)

        ###
        # create widget/dock for calibration text window
        self.calibration_text_widget = QtWidgets.QLabel()

        self.calibration_text_dock = Dock("Calibration Data")
        self.calibration_text_dock.addWidget(self.calibration_text_widget)
        self.dock_area.addDock(self.calibration_text_dock, "above", self.image_point_remapping_plot_dock)

        self._display_main_window()

    def _display_main_window(self):
        # display window
        self.main_window_widget.show_window()

    def update_image_subplot(self, new_image):
        self.image_view_widget.setImage(
            cv2.cvtColor(cv2.rotate(new_image, cv2.ROTATE_90_COUNTERCLOCKWISE), cv2.COLOR_BGR2RGB)
        )

    def update_reprojection_error_subplot(self, reprojection_error_new, reprojection_error_current_best):
        self.reprojection_error_all = np.append(self.reprojection_error_all, reprojection_error_new)
        self.reprojection_error_current_best = np.append(
            self.reprojection_error_current_best, reprojection_error_current_best
        )

        self.reprojection_error_all_line.setData(self.reprojection_error_all)
        self.reprojection_error_current_best_line.setData(self.reprojection_error_current_best)

    def update_calibration_text_overlay(self, calibration_data: CameraCalibrationData):
        lens_distortion_as_str = [f"{d[0]:.3f}" for d in calibration_data.lens_distortion_coefficients]
        calibration_text = f"reprojection error:{calibration_data.reprojection_error:.3f} \n {lens_distortion_as_str} \n {str(calibration_data.camera_matrix)}"
        self.calibration_text_widget.setText(calibration_text)

    def update_image_point_remapping_subplot(
        self,
        image_point_original_x,
        image_point_original_y,
        image_point_remapped_x,
        image_point_remapped_y,
    ):
        self.image_point_original_dottos.setData(x=image_point_original_x, y=image_point_original_y)

        self.image_point_remapped_dottos.setData(x=image_point_remapped_x, y=image_point_remapped_y)

    def update_3d_subplot(self, charuco_xyz: np.ndarray = None):
        if charuco_xyz is None:
            return
        self.opengl_charuco_scatter_item.setData(pos=charuco_xyz)

    def close(self):
        self.main_window_widget.close()
