from ._version import get_versions

__version__ = get_versions()["version"]
del get_versions

from freemocap import fmc_runme


def RunMe(sessionID=None, stage=1, useOpenPose=True,  openPoseDummyRun = False,  useMediaPipe=False, useDLC=True, dlcConfigPath=None, debug=False):\

    fmc_runme.Run(sessionID, stage, useOpenPose, openPoseDummyRun, useMediaPipe, useDLC, dlcConfigPath, debug)