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

try:
    from qtconsole import inprocess
except:
    print(
        "The example in `jupyter_console_example.py` requires `qtconsole` to calculate_center_of_mass. Install with `pip install qtconsole` or equivalent."
    )


class JupyterConsoleWidget(inprocess.QtInProcessRichJupyterWidget):
    def __init__(self, dark_mode: bool = True):
        super().__init__()

        self.kernel_manager = inprocess.QtInProcessKernelManager()
        self.kernel_manager.start_kernel()
        self.kernel_client = self.kernel_manager.client()
        self.kernel_client.start_channels()
        self._import_stuff()
        self.execute("%whos")
        if dark_mode:
            self.set_default_style("linux")

    def _import_stuff(self):
        self.execute("import numpy as np")
        self.execute("import matplotlib.pyplot as plt")

    def print(self, message: str):
        self.execute(f"print('{message}')")

    def shutdown_kernel(self):
        self.kernel_client.stop_channels()
        self.kernel_manager.shutdown_kernel()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, dark_mode=True):
        super().__init__()
        central_dock_area = DockArea()

        # create plot widget (and  dock)
        self.plot_widget = pg.PlotWidget()
        plot_dock = Dock(name="Plot Widget Dock", closable=True)
        plot_dock.addWidget(self.plot_widget)
        central_dock_area.addDock(plot_dock)

        # create jupyter console widget (and  dock)
        self.jupyter_console_widget = JupyterConsoleWidget()
        jupyter_console_dock = Dock("Jupyter Console Dock")
        jupyter_console_dock.addWidget(self.jupyter_console_widget)
        central_dock_area.addDock(jupyter_console_dock)
        self.setCentralWidget(central_dock_area)

        app = QtWidgets.QApplication.instance()
        app.aboutToQuit.connect(self.jupyter_console_widget.shutdown_kernel)

        kernel = self.jupyter_console_widget.kernel_manager.kernel
        kernel.shell.push_variables(dict(np=np, pw=self.plot_widget))

        # set dark mode
        if dark_mode:
            # Set Dark bg color via this relatively roundabout method
            self.jupyter_console_widget.set_default_style("linux")


if __name__ == "__main__":
    pg.mkQApp()
    main = MainWindow(dark_mode=True)
    main.show()
    main.jupyter_console_widget.execute('print("hello world :D ")')

    # plot a sine/cosine waves by printing to console
    # this is equivalent to typing the commands into the console manually
    main.jupyter_console_widget.execute("x = np.arange(0, 3 * np.pi, .1)")
    main.jupyter_console_widget.execute("pw.plotItem.plot(np.sin(x), pen='r')")
    main.jupyter_console_widget.execute(
        "pw.plotItem.plot(np.cos(x),\
         pen='cyan',\
         symbol='o',\
         symbolPen='m',\
         symbolBrush=(0,0,255))"
    )
    main.jupyter_console_widget.execute("whos")
    main.jupyter_console_widget.execute("")

    pg.exec()
