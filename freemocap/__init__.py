from ._version import get_versions

__version__ = get_versions()["version"]
del get_versions

from freemocap import fmc_runme
from freemocap import play_skeleton_animation

def RunMe(sessionID=None, stage=1, useOpenPose=True,  openPoseDummyRun = False,  useMediaPipe=False, useDLC=True, dlcConfigPath=None, recordVid=False, debug=False):

    fmc_runme.Run(sessionID, stage, useOpenPose, openPoseDummyRun, useMediaPipe, useDLC, dlcConfigPath, recordVid, debug)