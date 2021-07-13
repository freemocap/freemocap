from ._version import get_versions

__version__ = get_versions()["version"]
del get_versions

from freemocap import fmc_runme

def RunMe(sessionID=None,stage=1,useOpenPose=True,useMediaPipe=False,useDLC=True,dlcConfigPath=None,debug=False,setDataPath=False):
    fmc_runme.Run(sessionID,stage,useOpenPose,useMediaPipe,useDLC,dlcConfigPath,debug,setDataPath)