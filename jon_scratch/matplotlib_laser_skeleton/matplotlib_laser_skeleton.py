from pathlib import Path

import keyboard
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
from mediapipe.python.solutions import holistic as mp_holistic

matplotlib.use('qtagg')

mediapipe_body_pose_connections = [this_connection for this_connection in mp_holistic.POSE_CONNECTIONS]


class MatplotlibLaserSkeleton:
    def __init__(self, file_path):
        self.fig = None
        self.ax3d = None
        self.mediapipe_all_fr_mar_xyz = None
        self.file_path = Path(file_path)
        self.load_mediapipe_data()

    def load_mediapipe_data(self):
        mediapipe_data_path = self.file_path / 'DataArrays' / 'mediaPipeSkel_3d.npy'
        self.mediapipe_all_fr_mar_xyz = np.load(str(mediapipe_data_path))

    def play_laser_skeleton_animation(self, start_frame: int = 0, end_frame: int = None):
        if end_frame is None:
            end_frame = self.mediapipe_all_fr_mar_xyz.shape[0]

        self.create_figure()

        for frame_number in range(start_frame, end_frame):
            plt.cla()
            self.plot_mediapipe_skeleton(frame_number)
            plt.show()
            plt.pause(0.001)
            if keyboard.is_pressed('esc'):
                print('You Pressed Escape!')
                plt.close('all')
                break  # finishing the loop

    def create_figure(self):
        plt.ion()
        self.fig = plt.figure()
        self.ax3d = self.fig.add_subplot(111, projection='3d')
        self.set_axis_limits()

    def set_axis_limits(self):
        median_position = np.nanmedian(self.mediapipe_all_fr_mar_xyz, axis=0)
        median_position = np.nanmedian(median_position, axis=0)
        stddev_position = np.nanstd(median_position, axis=0)
        axis_range = 1000
        self.ax3d.set_xlim(median_position[0] - axis_range, median_position[0] + axis_range)
        self.ax3d.set_ylim(median_position[1] - axis_range, median_position[1] + axis_range)
        self.ax3d.set_zlim(median_position[2] - axis_range, median_position[2] + axis_range)

    def plot_mediapipe_skeleton(self, frame_number: int):
        print(f'Plotting frame {frame_number}')
        self.ax3d.plot(self.mediapipe_all_fr_mar_xyz[frame_number, :, 0],
                       self.mediapipe_all_fr_mar_xyz[frame_number, :, 1],
                       self.mediapipe_all_fr_mar_xyz[frame_number, :, 2],
                       color='k', marker='o', linestyle='none', markersize=1)


if __name__ == '__main__':
    session_path = Path('C:/Users/jonma/Dropbox/FreeMoCapProject/FreeMocap_Data/sesh_2022-02-15_11_54_28_pupil_maybe')
    matplotlib_laser_skeleton = MatplotlibLaserSkeleton(session_path)
    matplotlib_laser_skeleton.play_laser_skeleton_animation(start_frame=1000, end_frame=1200)
