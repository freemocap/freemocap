# -*- coding: utf-8 -*-
"""
built off the '3D Graphics- Scatter Plot' example from `python -m pyqtgraph.examples`
"""
from pathlib import Path
import sys

import pyqtgraph as pg
from pyqtgraph import functions as fn
from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph.opengl as gl
import numpy as np


class FMC_Visualizer:
    def __init__(self, fmc_session_obj = None, recording_session_path = None):

        #setup QT app window
        self.app = pg.mkQApp("FreeMoCap Data Visualizer")
        self.gl_view_widget = gl.GLViewWidget()
        self.gl_view_widget.show()
        self.gl_view_widget.setWindowTitle('FreeMoCap Data Visualizer')
        self.gl_view_widget.setCameraPosition(distance=10, elevation=-90, azimuth=-90)

        grid_distance = 10
        gl_x_plane_grid_item = gl.GLGridItem()        
        gl_x_plane_grid_item.rotate(90, 0, 1, 0)
        gl_x_plane_grid_item.translate(grid_distance, 0, 0)        
        self.gl_view_widget.addItem(gl_x_plane_grid_item)
        
        gl_y_plane_grid_item = gl.GLGridItem()
        gl_y_plane_grid_item.rotate(90, 1, 0, 0)
        gl_y_plane_grid_item.translate(0, grid_distance, 0)
        self.gl_view_widget.addItem(gl_y_plane_grid_item)
        
        gl_z_plane_grid_item = gl.GLGridItem()
        gl_z_plane_grid_item.translate(0, 0, grid_distance)
        self.gl_view_widget.addItem(gl_z_plane_grid_item)
        
        origin_location_array = np.array([0,0, 0])
        x_axis_line_array = np.array([[0,0, 0], [1,0,0]])
        y_axis_line_array = np.array([[0,0, 0], [0,1,0]])
        z_axis_line_array = np.array([[0,0, 0], [0,0,1]])
                        
        # self.origin_location_scatter_item = gl.GLScatterPlotItem(pos=origin_location_array, color=(1,1,1,1),  size=.1, pxMode=False)
        self.origin_x_axis_gl_lineplot_item = gl.GLLinePlotItem(pos=x_axis_line_array, color=(1,0,0,1), width=1., antialias=True)
        self.origin_y_axis_gl_lineplot_item = gl.GLLinePlotItem(pos=y_axis_line_array, color=(0,1,0,1), width=1., antialias=True)
        self.origin_z_axis_gl_lineplot_item = gl.GLLinePlotItem(pos=z_axis_line_array, color=(0,0,1,1), width=1., antialias=True)
        
        # self.gl_view_widget.addItem(self.origin_location_scatter_item)
        self.gl_view_widget.addItem(self.origin_x_axis_gl_lineplot_item)
        self.gl_view_widget.addItem(self.origin_y_axis_gl_lineplot_item)
        self.gl_view_widget.addItem(self.origin_z_axis_gl_lineplot_item)
        
        if fmc_session_obj is None:       
            if recording_session_path: 
                self.recording_session_path = Path(recording_session_path)
            else:
                #JSM NOTE - add something to load the last recorded session if nothing is specified
                pass
                
            # load charuco data
            self.charuco_3d_path = self.recording_session_path / "charuco_3d_points.npy"
            self.charuco_nFrames_nTrackedPoints_XYZ = np.load(str(self.charuco_3d_path))
            self.charuco_nFrames_nTrackedPoints_XYZ = self.charuco_nFrames_nTrackedPoints_XYZ/1000 #convert to meters

            # load mediapipe data
            self.mediapipe_3d_path = self.recording_session_path / "mediapipe_3d_points.npy"
            self.mediapipe_nFrames_nTrackedPoints_XYZ = np.load(str(self.mediapipe_3d_path))
            self.mediapipe_nFrames_nTrackedPoints_XYZ = self.mediapipe_nFrames_nTrackedPoints_XYZ/1000 #convert to meters
        else:
            # load charuco data        
            self.charuco_nFrames_nTrackedPoints_XYZ = fmc_session_obj.charuco_nFrames_nTrackedPoints_XYZ/1000 #convert to meters

            # load mediapipe data
            self.mediapipe_nFrames_nTrackedPoints_XYZ = fmc_session_obj.mediapipe_nFrames_nTrackedPoints_XYZ/1000 #convert to meters

        self.frame_num = 0
        self.num_frames = self.charuco_nFrames_nTrackedPoints_XYZ.shape[0]


        self.charuco_gl_scatter_item = gl.GLScatterPlotItem(pos=self.charuco_nFrames_nTrackedPoints_XYZ[self.frame_num,:,:], color=(1,1,1,.3), size=.1, pxMode=False)
        self.gl_view_widget.addItem(self.charuco_gl_scatter_item)
        
        self.charuco_gl_lineplot_item = gl.GLLinePlotItem(pos=self.charuco_nFrames_nTrackedPoints_XYZ[self.frame_num,:,:], color=(0,1,1,1), width=1., antialias=True)
        self.gl_view_widget.addItem(self.charuco_gl_lineplot_item)


        # Plot Media Pipe stuff
        self.mediapipe_gl_scatter_item = gl.GLScatterPlotItem(pos=self.mediapipe_nFrames_nTrackedPoints_XYZ[self.frame_num,:,:], color=(1,0,1,.3), size=.025, pxMode=False)
        self.gl_view_widget.addItem(self.mediapipe_gl_scatter_item)

        #mediapipe body connect-the-dots order
        self.mediapipe_head_indexes = [8, 6, 5, 4, 0, 10, 9, 0, 1, 2, 3, 7 ]
        self.mediapipe_tors_indexes = [12, 11, 24, 23, 12]
        self.mediapipe_rArm_indexes = [12, 14, 16, 18, 20, 16, 22 ]
        self.mediapipe_lArm_indexes = [11, 13, 15, 17, 19, 15, 21]
        self.mediapipe_rLeg_indexes = [24, 26, 28, 30, 32, 28, ]
        self.mediapipe_lLeg_indexes = [23, 25, 27, 29, 31, 27, ]
        
        rHandIDstart = 33
        lHandIDstart = 54
        mediapipe_hand_indexes = [0,1,2,3,4,3,2,1,0,5,6,7,8,7,6,5,9,10,11,12,11,10,9,13,14,15,16,15,14,13,17,18,19,20,19,18,17,0]
        
        
        self.mediapipe_rHand_indexes = [this_index + rHandIDstart for this_index in mediapipe_hand_indexes]
        self.mediapipe_lHand_indexes = [this_index + lHandIDstart for this_index in mediapipe_hand_indexes]
        
        self.mediapipe_head_gl_lineplot_item = gl.GLLinePlotItem(pos=self.mediapipe_nFrames_nTrackedPoints_XYZ[self.frame_num,self.mediapipe_head_indexes,:], color=(1,0,1,1), width=1., antialias=True)                
        self.mediapipe_tors_gl_lineplot_item = gl.GLLinePlotItem(pos=self.mediapipe_nFrames_nTrackedPoints_XYZ[self.frame_num,self.mediapipe_tors_indexes,:], color=(1,0,1,1), width=1., antialias=True)                        
        self.mediapipe_rArm_gl_lineplot_item = gl.GLLinePlotItem(pos=self.mediapipe_nFrames_nTrackedPoints_XYZ[self.frame_num,self.mediapipe_rArm_indexes,:], color=(1,0,1,1), width=1., antialias=True)                
        self.mediapipe_lArm_gl_lineplot_item = gl.GLLinePlotItem(pos=self.mediapipe_nFrames_nTrackedPoints_XYZ[self.frame_num,self.mediapipe_lArm_indexes,:], color=(1,0,1,1), width=1., antialias=True)                
        self.mediapipe_rLeg_gl_lineplot_item = gl.GLLinePlotItem(pos=self.mediapipe_nFrames_nTrackedPoints_XYZ[self.frame_num,self.mediapipe_rLeg_indexes,:], color=(1,0,1,1), width=1., antialias=True)                
        self.mediapipe_lLeg_gl_lineplot_item = gl.GLLinePlotItem(pos=self.mediapipe_nFrames_nTrackedPoints_XYZ[self.frame_num,self.mediapipe_lLeg_indexes,:], color=(1,0,1,1), width=1., antialias=True)
        
        self.mediapipe_rHand_gl_lineplot_item = gl.GLLinePlotItem(pos=self.mediapipe_nFrames_nTrackedPoints_XYZ[self.frame_num,self.mediapipe_rHand_indexes,:], color=(1,1,0,1), width=2., antialias=True)        
        self.mediapipe_lHand_gl_lineplot_item = gl.GLLinePlotItem(pos=self.mediapipe_nFrames_nTrackedPoints_XYZ[self.frame_num,self.mediapipe_lHand_indexes,:], color=(0,1,1,1), width=2., antialias=True)
        
        
        self.gl_view_widget.addItem(self.mediapipe_head_gl_lineplot_item)
        self.gl_view_widget.addItem(self.mediapipe_tors_gl_lineplot_item)
        self.gl_view_widget.addItem(self.mediapipe_rArm_gl_lineplot_item)
        self.gl_view_widget.addItem(self.mediapipe_lArm_gl_lineplot_item)
        self.gl_view_widget.addItem(self.mediapipe_rLeg_gl_lineplot_item)
        self.gl_view_widget.addItem(self.mediapipe_lLeg_gl_lineplot_item)
        self.gl_view_widget.addItem(self.mediapipe_rHand_gl_lineplot_item)
        self.gl_view_widget.addItem(self.mediapipe_lHand_gl_lineplot_item)


        self.qt_timer = QtCore.QTimer()
        self.qt_timer.timeout.connect(self.update)
        self.qt_timer.start(50)



    def update(self):
        
        self.frame_num +=1 
        if self.frame_num > self.num_frames:
            self.frame_num = 0
        
            
        self.charuco_gl_scatter_item.setData(pos=self.charuco_nFrames_nTrackedPoints_XYZ[self.frame_num,:,:])
        self.charuco_gl_lineplot_item.setData(pos=self.charuco_nFrames_nTrackedPoints_XYZ[self.frame_num,:,:])
        
        self.mediapipe_gl_scatter_item.setData(pos=self.mediapipe_nFrames_nTrackedPoints_XYZ[self.frame_num,:,:])
        
        self.mediapipe_head_gl_lineplot_item.setData(pos=self.mediapipe_nFrames_nTrackedPoints_XYZ[self.frame_num, self.mediapipe_head_indexes,:])
        self.mediapipe_tors_gl_lineplot_item.setData(pos=self.mediapipe_nFrames_nTrackedPoints_XYZ[self.frame_num, self.mediapipe_tors_indexes,:])
        self.mediapipe_rArm_gl_lineplot_item.setData(pos=self.mediapipe_nFrames_nTrackedPoints_XYZ[self.frame_num, self.mediapipe_rArm_indexes,:])
        self.mediapipe_lArm_gl_lineplot_item.setData(pos=self.mediapipe_nFrames_nTrackedPoints_XYZ[self.frame_num, self.mediapipe_lArm_indexes,:])
        self.mediapipe_rLeg_gl_lineplot_item.setData(pos=self.mediapipe_nFrames_nTrackedPoints_XYZ[self.frame_num, self.mediapipe_rLeg_indexes,:])
        self.mediapipe_lLeg_gl_lineplot_item.setData(pos=self.mediapipe_nFrames_nTrackedPoints_XYZ[self.frame_num, self.mediapipe_lLeg_indexes,:])

        self.mediapipe_rHand_gl_lineplot_item.setData(pos=self.mediapipe_nFrames_nTrackedPoints_XYZ[self.frame_num, self.mediapipe_rHand_indexes,:])
        self.mediapipe_lHand_gl_lineplot_item.setData(pos=self.mediapipe_nFrames_nTrackedPoints_XYZ[self.frame_num, self.mediapipe_lHand_indexes,:])

        if self.frame_num % 10 == 0:
            print("Frame Num : " + str(self.frame_num) + " - ViewPoint - Distance: " + str(self.gl_view_widget.opts['distance']) + " Elevation: " + str(self.gl_view_widget.opts['elevation']) + " Azimuth: " + str(self.gl_view_widget.opts['azimuth']) )
    
    def start(self):
        if (sys.flags.interactive != 1) or not hasattr(QtCore, "PYQT_VERSION"):
            QtGui.QApplication.instance().exec_()        


if __name__ == '__main__':
        visualizer = FMC_Visualizer(recording_session_path = "C:/Users/jonma/Dropbox/FreeMoCapProject/FreeMocap_Data/FreeMoCap_Session_2021-12-09_11_05_31")
        visualizer.start()
        
