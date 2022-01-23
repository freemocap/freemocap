#jsm - 2021-Oct-23 - based on pyqtgrph.example VideoSpeedTest

# -*- coding: utf-8 -*-
"""
Tests the speed of image updates for an ImageItem and RawImageWidget.
The speed will generally depend on the type of data being shown, whether
it is being scaled and/or converted by lookup table, and whether OpenGL
is used by the view widget
"""


import argparse
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
    import cupy as cp
    pg.setConfigOption("useCupy", True)
    _has_cupy = True
except ImportError:
    cp = None
    _has_cupy = False

try:
    import numba
    _has_numba = True
except ImportError:
    numba = None
    _has_numba = False

try:
    from pyqtgraph.widgets.RawImageWidget import RawImageGLWidget
except ImportError:
    RawImageGLWidget = None

parser = argparse.ArgumentParser(description="Benchmark for testing video performance")
parser.add_argument('--cuda', default=False, action='store_true', help="Use CUDA to process on the GPU", dest="cuda")
parser.add_argument('--dtype', default='uint8', choices=['uint8', 'uint16', 'float'], help="Image dtype (uint8, uint16, or float)")
parser.add_argument('--frames', default=3, type=int, help="Number of image frames to generate (default=3)")
parser.add_argument('--image-mode', default='mono', choices=['mono', 'rgb'], help="Image data mode (mono or rgb)", dest='image_mode')
parser.add_argument('--levels', default=None, type=lambda s: tuple([float(x) for x in s.split(',')]), help="min,max levels to scale monochromatic image dynamic range, or rmin,rmax,gmin,gmax,bmin,bmax to scale rgb")
parser.add_argument('--lut', default=False, action='store_true', help="Use color lookup table")
parser.add_argument('--lut-alpha', default=False, action='store_true', help="Use alpha color lookup table", dest='lut_alpha')
parser.add_argument('--size', default='512x512', type=lambda s: tuple([int(x) for x in s.split('x')]), help="WxH image dimensions default='512x512'")
args = parser.parse_args(sys.argv[1:])

if RawImageGLWidget is not None:
    # don't limit frame rate to vsync
    sfmt = QtGui.QSurfaceFormat()
    sfmt.setSwapInterval(0)
    QtGui.QSurfaceFormat.setDefaultFormat(sfmt)

app = pg.mkQApp("Video Speed Test Example")

win = QtGui.QMainWindow()
win.setWindowTitle('pyqtgraph example: VideoSpeedTest')
ui = ui_template.Ui_MainWindow()
ui.setupUi(win)
win.show()

if RawImageGLWidget is None:
    ui.rawGLRadio.setEnabled(False)
    ui.rawGLRadio.setText(ui.rawGLRadio.text() + " (OpenGL not available)")
else:
    ui.rawGLImg = RawImageGLWidget()
    ui.stack.addWidget(ui.rawGLImg)

# read in CLI args
ui.cudaCheck.setChecked(args.cuda and _has_cupy)
ui.cudaCheck.setEnabled(_has_cupy)
ui.numbaCheck.setChecked(_has_numba and pg.getConfigOption("useNumba"))
ui.numbaCheck.setEnabled(_has_numba)
ui.framesSpin.setValue(args.frames)
ui.widthSpin.setValue(args.size[0])
ui.heightSpin.setValue(args.size[1])
ui.dtypeCombo.setCurrentText(args.dtype)
ui.rgbCheck.setChecked(args.image_mode=='rgb')
ui.maxSpin1.setOpts(value=255, step=1)
ui.minSpin1.setOpts(value=0, step=1)
levelSpins = [ui.minSpin1, ui.maxSpin1, ui.minSpin2, ui.maxSpin2, ui.minSpin3, ui.maxSpin3]
if args.cuda and _has_cupy:
    xp = cp
else:
    xp = np
if args.levels is None:
    ui.scaleCheck.setChecked(False)
    ui.rgbLevelsCheck.setChecked(False)
else:
    ui.scaleCheck.setChecked(True)
    if len(args.levels) == 2:
        ui.rgbLevelsCheck.setChecked(False)
        ui.minSpin1.setValue(args.levels[0])
        ui.maxSpin1.setValue(args.levels[1])
    elif len(args.levels) == 6:
        ui.rgbLevelsCheck.setChecked(True)
        for spin,val in zip(levelSpins, args.levels):
            spin.setValue(val)
    else:
        raise ValueError("levels argument must be 2 or 6 comma-separated values (got %r)" % (args.levels,))
ui.lutCheck.setChecked(args.lut)
ui.alphaCheck.setChecked(args.lut_alpha)


#ui.graphicsView.useOpenGL()  ## buggy, but you can try it if you need extra speed.

vb = pg.ViewBox()
ui.graphicsView.setCentralItem(vb)
vb.setAspectLocked()
pg_img = pg.ImageItem()
vb.addItem(pg_img)


cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
success, image = cap.read()
assert success, 'Camera Failed to load image'
vidWidth, vidHeight, vidNumColorChannels = image.shape




LUT = None
def updateLUT():
    global LUT, ui
    dtype = ui.dtypeCombo.currentText()
    if dtype == 'uint8':
        n = 256
    else:
        n = 4096
    LUT = ui.gradient.getLookupTable(n, alpha=ui.alphaCheck.isChecked())
    if _has_cupy and xp == cp:
        LUT = cp.asarray(LUT)
ui.gradient.sigGradientChanged.connect(updateLUT)
updateLUT()

ui.alphaCheck.toggled.connect(updateLUT)

