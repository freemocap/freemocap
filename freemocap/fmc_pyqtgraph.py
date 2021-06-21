from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph.opengl as gl
import pyqtgraph as pg
import pyqtgraph.console
from pyqtgraph.dockarea import Dock, DockArea
import cv2 

import numpy as np
from pathlib import Path
import sys


class PlaySkeletonWidget():
    def __init__(self, session):

        #set up PyQT widget (the window that pops up and shows the plots, I think ? cribbed from - https://gist.github.com/markjay4k/da2f55e28514be7160a7c5fbf95bd243)
        # self.app = QtGui.QApplication(sys.argv)
        self.Skel3dViewWidget = gl.GLViewWidget()
        self.Skel3dViewWidget.opts['distance'] = 2000
        self.Skel3dViewWidget.setWindowTitle('SessionID: {}'.format(session.sessionID))
        self.Skel3dViewWidget.setGeometry(0, 110, 1920, 1080)
        self.Skel3dViewWidget.show()


        #load data to be plotted
        self.useOpenPose = session.useOpenPose
        if self.useOpenPose:
            self.skel_fr_mar_dim  = np.load(session.dataArrayPath/'openPoseSkel_3d.npy')
            self.skelScatterItem = gl.GLScatterPlotItem(pos=self.skel_fr_mar_dim, color=(1,0,1,.8), size=10, pxMode=False)

            
            self.Skel3dViewWidget.addItem(self.skelScatterItem)


            #make skeleton line plots (numbers specify what order to connects the dots)
            self.head = [17, 15, 0, 1, 0, 16, 18]
            self.spine = [1,8]
            self.rArm = [17, 15, 0, 16, 18]
            self.rArm = [4 ,3 ,2 ,1]
            self.lArm = [1, 5, 6, 7]
            self.rLeg = [11 ,10, 9, 8]
            self.lLeg = [14 ,13 ,12, 8]
            self.rFoot = [11, 23,22, 11, 24]
            self.lFoot = [14, 20, 19, 14, 21]

            #Make some handy maps ;D
            rHandIDstart = 25 
            lHandIDstart = rHandIDstart+21

            self.rHand = np.array([0, 1, 2, 3, 4, False, 0, 5, 6, 7, 8, False, 0, 9, 10, 11, 12, False, 0, 13, 14, 15, 16, False, 0, 17, 18, 19, 20,]) + rHandIDstart
            self.lHand =  self.rHand + lHandIDstart


            self.headLineItem = gl.GLLinePlotItem(pos=self.skel_fr_mar_dim[:,self.head,:],  color=(1,1,1,.2), width=4., antialias=True)
            self.Skel3dViewWidget.addItem(self.headLineItem)

            self.spineLineItem = gl.GLLinePlotItem(pos=self.skel_fr_mar_dim[:,self.spine,:],  color=(1,1,1,.9), width=4., antialias=True)
            self.Skel3dViewWidget.addItem(self.spineLineItem)

            self.rArmLineItem = gl.GLLinePlotItem(pos=self.skel_fr_mar_dim[:,self.rArm,:],  color=(1,.2,.15,.9), width=4., antialias=True)
            self.Skel3dViewWidget.addItem(self.rArmLineItem)

            self.lArmLineItem = gl.GLLinePlotItem(pos=self.skel_fr_mar_dim[:,self.lArm,:],  color=(.4,.6,1,.9), width=4., antialias=True)
            self.Skel3dViewWidget.addItem(self.lArmLineItem)

            self.rLegLineItem = gl.GLLinePlotItem(pos=self.skel_fr_mar_dim[:,self.rLeg,:],  color=(1,.2,.15,.9), width=4., antialias=True)
            self.Skel3dViewWidget.addItem(self.rLegLineItem)

            self.lLegLineItem = gl.GLLinePlotItem(pos=self.skel_fr_mar_dim[:,self.lLeg,:],  color=(.4,.6,1,.9), width=4., antialias=True)
            self.Skel3dViewWidget.addItem(self.lLegLineItem)

            self.rFootLineItem = gl.GLLinePlotItem(pos=self.skel_fr_mar_dim[:,self.rFoot,:],  color=(1,.2,.15,.9), width=4., antialias=True)
            self.Skel3dViewWidget.addItem(self.rFootLineItem)

            self.lFootLineItem = gl.GLLinePlotItem(pos=self.skel_fr_mar_dim[:,self.lFoot,:],  color=(.4,.6,1,.9), width=4., antialias=True)
            self.Skel3dViewWidget.addItem(self.lFootLineItem)

            # plot handybois
            self.rHandLineItem = gl.GLLinePlotItem(pos=self.skel_fr_mar_dim[:,self.rHand,:],  color=(.2,.4,1,.9), width=1., antialias=True)
            # self.Skel3dViewWidget.addItem(self.rHandLineItem)
            
            self.lHandLineItem = gl.GLLinePlotItem(pos=self.skel_fr_mar_dim[:,self.lHand,:],  color=(1,.1,.05,.9), width=1., antialias=True)
            # self.Skel3dViewWidget.addItem(self.lHandLineItem)




        
        self.useDLC = session.useDLC
        if self.useDLC:
            # self.dlc_fr_mar_dim = np.load(session.dataArrayPath/'mediaPipeSkel_3d.npy')
            self.dlc_fr_mar_dim = np.load(session.dataArrayPath/'deepLabCut_3d.npy')
            self.dlcScatterItem = gl.GLScatterPlotItem(pos=self.dlc_fr_mar_dim, color=(1,0,0,.8), size=60, pxMode=False)
            self.Skel3dViewWidget.addItem(self.dlcScatterItem)
            
            self.dlc0LineItem = gl.GLLinePlotItem(pos=self.dlc_fr_mar_dim[:,0,:],  color=(0,1,1,.5), width=4., antialias=True)
            self.dlc1LineItem = gl.GLLinePlotItem(pos=self.dlc_fr_mar_dim[:,1,:],  color=(1,0,1,.5), width=4., antialias=True)
            self.dlc2LineItem = gl.GLLinePlotItem(pos=self.dlc_fr_mar_dim[:,2,:],  color=(1,1,0,.5), width=4., antialias=True)

            self.Skel3dViewWidget.addItem(self.dlc0LineItem)
            self.Skel3dViewWidget.addItem(self.dlc1LineItem)
            self.Skel3dViewWidget.addItem(self.dlc2LineItem)

            self.tailLength = 10
            
            


        self.charuco_mar_dim = np.load(session.dataArrayPath/'charuco_points.npy')
        self.charucoScatterItem = gl.GLScatterPlotItem(pos=self.charuco_mar_dim, color=(1,1,1,.8), size=10, pxMode=False)
        self.Skel3dViewWidget.addItem(self.charucoScatterItem)

        #plot videos Frames!

        #set frame counter
        self.currentFrameNumber = 0
        self.framerate = 50 #frames per second
        self.frameDuration = 1000/self.framerate #milliseconds

    # def start(self):
    #     if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
    #         QtGui.QApplication.instance().exec_()

    def update(self):

        #Plot Mr. Skreleton :D
        #Plots the dots 
        self.skelScatterItem.setData(pos=self.skel_fr_mar_dim[self.currentFrameNumber,:,:]) 
        
        #connect the dottos
        self.headLineItem.setData(pos=self.skel_fr_mar_dim[self.currentFrameNumber, self.head,:])
        self.spineLineItem.setData(pos=self.skel_fr_mar_dim[self.currentFrameNumber, self.spine,:])
        self.rArmLineItem.setData(pos=self.skel_fr_mar_dim[self.currentFrameNumber, self.rArm,:])
        self.lArmLineItem.setData(pos=self.skel_fr_mar_dim[self.currentFrameNumber, self.lArm,:])
        self.rLegLineItem.setData(pos=self.skel_fr_mar_dim[self.currentFrameNumber, self.rLeg,:])
        self.lLegLineItem.setData(pos=self.skel_fr_mar_dim[self.currentFrameNumber, self.lLeg,:])
        self.rFootLineItem.setData(pos=self.skel_fr_mar_dim[self.currentFrameNumber, self.rFoot,:])
        self.lFootLineItem.setData(pos=self.skel_fr_mar_dim[self.currentFrameNumber, self.lFoot,:])

        self.rHandLineItem.setData(pos=self.skel_fr_mar_dim[self.currentFrameNumber, self.rHand,:])
        self.lHandLineItem.setData(pos=self.skel_fr_mar_dim[self.currentFrameNumber, self.lHand,:])

        if self.useDLC:
            #Plot DeepLabCut data
            self.dlcScatterItem.setData(pos=self.dlc_fr_mar_dim[self.currentFrameNumber,:,:])
            
            if self.currentFrameNumber > self.tailLength:
                self.tailIndexes = range(self.currentFrameNumber-self.tailLength , self.currentFrameNumber)
                self.dlc0LineItem.setData(pos=self.dlc_fr_mar_dim[self.tailIndexes,0,:])
                self.dlc1LineItem.setData(pos=self.dlc_fr_mar_dim[self.tailIndexes,1,:])
                self.dlc2LineItem.setData(pos=self.dlc_fr_mar_dim[self.tailIndexes,2,:])


        self.currentFrameNumber += 1
        if self.currentFrameNumber >= self.skel_fr_mar_dim.shape[0]:
            self.currentFrameNumber = 0

    def animate(self):
        timer = QtCore.QTimer()
        timer.timeout.connect(self.update)
        # timer.start(self.frameDuration)
        timer.start(0)
        # self.start()


