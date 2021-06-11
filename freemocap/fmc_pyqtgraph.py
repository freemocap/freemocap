from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph.opengl as gl
import pyqtgraph as pg

import numpy as np
from pathlib import Path
import sys


class PlaySkeleton():
    def __init__(self, session):

        #set up PyQT widget (the window that pops up and shows the plots, I think ? cribbed from - https://gist.github.com/markjay4k/da2f55e28514be7160a7c5fbf95bd243)
        self.app = QtGui.QApplication(sys.argv)
        self.QtWindow = gl.GLViewWidget()
        self.QtWindow.opts['distance'] = 2000
        self.QtWindow.setWindowTitle('SessionID: {}'.format(session.sessionID))
        self.QtWindow.setGeometry(0, 110, 1920, 1080)
        self.QtWindow.show()

        # create the background grids
        # gx = gl.GLGridItem()
        # gx.rotate(90, 0, 1, 0)
        # gx.translate(-2e3, 0, 0)
        # self.QtWindow.addItem(gx)
        # gy = gl.GLGridItem()
        # gy.rotate(90, 1, 0, 0)
        # gy.translate(0, -2e3, 0)
        # self.QtWindow.addItem(gy)
        # gz = gl.GLGridItem()
        # gz.translate(0, 0, -2e3)
        # self.QtWindow.addItem(gz)

        #load data to be plotted
        # if session.skel_fr_mar_dim:
        self.skel_fr_mar_dim  = np.load(session.dataArrayPath/'openPoseSkel_3d.npy')
        self.skelScatterItem = gl.GLScatterPlotItem(pos=self.skel_fr_mar_dim, color=(1,0,1,.8), size=10, pxMode=False)
        self.QtWindow.addItem(self.skelScatterItem)

        # if session.dlc_fr_mar_dim:
        #     self.dlc_fr_mar_dim = np.load(session.dataArrayPath/'mediaPipeSkel_3d.npy')
        #     self.dlcScatterItem = gl.GLScatterPlotItem(pos=self.dlc_fr_mar_dim, color=(1,0,0,.8), size=40, pxMode=False)
        #     QtWindow.addItem(self.dlcScatterItem)


        self.charuco_mar_dim = np.load(session.dataArrayPath/'charuco_points.npy')
        self.charucoScatterItem = gl.GLScatterPlotItem(pos=self.charuco_mar_dim, color=(1,1,1,.8), size=10, pxMode=False)
        self.QtWindow.addItem(self.charucoScatterItem)

        #set frame counter
        self.currentFrameNumber = 0
        self.framerate = 30 #frames per second
        self.frameDuration = 1000/self.framerate #milliseconds

    def start(self):
        if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
            QtGui.QApplication.instance().exec_()

    def update(self):
        self.skelScatterItem.setData(pos=self.skel_fr_mar_dim[self.currentFrameNumber,:,:])
        self.currentFrameNumber += 1
        if self.currentFrameNumber >= self.skel_fr_mar_dim.shape[0]:
            self.currentFrameNumber = 0

    def animate(self):
        timer = QtCore.QTimer()
        timer.timeout.connect(self.update)
        timer.start(self.frameDuration)
        self.start()




























































# def PlaySkeleton( session,
#                     vidType=1,
#                     startFrame=40,
#                     azimuth=-90,
#                     elevation=-80,
#                     useOpenPose=True,
#                     useMediaPipe=False,
#                     useDLC=False):

    
#     mean_charuco_mar_dim = np.load(session.dataArrayPath/'charuco_points.npy')
    
#     # mean_charuco_mar_dim[:,0] -=mean_charuco_mar_dim[0,0]
#     # mean_charuco_mar_dim[:,1] -=mean_charuco_mar_dim[0,1]
#     # mean_charuco_mar_dim[:,2] -=mean_charuco_mar_dim[0,2]

#     global skel_fr_mar_dim, frameNum, dlc_fr_mar_dim, head, spine, rArm, lArm, rLeg, lLeg, rFoot, lFoot

