#jsm - 2021-Oct-23 - based on pyqtgrph.example VideoSpeedTest (gutted to simplest form)

import sys

import numpy as np

import pyqtgraph as pg
from pyqtgraph.Qt import QtGui, QtCore, QT_LIB
from time import perf_counter

import cv2

pg.setConfigOption('imageAxisOrder', 'row-major')

import importlib
ui_template = importlib.import_module(f'VideoTemplate_{QT_LIB.lower()}')

try:
    from pyqtgraph.widgets.RawImageWidget import RawImageGLWidget
except ImportError:
    RawImageGLWidget = None



if RawImageGLWidget is not None:
    # don't limit frame rate to vsync
    sfmt = QtGui.QSurfaceFormat()
    sfmt.setSwapInterval(0)
    QtGui.QSurfaceFormat.setDefaultFormat(sfmt)

app = pg.mkQApp("Simple QT Webcam Viewer")

win = QtGui.QMainWindow()
win.setWindowTitle(' based on - pyqtgraph example: VideoSpeedTest')
ui = ui_template.Ui_MainWindow()
ui.setupUi(win)
win.show()

if RawImageGLWidget is None:
    ui.rawGLRadio.setEnabled(False)
    ui.rawGLRadio.setText(ui.rawGLRadio.text() + " (OpenGL not available)")
else:
    ui.rawGLImg = RawImageGLWidget()
    ui.stack.addWidget(ui.rawGLImg)

vb = pg.ViewBox()
ui.graphicsView.setCentralItem(vb)
vb.setAspectLocked()
pg_img = pg.ImageItem()
vb.addItem(pg_img)


cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

cap.set(cv2.CAP_PROP_EXPOSURE, -7)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G')) 

success, image = cap.read()
assert success, 'Camera Failed to load image'
vidWidth, vidHeight, vidNumColorChannels = image.shape



ptr = 0
lastTime = perf_counter()
fps = None
def update():
    global ui, lastTime, fps, pg_img
    
    #read image from camera
    success, image = cap.read()
    assert success, 'Camera Failed to load image'
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB) #convert image from BGR to RGB color format
    
    if ui.rawRadio.isChecked():
        ui.rawImg.setImage(image)
        ui.stack.setCurrentIndex(1)
    elif ui.rawGLRadio.isChecked():
        ui.rawGLImg.setImage(image)
        ui.stack.setCurrentIndex(2)
    else:
        pg_img.setImage(cv2.rotate(image, cv2.ROTATE_180))
        ui.stack.setCurrentIndex(0)
        

    now = perf_counter()
    dt = now - lastTime
    lastTime = now
    if fps is None:
        fps = 1.0/dt
    else:
        s = np.clip(dt*3., 0, 1)
        fps = fps * (1-s) + (1.0/dt) * s
    ui.fpsLabel.setText('%0.2f timestamp_manager' % fps)
    app.processEvents()  ## force complete redraw for every plot
timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(0)

if __name__ == '__main__':
    pg.exec()
