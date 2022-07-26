from typing import List
import numpy as np
from matplotlib import pyplot as plt

plt.set_loglevel("warning")


def create_timestamp_diagnostic_plots(camera_timestamps: List):
    """plot some diagnostics to assess quality of camera sync"""
    pass


#     multi_frame_timestamp_list = (
#         self.multi_frame_timestamp_logger.timestamps_in_seconds_from_unspecified_zero
#     )
#     # multi_frame_interval_list = self.multi_frame_interval_list
#
#     fig = plt.figure(figsize=(18, 10))
#     max_frame_duration = 0.1
#     ax1 = plt.subplot(
#         231,
#         title="Camera Frame Timestamp vs Frame#",
#         xlabel="Frame#",
#         ylabel="Timestamp (sec)",
#     )
#     ax2 = plt.subplot(
#         232,
#         ylim=(0, max_frame_duration),
#         title="Camera Frame Duration Trace",
#         xlabel="Frame#",
#         ylabel="Duration (sec)",
#     )
#     ax3 = plt.subplot(
#         233,
#         xlim=(0, max_frame_duration),
#         title="Camera Frame Duration Histogram (count)",
#         xlabel="Duration(s, 1ms bins)",
#         ylabel="Probability",
#     )
#     ax4 = plt.subplot(
#         234,
#         title="MuliFrame Timestamp vs Frame#",
#         xlabel="Frame#",
#         ylabel="Timestamp (sec)",
#     )
#     ax5 = plt.subplot(
#         235,
#         ylim=(0, max_frame_duration),
#         title="Multi Frame Duration/Span Trace",
#         xlabel="Frame#",
#         ylabel="Duration (sec)",
#     )
#     ax6 = plt.subplot(
#         236,
#         xlim=(0, max_frame_duration),
#         title="MultiFrame Duration Histogram (count)",
#         xlabel="Duration(s, 1ms bins)",
#         ylabel="Probability",
#     )
#
#     for (
#             this_camera_id,
#             this_camera_timestamp_logger,
#     ) in self._webcam_timestamp_loggers.items():
#         this_camera_timestamps = this_camera_timestamp_logger._timestamps_from_zero
#         ax1.plot(this_camera_timestamps, label=f"Camera# {this_camera_id}")
#         ax1.legend()
#         ax2.plot(np.diff(this_camera_timestamps), ".")
#         ax3.hist(
#             np.diff(this_camera_timestamps),
#             bins=np.arange(0, max_frame_duration, 0.0025),
#             alpha=0.5,
#         )
#
#     ax4.plot(multi_frame_timestamp_list, color="darkslategrey", label=f"MultiFrame")
#     ax5.plot(
#         np.diff(np.asarray(multi_frame_timestamp_list)),
#         ".",
#         color="darkslategrey",
#         label="Multi Frame Duration",
#     )
#     # ax5.plot(
#     #     multi_frame_interval_list, ".", color="orangered", label="Frame TimeSpan"
#     # )
#     ax5.legend()
#     ax6.hist(
#         np.diff(np.asarray(multi_frame_timestamp_list)),
#         bins=np.arange(0, max_frame_duration, 0.0025),
#         density=True,
#         alpha=0.5,
#         color="darkslategrey",
#         label="Frame Duration",
#     )
#     # ax6.hist(
#     #     np.diff(multi_frame_interval_list),
#     #     bins=np.arange(0, max_frame_duration, 0.0025),
#     #     density=True,
#     #     alpha=0.5,
#     #     color="orangered",
#     #     label="Frame Timespan",
#     # )
#     ax5.legend()
#
#     fig_save_path = (
#             Path(get_session_folder_path(self._session_id))
#             / "camera_timestamp_diagnostics.png"
#     )
#     plt.savefig(str(fig_save_path))
#     logger.info(f"Saving diagnostic figure to - {str(fig_save_path)}")
#     # plt.show()
