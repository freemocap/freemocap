import logging
import subprocess
from importlib.metadata import distributions

logger = logging.getLogger(__name__)


def fix_opencv_conflict():
    installed_packages = {dist.metadata["Name"] for dist in distributions()}
    if "opencv-python" in installed_packages and "opencv-contrib-python" in installed_packages:

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


if __name__ == "__main__":
    fix_opencv_conflict()
