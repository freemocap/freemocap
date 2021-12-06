# -*- coding: utf-8 -*-
"""
Demonstrates use of GLScatterPlotItem with rapidly-updating plots.

"""

import pyqtgraph as pg
from pyqtgraph import functions as fn
from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph.opengl as gl
import numpy as np

app = pg.mkQApp("GLScatterPlotItem Example")
w = gl.GLViewWidget()
w.show()
w.setWindowTitle('pyqtgraph example: GLScatterPlotItem')
w.setCameraPosition(distance=20)

g = gl.GLGridItem()
w.addItem(g)

phase = 0.
##
##  Third example shows a grid of points with rapidly updating position
##  and pxMode = False
##

pos3 = np.zeros((100,100,3))
pos3[:,:,:2] = np.mgrid[:100, :100].transpose(1,2,0) * [-0.1,0.1]
pos3 = pos3.reshape(10000,3)
d3 = (pos3**2).sum(axis=1)**0.5

sp3 = gl.GLScatterPlotItem(pos=pos3, color=(1,1,1,.3), size=0.1, pxMode=False)

w.addItem(sp3)


def update():
    ## update volume colors
    global phase
    phase -= 0.1
    
    ## update surface positions and colors
    global sp3, d3, pos3
    z = -np.cos(d3*2+phase)
    pos3[:,2] = z
    color = np.zeros((len(d3),4), dtype=np.float32)
    color[:,3] = .3
    color[:,0] = pos3[:,2]
    color[:,1] = .5
    # color[:,2] = pos3[:,2]
    sp3.setData(pos=pos3, color=color)
    
t = QtCore.QTimer()
t.timeout.connect(update)
t.start(50)

if __name__ == '__main__':
    pg.exec()
