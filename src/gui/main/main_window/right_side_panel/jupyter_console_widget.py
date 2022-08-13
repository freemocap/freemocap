import numpy as np

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