def updateScale():
    global ui, levelSpins
    if ui.rgbLevelsCheck.isChecked():
        for s in levelSpins[2:]:
            s.setEnabled(True)
    else:
        for s in levelSpins[2:]:
            s.setEnabled(False)

updateScale()

ui.rgbLevelsCheck.toggled.connect(updateScale)

cache = {}
def mkData():
    with pg.BusyCursor():
        global data, cache, ui, xp
        frames = ui.framesSpin.value()
        width = ui.widthSpin.value()
        height = ui.heightSpin.value()
        cacheKey = (ui.dtypeCombo.currentText(), ui.rgbCheck.isChecked(), frames, width, height)
        if cacheKey not in cache:
            if cacheKey[0] == 'uint8':
                dt = xp.uint8
                loc = 128
                scale = 64
                mx = 255
            elif cacheKey[0] == 'uint16':
                dt = xp.uint16
                loc = 4096
                scale = 1024
                mx = 2**16 - 1
            elif cacheKey[0] == 'float':
                dt = xp.float32
                loc = 1.0
                scale = 0.1
                mx = 1.0
            else:
                raise ValueError(f"unable to handle dtype: {cacheKey[0]}")

            chan_shape = (height, width)
            if ui.rgbCheck.isChecked():
                frame_shape = chan_shape + (3,)
            else:
                frame_shape = chan_shape
            data = xp.empty((frames,) + frame_shape, dtype=dt)
            view = data.reshape((-1,) + chan_shape)
            for idx in range(view.shape[0]):
                subdata = xp.random.normal(loc=loc, scale=scale, size=chan_shape)
                # note: gaussian filtering has been removed as it slows down array
                #       creation greatly.
                if cacheKey[0] != 'float':
                    xp.clip(subdata, 0, mx, out=subdata)
                view[idx] = subdata

            data[:, 10:50, 10] = mx
            data[:, 48, 9:12] = mx
            data[:, 47, 8:13] = mx
            cache = {cacheKey: data} # clear to save memory (but keep one to prevent unnecessary regeneration)

        data = cache[cacheKey]
        updateLUT()
        updateSize()

def updateSize():
    global ui, vb
    frames = ui.framesSpin.value()
    width = ui.widthSpin.value()
    height = ui.heightSpin.value()
    dtype = xp.dtype(str(ui.dtypeCombo.currentText()))
    rgb = 3 if ui.rgbCheck.isChecked() else 1
    ui.sizeLabel.setText('%d MB' % (frames * width * height * rgb * dtype.itemsize / 1e6))
    vb.setRange(QtCore.QRectF(0, 0, width, height))


def noticeCudaCheck():
    global xp, cache
    cache = {}
    if ui.cudaCheck.isChecked():
        if _has_cupy:
            xp = cp
        else:
            xp = np
            ui.cudaCheck.setChecked(False)
    else:
        xp = np
    mkData()


def noticeNumbaCheck():
    pg.setConfigOption('useNumba', _has_numba and ui.numbaCheck.isChecked())


mkData()


ui.dtypeCombo.currentIndexChanged.connect(mkData)
ui.rgbCheck.toggled.connect(mkData)
ui.widthSpin.editingFinished.connect(mkData)
ui.heightSpin.editingFinished.connect(mkData)
ui.framesSpin.editingFinished.connect(mkData)

ui.widthSpin.valueChanged.connect(updateSize)
ui.heightSpin.valueChanged.connect(updateSize)
ui.framesSpin.valueChanged.connect(updateSize)
ui.cudaCheck.toggled.connect(noticeCudaCheck)
ui.numbaCheck.toggled.connect(noticeNumbaCheck)


ptr = 0
lastTime = perf_counter()
fps = None
def update():
    global ui, ptr, lastTime, fps, LUT, pg_img
    if ui.lutCheck.isChecked():
        useLut = LUT
    else:
        useLut = None

    downsample = ui.downsampleCheck.isChecked()

    if ui.scaleCheck.isChecked():
        if ui.rgbLevelsCheck.isChecked():
            useScale = [
                [ui.minSpin1.value(), ui.maxSpin1.value()],
                [ui.minSpin2.value(), ui.maxSpin2.value()],
                [ui.minSpin3.value(), ui.maxSpin3.value()]]
        else:
            useScale = [ui.minSpin1.value(), ui.maxSpin1.value()]
    else:
        useScale = None

    #read image from camera
    success, image = cap.read()
    assert success, 'Camera Failed to load image'
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB) #convert image from BGR to RGB color format
    
    if ui.rawRadio.isChecked():
        ui.rawImg.setImage(image, lut=useLut, levels=useScale)
        ui.stack.setCurrentIndex(1)
    elif ui.rawGLRadio.isChecked():
        ui.rawGLImg.setImage(image, lut=useLut, levels=useScale)
        ui.stack.setCurrentIndex(2)
    else:
        pg_img.setImage(cv2.rotate(image, cv2.ROTATE_180), autoLevels=False, levels=useScale, lut=useLut, autoDownsample=downsample)
        ui.stack.setCurrentIndex(0)
        #img.setImage(data[ptr%data.shape[0]], autoRange=False)

    ptr += 1
    now = perf_counter()
    dt = now - lastTime
    lastTime = now
    if fps is None:
        fps = 1.0/dt
    else:
        s = np.clip(dt*3., 0, 1)
        fps = fps * (1-s) + (1.0/dt) * s
    ui.fpsLabel.setText('%0.2f fps' % fps)
    app.processEvents()  ## force complete redraw for every plot
timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(0)

if __name__ == '__main__':
    pg.exec()
