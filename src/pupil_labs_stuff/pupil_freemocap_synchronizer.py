import logging

import matplotlib
import numpy as np

from matplotlib import pyplot as plt

from src.pupil_labs_stuff.data_classes.freemocap_session_data_class import FreemocapSessionDataClass
from src.pupil_labs_stuff.data_classes.pupil_dataclass_and_handler import PupilLabsDataClass

matplotlib.use("qt5agg")
logger = logging.getLogger(__name__)


class PupilFreemocapSynchronizer:
    """
    synchronize pupil and freemocap timestamps, return synchronized session data (exactly the same number of synchronized frames in each data stream
    """

    def __init__(self, raw_session_data: FreemocapSessionDataClass):
        self.raw_session_data = raw_session_data
        self.synchronized_session_data: FreemocapSessionDataClass = None

    def synchronize(
        self,
        debug: bool = False,
        vor_frame_start: int = None,
        vor_frame_end: int = None,
    ):
        """
        align freemocap and pupil timestamps and clip the starts and ends of the various data traces so that everything covers the same timespacn
        """
        # find start and end frames shared by all datastreams
        freemocap_timestamps = self.raw_session_data.timestamps
        right_eye_timestamps = self.raw_session_data.right_eye_pupil_labs_data.timestamps
        left_eye_timestamps = self.raw_session_data.left_eye_pupil_labs_data.timestamps

        start_time_unix = np.max((freemocap_timestamps[0], right_eye_timestamps[0], left_eye_timestamps[0]))
        end_time_unix = np.min(
            (
                freemocap_timestamps[-1],
                right_eye_timestamps[-1],
                left_eye_timestamps[-1],
            )
        )

        # freemocap
        if any(freemocap_timestamps >= start_time_unix):
            freemocap_start_frame = np.where(freemocap_timestamps >= start_time_unix)[0][0]
        else:
            freemocap_start_frame = 0

        if any(freemocap_timestamps <= end_time_unix):
            freemocap_end_frame = np.where(freemocap_timestamps <= end_time_unix)[0][-1]
        else:
            freemocap_end_frame = len(freemocap_timestamps)

        # right eye
        if any(right_eye_timestamps >= start_time_unix):
            right_eye_start_frame = np.where(right_eye_timestamps >= start_time_unix)[0][0]
        else:
            right_eye_start_frame = 0

        if any(right_eye_timestamps <= end_time_unix):
            right_eye_end_frame = np.where(right_eye_timestamps <= end_time_unix)[0][-1]
        else:
            right_eye_end_frame = len(right_eye_timestamps)

        # left eye
        if any(left_eye_timestamps >= start_time_unix):
            left_eye_start_frame = np.where(left_eye_timestamps >= start_time_unix)[0][0]
        else:
            left_eye_start_frame = 0

        if any(left_eye_timestamps <= end_time_unix):
            left_eye_end_frame = np.where(left_eye_timestamps <= end_time_unix)[0][-1]
        else:
            left_eye_end_frame = len(left_eye_timestamps)

        self.right_eye_start_frame = right_eye_start_frame
        self.right_eye_end_frame = right_eye_end_frame
        self.left_eye_start_frame = left_eye_start_frame
        self.left_eye_end_frame = left_eye_end_frame

        # rebase time onto freemocap's framerate (b/c it's slower than pupil) <- sloppy, assumes mocap slower than eye tracker, which is untrue for, say, GoPros
        self.synchronized_timestamps = self.raw_session_data.timestamps[freemocap_start_frame:freemocap_end_frame]

        logger.warning(
            "SLOPPY ASSUMPTION: assuming freemocap framerate is always slower than eye tracker (true for webcams, not true for GoPros)"
        )

        self.clip_eye_data()
        self.resample_eye_data()
        # self.normalize_eye_data()

        self.synchronized_timestamps = self.synchronized_timestamps - self.synchronized_timestamps[0]

        assert self.synchronized_timestamps.shape[0] == self.right_eye_theta.shape[0]
        assert self.synchronized_timestamps.shape[0] == self.left_eye_theta.shape[0]

        if debug:
            self.show_debug_plots(vor_frame_start, vor_frame_end)

        synchronized_right_eye_data = PupilLabsDataClass(
            timestamps=self.synchronized_timestamps,
            theta=self.right_eye_theta,
            phi=self.right_eye_phi,
            pupil_center_normal_x=self.right_eye_pupil_center_normal_x,
            pupil_center_normal_y=self.right_eye_pupil_center_normal_y,
            pupil_center_normal_z=self.right_eye_pupil_center_normal_z,
            eye_d=0,
        )
        synchronized_left_eye_data = PupilLabsDataClass(
            timestamps=self.synchronized_timestamps,
            theta=self.left_eye_theta,
            phi=self.left_eye_phi,
            pupil_center_normal_x=self.left_eye_pupil_center_normal_x,
            pupil_center_normal_y=self.left_eye_pupil_center_normal_y,
            pupil_center_normal_z=self.left_eye_pupil_center_normal_z,
            eye_d=1,
        )

        synchronized_session_data = FreemocapSessionDataClass(
            timestamps=self.synchronized_timestamps,
            mediapipe_skel_fr_mar_dim=self.raw_session_data.mediapipe_skel_fr_mar_xyz[
                freemocap_start_frame:freemocap_end_frame, :, :
            ],
            right_eye_pupil_labs_data=synchronized_right_eye_data,
            left_eye_pupil_labs_data=synchronized_left_eye_data,
        )
        return synchronized_session_data

    def clip_eye_data(self):
        self.right_eye_timestamps_clipped = self.raw_session_data.right_eye_pupil_labs_data.timestamps[
            self.right_eye_start_frame : self.right_eye_end_frame
        ]

        self.right_eye_pupil_center_normal_x_clipped = (
            self.raw_session_data.right_eye_pupil_labs_data.pupil_center_normal_x[
                self.right_eye_start_frame : self.right_eye_end_frame
            ]
        )

        self.right_eye_pupil_center_normal_y_clipped = (
            self.raw_session_data.right_eye_pupil_labs_data.pupil_center_normal_y[
                self.right_eye_start_frame : self.right_eye_end_frame
            ]
        )

        self.right_eye_pupil_center_normal_z_clipped = (
            self.raw_session_data.right_eye_pupil_labs_data.pupil_center_normal_z[
                self.right_eye_start_frame : self.right_eye_end_frame
            ]
        )

        self.right_eye_theta_clipped = self.raw_session_data.right_eye_pupil_labs_data.theta[
            self.right_eye_start_frame : self.right_eye_end_frame
        ]

        self.right_eye_phi_clipped = self.raw_session_data.right_eye_pupil_labs_data.phi[
            self.right_eye_start_frame : self.right_eye_end_frame
        ]

        self.left_eye_timestamps_clipped = self.raw_session_data.left_eye_pupil_labs_data.timestamps[
            self.left_eye_start_frame : self.left_eye_end_frame
        ]

        self.left_eye_pupil_center_normal_x_clipped = (
            self.raw_session_data.left_eye_pupil_labs_data.pupil_center_normal_x[
                self.left_eye_start_frame : self.left_eye_end_frame
            ]
        )

        self.left_eye_pupil_center_normal_y_clipped = (
            self.raw_session_data.left_eye_pupil_labs_data.pupil_center_normal_y[
                self.left_eye_start_frame : self.left_eye_end_frame
            ]
        )

        self.left_eye_pupil_center_normal_z_clipped = (
            self.raw_session_data.left_eye_pupil_labs_data.pupil_center_normal_z[
                self.left_eye_start_frame : self.left_eye_end_frame
            ]
        )

        self.left_eye_theta_clipped = self.raw_session_data.left_eye_pupil_labs_data.theta[
            self.left_eye_start_frame : self.left_eye_end_frame
        ]

        self.left_eye_phi_clipped = self.raw_session_data.left_eye_pupil_labs_data.phi[
            self.left_eye_start_frame : self.left_eye_end_frame
        ]

    def resample_eye_data(self):
        freemocap_timestamps = self.synchronized_timestamps
        right_eye_timestamps = self.right_eye_timestamps_clipped
        left_eye_timestamps = self.left_eye_timestamps_clipped

        self.right_eye_pupil_center_normal_x = np.interp(
            freemocap_timestamps,
            right_eye_timestamps,
            self.right_eye_pupil_center_normal_x_clipped,
        )
        self.right_eye_pupil_center_normal_y = np.interp(
            freemocap_timestamps,
            right_eye_timestamps,
            self.right_eye_pupil_center_normal_y_clipped,
        )
        self.right_eye_pupil_center_normal_z = np.interp(
            freemocap_timestamps,
            right_eye_timestamps,
            self.right_eye_pupil_center_normal_z_clipped,
        )
        self.right_eye_theta = np.interp(freemocap_timestamps, right_eye_timestamps, self.right_eye_theta_clipped)
        self.right_eye_phi = np.interp(freemocap_timestamps, right_eye_timestamps, self.right_eye_phi_clipped)

        self.left_eye_pupil_center_normal_x = np.interp(
            freemocap_timestamps,
            left_eye_timestamps,
            self.left_eye_pupil_center_normal_x_clipped,
        )
        self.left_eye_pupil_center_normal_y = np.interp(
            freemocap_timestamps,
            left_eye_timestamps,
            self.left_eye_pupil_center_normal_y_clipped,
        )
        self.left_eye_pupil_center_normal_z = np.interp(
            freemocap_timestamps,
            left_eye_timestamps,
            self.left_eye_pupil_center_normal_z_clipped,
        )
        self.left_eye_theta = np.interp(freemocap_timestamps, left_eye_timestamps, self.left_eye_theta_clipped)
        self.left_eye_phi = np.interp(freemocap_timestamps, left_eye_timestamps, self.left_eye_phi_clipped)

    def normalize_eye_data(self):
        self.right_eye_pupil_center_normal_x = self.right_eye_pupil_center_normal_x / np.linalg.norm(
            self.right_eye_pupil_center_normal_x
        )
        self.right_eye_pupil_center_normal_y = self.right_eye_pupil_center_normal_y / np.linalg.norm(
            self.right_eye_pupil_center_normal_y
        )
        self.right_eye_pupil_center_normal_z = self.right_eye_pupil_center_normal_z / np.linalg.norm(
            self.right_eye_pupil_center_normal_z
        )

        self.left_eye_pupil_center_normal_x = self.left_eye_pupil_center_normal_x / np.linalg.norm(
            self.left_eye_pupil_center_normal_x
        )
        self.left_eye_pupil_center_normal_y = self.left_eye_pupil_center_normal_y / np.linalg.norm(
            self.left_eye_pupil_center_normal_y
        )
        self.left_eye_pupil_center_normal_z = self.left_eye_pupil_center_normal_z / np.linalg.norm(
            self.left_eye_pupil_center_normal_z
        )

    def show_debug_plots(self, vor_frame_start, vor_frame_end):

        ###########################
        # Plot Raw Data
        ###########################
        fig = plt.figure(num=653412, figsize=(10, 20))
        fig.suptitle("Raw data")
        ax1 = fig.add_subplot(411)
        ax1.plot(
            self.raw_session_data.right_eye_pupil_labs_data.timestamps,
            self.raw_session_data.right_eye_pupil_labs_data.pupil_center_normal_x,
            ".-",
            label="right_eye_pupil_center_normal_x",
        )
        ax1.plot(
            self.raw_session_data.right_eye_pupil_labs_data.timestamps,
            self.raw_session_data.right_eye_pupil_labs_data.pupil_center_normal_y,
            ".-",
            label="right_eye_pupil_center_normal_y",
        )
        ax1.plot(
            self.raw_session_data.right_eye_pupil_labs_data.timestamps,
            self.raw_session_data.right_eye_pupil_labs_data.pupil_center_normal_z,
            ".-",
            label="right_eye_pupil_center_normal_z",
        )
        ax1.legend(loc="upper left")

        ax2 = fig.add_subplot(412)
        ax2.plot(
            self.raw_session_data.right_eye_pupil_labs_data.timestamps,
            self.raw_session_data.right_eye_pupil_labs_data.theta,
            ".-",
            label="right_eye_theta",
        )
        ax2.plot(
            self.raw_session_data.right_eye_pupil_labs_data.timestamps,
            self.raw_session_data.right_eye_pupil_labs_data.phi,
            ".-",
            label="right_eye_phi",
        )
        ax2.legend(loc="upper left")

        ax3 = fig.add_subplot(413)
        ax3.plot(
            self.synchronized_timestamps,
            self.left_eye_pupil_center_normal_x,
            ".-",
            label="left_eye_pupil_center_normal_x",
        )
        ax3.plot(
            self.synchronized_timestamps,
            self.left_eye_pupil_center_normal_y,
            ".-",
            label="left_eye_pupil_center_normal_y",
        )
        ax3.plot(
            self.synchronized_timestamps,
            self.left_eye_pupil_center_normal_z,
            ".-",
            label="left_eye_pupil_center_normal_z",
        )
        ax3.legend(loc="upper left")

        ax4 = fig.add_subplot(414)
        ax4.plot(
            self.raw_session_data.left_eye_pupil_labs_data.timestamps,
            self.raw_session_data.left_eye_pupil_labs_data.theta,
            ".-",
            label="left_eye_theta",
        )
        ax4.plot(
            self.raw_session_data.left_eye_pupil_labs_data.timestamps,
            self.raw_session_data.left_eye_pupil_labs_data.phi,
            ".-",
            label="left_eye_phi",
        )
        ax4.legend(loc="upper left")

        ###########################
        # Plot synchronized data
        ###########################

        fig = plt.figure(num=65341, figsize=(10, 20))
        fig.suptitle("Synchronized data")
        ax1 = fig.add_subplot(411)
        ax1.plot(
            self.synchronized_timestamps[vor_frame_start:vor_frame_end],
            self.right_eye_pupil_center_normal_x[vor_frame_start:vor_frame_end],
            ".-",
            label="right_eye_pupil_center_normal_x",
        )
        ax1.plot(
            self.synchronized_timestamps[vor_frame_start:vor_frame_end],
            self.right_eye_pupil_center_normal_y[vor_frame_start:vor_frame_end],
            ".-",
            label="right_eye_pupil_center_normal_y",
        )
        ax1.plot(
            self.synchronized_timestamps[vor_frame_start:vor_frame_end],
            self.right_eye_pupil_center_normal_z[vor_frame_start:vor_frame_end],
            ".-",
            label="right_eye_pupil_center_normal_z",
        )
        ax1.legend(loc="upper left")

        ax2 = fig.add_subplot(412)
        ax2.plot(
            self.synchronized_timestamps[vor_frame_start:vor_frame_end],
            self.right_eye_theta[vor_frame_start:vor_frame_end],
            ".-",
            label="right_eye_theta",
        )
        ax2.plot(
            self.synchronized_timestamps[vor_frame_start:vor_frame_end],
            self.right_eye_phi[vor_frame_start:vor_frame_end],
            ".-",
            label="right_eye_phi",
        )
        ax2.legend(loc="upper left")

        ax3 = fig.add_subplot(413)
        ax3.plot(
            self.synchronized_timestamps[vor_frame_start:vor_frame_end],
            self.left_eye_pupil_center_normal_x[vor_frame_start:vor_frame_end],
            ".-",
            label="left_eye_pupil_center_normal_x",
        )
        ax3.plot(
            self.synchronized_timestamps[vor_frame_start:vor_frame_end],
            self.left_eye_pupil_center_normal_y[vor_frame_start:vor_frame_end],
            ".-",
            label="left_eye_pupil_center_normal_y",
        )
        ax3.plot(
            self.synchronized_timestamps[vor_frame_start:vor_frame_end],
            self.left_eye_pupil_center_normal_z[vor_frame_start:vor_frame_end],
            ".-",
            label="left_eye_pupil_center_normal_z",
        )
        ax3.legend(loc="upper left")

        ax4 = fig.add_subplot(414)
        ax4.plot(
            self.synchronized_timestamps[vor_frame_start:vor_frame_end],
            self.left_eye_theta[vor_frame_start:vor_frame_end],
            ".-",
            label="left_eye_theta",
        )
        ax4.plot(
            self.synchronized_timestamps[vor_frame_start:vor_frame_end],
            self.left_eye_phi[vor_frame_start:vor_frame_end],
            ".-",
            label="left_eye_phi",
        )
        ax4.legend(loc="upper left")

        plt.show()