#     for ii in range(20):
#         print('JON IS USING GLOBAL VARIABLES IN THE PYQTGRAPH PLOT FUNCTIONS IN A VERY IRRESPONSIBLE WAY. SHAME BE UPON HIM')
    
#     if useOpenPose:
        
#         skel_fr_mar_dim = np.load(session.dataArrayPath/'openPoseSkel_3d.npy')

#     if useMediaPipe:
#         mediaPipe_skel_fr_mar_dim = np.load(session.dataArrayPath/'mediaPipeSkel_3d.npy')
        
#     if useDLC:
#         dlc_fr_mar_dim = np.load(session.dataArrayPath/'deepLabCut_3d.npy')
#         dlc0 = np.squeeze(dlc_fr_mar_dim[:,0,:])
#         dlc1 = np.squeeze(dlc_fr_mar_dim[:,1,:])
#         dlc2 = np.squeeze(dlc_fr_mar_dim[:,2,:])
#         ballTrailLen = 4

    
#     if useOpenPose:
#         imgPathList = session.config_settings['openPose_imgPathList']
#         session.numCams = len(session.openPose_imgPathList)
    
#     camImgPathList = {}
#     for cam in range(session.numCams):
#         camImgPathList[cam] = list(sorted(Path(imgPathList[cam]).glob('*.png')))
#         session.numFrames = len(camImgPathList[cam]) #will need to perhaps put a check in on whether numFrames between cameras are the same
    

# # define Skeleton connections 
#     head = [17, 15, 0, 16, 18]
#     # head = [ 15, 0, 16]
#     spine = [0,1,8]
#     rArm = [17, 15, 0, 16, 18]
#     rArm = [4 ,3 ,2 ,1]
#     lArm = [1, 5, 6, 7]
#     rLeg = [11 ,10, 9, 8]
#     lLeg = [14 ,13 ,12, 8]
#     rFoot = [11, 23,22, 11, 24]
#     lFoot = [14, 20, 19, 14, 21]

#     #Make some handy maps ;D
#     rHandIDstart = 25 
#     lHandIDstart = rHandIDstart+21

#     thumb = np.array([0,1,2,3,4])
#     index = np.array([0, 5,6,7,8])
#     bird = np.array([0, 9,10,11,12])
#     ring = np.array([0, 13,14,15,16])
#     pinky = np.array([0, 17,18,19,20])

#     #This is mostly cribbed from the '3d Graphics:Scatter Plot' example from `python -m pyqtgraph.examples`
#     app = pg.mkQApp("GLScatterPlotItem Example")
#     QtWindow = gl.GLViewWidget()
#     QtWindow.opts['distance'] = 2000
#     QtWindow.show()
#     QtWindow.setWindowTitle('pyqtgraph example: GLScatterPlotItem')

#     # g = gl.GLGridItem()
#     # g.setSize(x=1e3, y=1e3, z=1)
#     # g.setSpacing(x=100, y=100)
#     # QtWindow.addItem(g)

#     charucoScatterItem = gl.GLScatterPlotItem(pos=mean_charuco_mar_dim, color=(1,1,1,.8), size=10, pxMode=False)
#     QtWindow.addItem(charucoScatterItem)

#     skelScatterItem = gl.GLScatterPlotItem(pos=skel_fr_mar_dim, color=(1,0,1,.8), size=10, pxMode=False)
#     QtWindow.addItem(skelScatterItem)
    
#     #make skeleton line plots
#     headLineItem = gl.GLLinePlotItem(pos=skel_fr_mar_dim[:,head,:],  color=(1,1,1,.5), width=2., antialias=True)
#     QtWindow.addItem(headLineItem)

#     spineLineItem = gl.GLLinePlotItem(pos=skel_fr_mar_dim[:,spine,:],  color=(1,1,1,.5), width=2., antialias=True)
#     QtWindow.addItem(spineLineItem)

#     rArmLineItem = gl.GLLinePlotItem(pos=skel_fr_mar_dim[:,rArm,:],  color=(1,0,0,.5), width=2., antialias=True)
#     QtWindow.addItem(rArmLineItem)

