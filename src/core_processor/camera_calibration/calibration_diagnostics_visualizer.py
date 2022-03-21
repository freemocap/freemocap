import numpy as np
import pyqtgraph as pg
import cv2


class CalibrationDiagnosticsVisualizer:
    def __init__(self):
        self.graphics_layout_window = pg.GraphicsLayoutWidget(show=True)
        self.graphics_layout_window.setWindowTitle('Reprojection Error')

        # dummy data to initialize subplots
        self.reprojection_error_all = np.empty(0)
        self.reprojection_error_current_best = np.empty(0)
        self.image_point_original = np.empty(0)
        self.image_point_remapped = np.empty(0)

        # create image subplot (based on `GraphicsItems - ImageItem - video` example `python -m pyqtgraph.examples`)
        self.undistorted_image_subplot = self.graphics_layout_window.addViewBox()
        self.undistorted_image_subplot.setAspectLocked(True)
        self.image_item_holder = pg.ImageItem(border='w')
        self.undistorted_image_subplot.addItem(self.image_item_holder)

        # create reprojection error subplot
        self.reprojection_error_subplot = self.graphics_layout_window.addPlot()
        self.reprojection_error_subplot.setLabel('left', "Reprojection Error", units='pixels')
        self.reprojection_error_subplot.setLabel('bottom', "Time", units='Frame#')
        self.reprojection_error_subplot.setYRange(0, 2)
        self.reprojection_error_subplot.addLegend()
        self.reprojection_error_all_line = self.reprojection_error_subplot.plot(self.reprojection_error_all,
                                                                                pen=(255, 0, 128),
                                                                                name="reprojection error- all")
        self.reprojection_error_current_best_line = self.reprojection_error_subplot.plot(
            self.reprojection_error_current_best,
            name="current best")

        # make next row
        self.graphics_layout_window.nextRow()

        # create lens distortion remapping subplot
        self.image_point_remapping_subplot = self.graphics_layout_window.addPlot()
        self.image_point_remapping_subplot.setLabel('left', "Y-position", units='pixels')
        self.image_point_remapping_subplot.setLabel('bottom', "X-position", units='pixels')
        self.image_point_remapping_subplot.addLegend()

        self.image_point_original_line = self.image_point_remapping_subplot.plot(self.image_point_original,
                                                                                 pen=(255, 200, 200),
                                                                                 name="image points - original")
        self.image_point_remapped_line = self.image_point_remapping_subplot.plot(self.image_point_remapped,
                                                                                 pen=(0, 255, 128),
                                                                                 name="image points - remapped")




    def update_image_subplot(self, new_image):
        self.image_item_holder.setImage(cv2.cvtColor(cv2.rotate(new_image, cv2.ROTATE_90_CLOCKWISE), cv2.COLOR_BGR2RGB))

    def update_reprojection_error_subplot(self, reprojection_error_new, reprojection_error_current_best):
        self.reprojection_error_all = np.append(self.reprojection_error_all, reprojection_error_new)
        self.reprojection_error_current_best = np.append(self.reprojection_error_current_best,
                                                         reprojection_error_current_best)

        self.reprojection_error_all_line.setData(self.reprojection_error_all)
        self.reprojection_error_current_best_line.setData(self.reprojection_error_current_best)

    def update_image_point_remapping_subplot(self, image_point_original_x, image_point_original_y,
                                             image_point_remapped_x, image_point_remapped_y):
        self.image_point_original_line.setData(x=image_point_original_x,
                                               y=image_point_original_y)

        self.image_point_original_line.setData(x=image_point_remapped_x,
                                               y=image_point_remapped_y)

    def close(self):
        self.graphics_layout_window.close()