class VideoWindowWidget:
    def __init__(self, vidNum, videoPath, session):
        #set up video capture
        self.vidCap = cv2.VideoCapture(str(videoPath))
        success, image = self.vidCap.read()
        self.vidCap.set(cv2.CAP_PROP_POS_FRAMES, 0) #reset video capture so things start on the first frame
        
        self.videoWidget = pg.GraphicsLayoutWidget()
        self.videoWidget.show()  ## show widget alone in its own window
        self.videoWidget.setWindowTitle('Video Name')
        self.view = self.videoWidget.addViewBox()
        ## lock the aspect ratio so pixels are always square
        self.view.setAspectLocked(True)

        ## Create image item
        self.imgItem = pg.ImageItem(border='w')
        self.view.addItem(self.imgItem)

        ## Set initial view bounds
        self.view.setRange(QtCore.QRectF(0, 0, image.shape[0], image.shape[1]))


        #set image, I guess?
        self.imgItem.setImage(image)

    def update(self):
        success, image = self.vidCap.read()

        if success:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
            self.imgItem.setImage(image)
        else:
            self.vidCap.set(cv2.CAP_PROP_POS_FRAMES, 0) #reset video capture so video will loop
            success, image = self.vidCap.read()            
            self.imgItem.setImage(image)



class PlayerDockedWindow:
    def __init__(self, session,displayVid):

        
        app = pg.mkQApp("DockArea Example")
        self.displayVid = displayVid
        self.win = QtGui.QMainWindow()
        area = DockArea()
        self.win.setCentralWidget(area)
        winHeight = 1000
        winWidth = 1900
        self.win.resize(winHeight,winWidth)
        self.win.setWindowTitle('FreeMoCap')

        ## Create docks, place them into the window one at a time.
        ## Note that size arguments are only a suggestion; docks will still have to
        ## fill the entire dock area and obey the limits of their internal widgets.

        self.VidPathList = []
        self.dock_name_dictionary = {}

        if displayVid == 0:
            path_to_search = session.syncedVidPath
        elif displayVid == 1:
            path_to_search = session.openPoseDataPath
        for count,vidPath in enumerate(path_to_search.glob('*.mp4')):
            self.VidPathList.append(vidPath)
            #dock_name = 'dock_video{}'.format(count)

            dock_name = count
            self.dock_name_dictionary[dock_name] = None


        dock_3dView = Dock('Session: {}'.format(session.sessionID), size=(1, 1), closable=True)     ## give this dock the minimum possible size
        dock_Console = Dock("Dock2 - Console", size=(winHeight,winWidth), closable=True)
        
        for key in self.dock_name_dictionary:
            self.dock_name_dictionary[key] = Dock(str(key), size=(1,1), closable=True)
        #dock_video0 = Dock("Video0", size=(1,1), closable=True)
        #dock_video1 = Dock("Video1", size=(1,1), closable=True)
        #dock_video2 = Dock("Video2", size=(1,1), closable=True)
        #dock_video3 = Dock("Video3", size=(1,1), closable=True)

        area.addDock(dock_3dView, 'left')      ## place d1 at left edge of dock area (it will fill the whole space since there are no other docks yet)
        direction_list = ['top','left','bottom','top']
        for key, value in self.dock_name_dictionary.items():
            if (key % 2) == 0:
                area.addDock(value,'right')
                previous_dock = value
            else:
                area.addDock(value,'bottom',previous_dock)
                #previous_dock = value
        
        #area.addDock(dock_video0, 'right')     ## place d2 at right edge of dock area
        #area.addDock(dock_video1, 'right', dock_video0)## place d3 at bottom edge of d1
        #area.addDock(dock_video2, 'bottom',dock_video0)     ## place d4 at right edge of dock area
        #area.addDock(dock_video3, 'left', dock_video2)  ## place d5 at left edge of d1
        #area.moveDock(dock_video1, 'right', dock_video0)

        ## Add widgets into each dock

        ## first dock gets save/restore buttons
        w1 = pg.LayoutWidget()
        label = QtGui.QLabel(""" -- DockArea Example -- 
        This window has 6 Dock widgets in it. Each dock can be dragged
        by its title bar to occupy a different space within the window 
        but note that one dock has its title bar hidden). Additionally,
        the borders between docks may be dragged to resize. Docks that are dragged on top
        of one another are stacked in a tabbed layout. Double-click a dock title
        bar to place it in its own window.
        """)

        w2 = pg.console.ConsoleWidget()
        dock_Console.addWidget(w2)

        self.playSkel = PlaySkeletonWidget(session)
        
        dock_3dView.addWidget(self.playSkel.Skel3dViewWidget)

        #self.VidPathList = []
        #for vidPath in session.syncedVidPath.glob('*.mp4'):
        #    self.VidPathList.append(vidPath)
        self.widget_list = []
        for key, dock_video in self.dock_name_dictionary.items():
            self.videoWidget = VideoWindowWidget(key,str(self.VidPathList[key]),session)
            self.widget_list.append(self.videoWidget)
            dock_video.addWidget(self.videoWidget.videoWidget)
        #self.video0Widget = VideoWindowWidget(0,str(self.VidPathList[0]), session)
        #dock_video0.addWidget(self.video0Widget.videoWidget )

        #self.video1Widget = VideoWindowWidget(1,str(self.VidPathList[1]),session)
        #dock_video1.addWidget(self.video1Widget.videoWidget )

        #self.video2Widget = VideoWindowWidget(2,str(self.VidPathList[2]), session)
        #dock_video2.addWidget(self.video2Widget.videoWidget )

        #self.video3Widget = VideoWindowWidget(3,str(self.VidPathList[3]),session)
        #dock_video3.addWidget(self.video3Widget.videoWidget )

        self.win.show()
    
    def update(self):
        self.playSkel.update()
        for widget in self.widget_list:
            widget.update()

        #self.video0Widget.update()
        #self.video1Widget.update()
        #self.video2Widget.update()
        #self.video3Widget.update()
        
    def animate(self):
        timer = QtCore.QTimer()
        timer.timeout.connect(self.update)
        timer.start(self.playSkel.frameDuration)
        self.start()

    def start(self):
        if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
                QtGui.QApplication.instance().exec_()

    