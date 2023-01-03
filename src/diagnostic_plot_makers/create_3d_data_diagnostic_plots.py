import logging
from pathlib import Path
from typing import Union

import numpy as np

from old_src.core_processes.mediapipe_stuff.mediapipe_skeleton_names_and_connections import (
    mediapipe_body_landmark_names,
)

logger = logging.getLogger(__name__)


def create_3d_data_diagnostic_plots(
    spatial_data3d_numFrames_numTrackedPoints_XYZ: np.ndarray,
    reprojection_error_data3d_numCams_numFrames_numTrackedPoints_error: np.ndarray,
    path_to_save_plots: Union[str, Path],
):
    """
    Create diagnostic plots for spot checking 3d data
    """

    logger.info("Creating 3d data diagnostic plots")
    # opportunistic load of matplotlib to avoid startup time costs
    from matplotlib import pyplot as plt

    plt.set_loglevel("warning")

    mean_reprojection_error_numFrames_numLandmark = np.mean(
        reprojection_error_data3d_numCams_numFrames_numTrackedPoints_error, axis=0
    )

    fig = plt.figure(figsize=(18, 10))
    ax1 = plt.subplot(411, title="X Data", xlabel="Frame#", ylabel="X position(mm)")
    ax2 = plt.subplot(412, title="Y Data", xlabel="Frame#", ylabel="Y position(mm)")
    ax3 = plt.subplot(413, title="Z Data", xlabel="Frame#", ylabel="Z position(mm)")
    ax4 = plt.subplot(
        414, title="Reprojection Error", xlabel="Frame#", ylabel="Error(mm)"
    )

    ax1.plot(spatial_data3d_numFrames_numTrackedPoints_XYZ[:, :, 0])
    ax1.legend(mediapipe_body_landmark_names)

    ax2.plot(spatial_data3d_numFrames_numTrackedPoints_XYZ[:, :, 1])
    ax2.legend(mediapipe_body_landmark_names)

    ax3.plot(spatial_data3d_numFrames_numTrackedPoints_XYZ[:, :, 2])
    ax3.legend(mediapipe_body_landmark_names)

    ax4.plot(mean_reprojection_error_numFrames_numLandmark[:, :, 0])
    ax4.legend(mediapipe_body_landmark_names)

    fig.savefig(path_to_save_plots)

    logger.info(f"Saving diagnostic figure as png")
    import matplotlib

    matplotlib.use("QtAgg")
    plt.show()
    plt.pause(0.1)
    f = 9
