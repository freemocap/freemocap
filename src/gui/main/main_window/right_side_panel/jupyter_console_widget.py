"""
This example show how to create a Rich Jupyter Widget, and places it in a MainWindow alongside a PlotWidget.

The widgets are implemented as `Docks` so they may be moved around within the Main Window

The `__main__` function shows an example that inputs the commands to plot simple `sine` and cosine` waves, equivalent to creating such plots by entering the commands manually in the console

Also shows the use of `whos`, which returns a list of the variables defined within the `ipython` kernel

This method for creating a Jupyter console is based on the example(s) here:
https://github.com/jupyter/qtconsole/tree/b4e08f763ef1334d3560d8dac1d7f9095859545a/examples
especially-
https://github.com/jupyter/qtconsole/blob/b4e08f763ef1334d3560d8dac1d7f9095859545a/examples/embed_qtconsole.py#L19

"""


import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets
from pyqtgraph.dockarea.Dock import Dock
from pyqtgraph.dockarea.DockArea import DockArea


from qtconsole import inprocess


class JupyterConsoleWidget(inprocess.QtInProcessRichJupyterWidget):
    def __init__(self, dark_mode: bool = True):
        super().__init__()
        self.kernel_manager = inprocess.QtInProcessKernelManager()
        self.kernel_manager.start_kernel()
        self.kernel_client = self.kernel_manager.client()
        self._kernel = self.kernel_manager.kernel
        self._kernel.shell.push(dict(np=np))
        self.kernel_client.start_channels()
        # self._kernel.iopub_socket.send(str('gehehehehe'))
        self._import_stuff()
        self.execute("%whos", hidden=True)

        if dark_mode:
            self.set_default_style("linux")

    def _import_stuff(self):
        self.execute("import matplotlib.pyplot as plt")

    def print(self, message: str):
        self.execute(f"print('{message}')")

    def shutdown_kernel(self):
        self.kernel_client.stop_channels()
        self.kernel_manager.shutdown_kernel()
