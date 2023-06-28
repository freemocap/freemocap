from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget,QVBoxLayout

import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

import numpy as np

from freemocap_utils.postprocessing_widgets.visualization_widgets.mediapipe_skeleton_builder import mediapipe_indices,mediapipe_connections,build_skeleton


class SkeletonViewWidget(QWidget):

    session_folder_loaded_signal = pyqtSignal()

    def __init__(self, plot_title:str):
        super().__init__()

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self.plot_title = plot_title
        self.fig,self.ax = self.initialize_skeleton_plot()
        self._layout.addWidget(self.fig)

        self.skeleton_loaded = False

        self.current_xlim = None
        self.current_ylim = None
        self.current_zlim = None


    def load_skeleton(self,skeleton_3d_data:np.ndarray):

        self.skeleton_3d_data = skeleton_3d_data
        self.mediapipe_skeleton = build_skeleton(self.skeleton_3d_data,mediapipe_indices,mediapipe_connections)
        self.reset_skeleton_3d_plot()

        self.skeleton_loaded = True

            
    def initialize_skeleton_plot(self):
        fig = Mpl3DPlotCanvas(self, width=5, height=4, dpi=100)
        ax = fig.figure.axes[0]

        ax.set_title(self.plot_title)
        return fig, ax

    def reset_skeleton_3d_plot(self):
        self.ax.cla()
        self.calculate_axes_means(self.skeleton_3d_data)
        self.skel_x,self.skel_y,self.skel_z = self.get_x_y_z_data(0)
        self.plot_skel(0,self.skel_x,self.skel_y,self.skel_z)


    def calculate_axes_means(self,skeleton_3d_data):
        self.mx_skel = np.nanmean(skeleton_3d_data[:,0:33,0])
        self.my_skel = np.nanmean(skeleton_3d_data[:,0:33,1])
        self.mz_skel = np.nanmean(skeleton_3d_data[:,0:33,2])
        self.skel_3d_range = 900

    def plot_skel(self,frame_number,skel_x,skel_y,skel_z):
        self.ax.scatter(skel_x,skel_y,skel_z)
        self.plot_skeleton_bones(frame_number)
        if self.current_xlim:
            self.ax.set_xlim([self.current_xlim[0],self.current_xlim[1]])
            self.ax.set_ylim([self.current_ylim[0],self.current_ylim[1]])
            self.ax.set_zlim([self.current_zlim[0],self.current_zlim[1]])
        else:
            self.ax.set_xlim([self.mx_skel-self.skel_3d_range, self.mx_skel+self.skel_3d_range])
            self.ax.set_ylim([self.my_skel-self.skel_3d_range, self.my_skel+self.skel_3d_range])
            self.ax.set_zlim([self.mz_skel-self.skel_3d_range, self.mz_skel+self.skel_3d_range])
        
        self.ax.set_title(self.plot_title)
        self.fig.figure.canvas.draw_idle()

    def plot_skeleton_bones(self,frame_number):
            this_frame_skeleton_data = self.mediapipe_skeleton[frame_number]
            for connection in this_frame_skeleton_data.keys():
                line_start_point = this_frame_skeleton_data[connection][0] 
                line_end_point = this_frame_skeleton_data[connection][1]
                
                bone_x,bone_y,bone_z = [line_start_point[0],line_end_point[0]],[line_start_point[1],line_end_point[1]],[line_start_point[2],line_end_point[2]] 

                self.ax.plot(bone_x,bone_y,bone_z)

    def get_x_y_z_data(self, frame_number:int):
        skel_x = self.skeleton_3d_data[frame_number,:,0]
        skel_y = self.skeleton_3d_data[frame_number,:,1]
        skel_z = self.skeleton_3d_data[frame_number,:,2]

        return skel_x,skel_y,skel_z

    def replot(self, frame_number:int):
        skel_x,skel_y,skel_z = self.get_x_y_z_data(frame_number)
        self.current_xlim = self.ax.get_xlim()
        self.current_ylim = self.ax.get_ylim()
        self.current_zlim = self.ax.get_zlim()
        self.ax.cla()
        self.plot_skel(frame_number,skel_x,skel_y,skel_z)
        #self.label.setText(str(frame_number))


class Mpl3DPlotCanvas(FigureCanvasQTAgg):

    def __init__(self, parent=None, width=4, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111,projection = '3d')
        super(Mpl3DPlotCanvas, self).__init__(fig)




