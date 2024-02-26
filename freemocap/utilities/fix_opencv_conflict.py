import logging
import subprocess

logger = logging.getLogger(__name__)


def fix_opencv_conflict():
    logger.warning("Conflicting versions of opencv found, uninstalling `opencv-python`")
    try:
        subprocess.run(["pip", "uninstall", "-y", "opencv-python", "opencv-contrib-python"], check=True)
    except subprocess.CalledProcessError:
        logger.warning(
            "Failed to uninstall existing opencv distributions, calibration may not work without manually uninstalling them and reinstalling with `pip install opencv-contrib-python==4.8.*`"
        )
        raise

    try:
        subprocess.run(["pip", "install", "opencv-contrib-python==4.8.*"], check=True)
    except subprocess.CalledProcessError:
        logger.error(
            "Failed to install opencv-contrib-python, please run `pip install opencv-contrib-python==4.8.*` manually"
        )
        raise
    logger.info(
        "Successfully fixed opencv conflict by uninstalling all versions and reinstalling opencv-contrib-python"
    )
