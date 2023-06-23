
from PyQt6.QtWidgets import QWidget,QVBoxLayout

import matplotlib
matplotlib.use('QtAgg')

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from freemocap_utils.postprocessing_widgets.visualization_widgets.mediapipe_skeleton_builder import mediapipe_indices

import numpy as np


class TimeSeriesPlotCanvas(FigureCanvasQTAgg):

    def __init__(self, parent=None, width=15, height=4, dpi=100):
        fig = Figure(figsize=(width, height * 0.7), dpi=dpi)
        self.x_ax = fig.add_subplot(311)
        self.y_ax = fig.add_subplot(312)
        self.z_ax = fig.add_subplot(313)

        fig.subplots_adjust(hspace=0.4)
        fig.tight_layout(pad=2.5)

        super(TimeSeriesPlotCanvas, self).__init__(fig)

class TimeSeriesPlotterWidget(QWidget):

    def __init__(self):
        super().__init__()

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self.lines = []


        self.fig, self.axes_list = self.initialize_skeleton_plot()

        toolbar = NavigationToolbar(self.fig, self)
        self._layout.addWidget(toolbar)
        self._layout.addWidget(self.fig)

    def initialize_skeleton_plot(self):
        fig = TimeSeriesPlotCanvas(self, width=12, height=9, dpi=100)
        self.x_ax = fig.figure.axes[0]
        self.y_ax = fig.figure.axes[1]
        self.z_ax = fig.figure.axes[2]

        self.axes_list = [self.x_ax,self.y_ax,self.z_ax]
        return fig, self.axes_list

    def get_mediapipe_indices(self,marker_to_plot):
        mediapipe_index = mediapipe_indices.index(marker_to_plot)
        return mediapipe_index
    

    def update_plot(self,marker_to_plot:str, original_freemocap_data:np.ndarray, processed_freemocap_data:np.ndarray, reset_axes = True):
        axes_names = ['X Axis (mm)', 'Y Axis (mm)', 'Z Axis (mm)']

        mediapipe_index = self.get_mediapipe_indices(marker_to_plot)

        for line in self.lines:
            line.remove()
        self.lines = []

        for dimension, (ax, ax_name) in enumerate(zip(self.axes_list, axes_names)):
            if reset_axes:
                ax.cla()

            line1, = ax.plot(original_freemocap_data[:, mediapipe_index, dimension], label='Original Data', alpha=.8, color='red')
            self.lines.append(line1)
            if processed_freemocap_data is not None:
                line2, = ax.plot(processed_freemocap_data[:, mediapipe_index, dimension], label='Processed Data', alpha=.6, color='blue')
                self.lines.append(line2)

            ax.set_ylabel(ax_name)

            if dimension == 2:  # put the xlabel only on the last plot
                ax.set_xlabel('Frame #')
            ax.legend()
        
        self.fig.figure.suptitle(f'{marker_to_plot} trajectory')

        self.fig.figure.canvas.draw_idle()