#     lArmLineItem = gl.GLLinePlotItem(pos=skel_fr_mar_dim[:,lArm,:],  color=(0,0,1,.5), width=2., antialias=True)
#     QtWindow.addItem(lArmLineItem)

#     rLegLineItem = gl.GLLinePlotItem(pos=skel_fr_mar_dim[:,rLeg,:],  color=(1,0,0,.5), width=2., antialias=True)
#     QtWindow.addItem(rLegLineItem)

#     lLegLineItem = gl.GLLinePlotItem(pos=skel_fr_mar_dim[:,lLeg,:],  color=(0,0,1,.5), width=2., antialias=True)
#     QtWindow.addItem(lLegLineItem)

#     rFootLineItem = gl.GLLinePlotItem(pos=skel_fr_mar_dim[:,rFoot,:],  color=(1,0,0,.5), width=2., antialias=True)
#     QtWindow.addItem(rFootLineItem)

#     lFootLineItem = gl.GLLinePlotItem(pos=skel_fr_mar_dim[:,lFoot,:],  color=(0,0,1,.5), width=2., antialias=True)
#     QtWindow.addItem(lFootLineItem)




#     dlcScatterItem = gl.GLScatterPlotItem(pos=dlc_fr_mar_dim, color=(1,0,0,.8), size=40, pxMode=False)
#     QtWindow.addItem(dlcScatterItem)

#     dlc0LineItem = gl.GLLinePlotItem(pos=dlc_fr_mar_dim[:,0,:],  color=(0,1,1,.5), width=4., antialias=True)
#     dlc1LineItem = gl.GLLinePlotItem(pos=dlc_fr_mar_dim[:,1,:],  color=(1,0,1,.5), width=4., antialias=True)
#     dlc2LineItem = gl.GLLinePlotItem(pos=dlc_fr_mar_dim[:,2,:],  color=(1,1,0,.5), width=4., antialias=True)
    
#     QtWindow.addItem(dlc0LineItem)
#     QtWindow.addItem(dlc1LineItem)
#     QtWindow.addItem(dlc2LineItem)


#     frameNum = 0
#     numFrames = skel_fr_mar_dim.shape[0]
#     def update():
#         #iterate through frames
#         global frameNum, skel_fr_mar_dim, head, spine, rArm, lArm, rLeg, lLeg, rFoot, lFoot
#         skelScatterItem.setData(pos=skel_fr_mar_dim[frameNum,:,:])
        
#         headLineItem.setData(pos=skel_fr_mar_dim[frameNum,head,:])
#         spineLineItem.setData(pos=skel_fr_mar_dim[frameNum,spine,:])
#         rArmLineItem.setData(pos=skel_fr_mar_dim[frameNum,rArm,:])
#         lArmLineItem.setData(pos=skel_fr_mar_dim[frameNum,lArm,:])
#         rLegLineItem.setData(pos=skel_fr_mar_dim[frameNum,rLeg,:])
#         lLegLineItem.setData(pos=skel_fr_mar_dim[frameNum,lLeg,:])
#         rFootLineItem.setData(pos=skel_fr_mar_dim[frameNum,rFoot,:])
#         lFootLineItem.setData(pos=skel_fr_mar_dim[frameNum,lFoot,:])

#         dlcScatterItem.setData(pos=dlc_fr_mar_dim[frameNum,:,:])

#         tailLength = 10
#         if frameNum > tailLength:
#             tailIndexes = range(frameNum-tailLength, frameNum)
#         else:
#             tailIndexes = range(frameNum)
#         dlc0LineItem.setData(pos=dlc_fr_mar_dim[tailIndexes,0,:])
#         dlc1LineItem.setData(pos=dlc_fr_mar_dim[tailIndexes,1,:])
#         dlc2LineItem.setData(pos=dlc_fr_mar_dim[tailIndexes,2,:])

#         frameNum+=1
#         if frameNum >= numFrames:
#             frameNum = 0

#     t = QtCore.QTimer()
#     t.timeout.connect(update)
#     t.start(25)
#     pg.mkQApp().exec_()
#     f=9

    