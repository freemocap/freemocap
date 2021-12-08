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
from rich.traceback import Frame


class FMC_Visualizer:
    def __init__(self, fmc_session_obj = None, recording_session_path = None):

        #setup QT app window
        self.app = pg.mkQApp("FreeMoCap Data Visualizer")
        self.gl_view_widget = gl.GLViewWidget()
        self.gl_view_widget.show()
        self.gl_view_widget.setWindowTitle('FreeMoCap Data Visualizer')
        self.gl_view_widget.setCameraPosition(distance=10)

        gl_grid_item = gl.GLGridItem()
        self.gl_view_widget.addItem(gl_grid_item)

        
        if fmc_session_obj is None:       
            if recording_session_path: 
                self.recording_session_path = Path(recording_session_path)
            else:
                pass
                #JSM NOTE - add something to load the last recorded session if nothing is specified
                
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

        self.mediapipe_gl_scatter_item = gl.GLScatterPlotItem(pos=self.mediapipe_nFrames_nTrackedPoints_XYZ[self.frame_num,:,:], color=(1,0,1,.3), size=.1, pxMode=False)
        self.gl_view_widget.addItem(self.mediapipe_gl_scatter_item)

        self.qt_timer = QtCore.QTimer()
        self.qt_timer.timeout.connect(self.update)
        self.qt_timer.start(50)



    def update(self):
        
        self.frame_num +=1 
        if self.frame_num > self.num_frames:
            self.frame_num = 0
        
            
        self.charuco_gl_scatter_item.setData(pos=self.charuco_nFrames_nTrackedPoints_XYZ[self.frame_num,:,:])
        self.mediapipe_gl_scatter_item.setData(pos=self.mediapipe_nFrames_nTrackedPoints_XYZ[self.frame_num,:,:])
        
        if self.frame_num % 10 == 0:
            print("Frame Num : " + str(self.frame_num))
    
    def start(self):
        if (sys.flags.interactive != 1) or not hasattr(QtCore, "PYQT_VERSION"):
            QtGui.QApplication.instance().exec_()        


if __name__ == '__main__':
    pg.exec()
