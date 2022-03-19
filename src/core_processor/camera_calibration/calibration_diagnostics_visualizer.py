import numpy as np
import pyqtgraph as pg


class CalibrationDiagnosticsVisualizer:
    def __init__(self):
        self.graphics_layout_window = pg.GraphicsLayoutWidget(show=True)
        self.graphics_layout_window.setWindowTitle('pyqtgraph example: Scrolling Plots')

        self.reprojection_error_all = np.empty(0)

        self.reprojection_error_subplot = self.graphics_layout_window.addPlot()
        self.reprojection_error_line = self.reprojection_error_subplot.plot(self.reprojection_error_all)

        self.subplot_1 = self.graphics_layout_window.addPlot()
        self.data1 = np.random.normal(size=300)
        self.curve2 = self.subplot_1.plot(self.data1)
        self.ptr1 = 0

    def update(self, reprojection_error_current):
        # update reprojection error subplot
        self.reprojection_error_all = np.append(self.reprojection_error_all, reprojection_error_current)
        self.reprojection_error_line.setData(self.reprojection_error_all)

        # update other subplot
        self.curve2.setData(self.data1)
        self.curve2.setPos(self.ptr1, 0)

    def close(self):
        self.graphics_layout_window.close()
