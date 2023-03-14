
pyinstaller --name="FreeMoCap"  --windowed  --onefile  --hidden-import pyqtgraph.graphicsItems.ViewBox.axisCtrlTemplate_pyqt6  --hidden-import pyqtgraph.graphicsItems.PlotItem.plotConfigTemplate_pyqt6  --hidden-import pyqtgraph.imageview.ImageViewTemplate_pyqt6  .\freemocap\__main__.py
