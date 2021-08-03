from ._version import get_versions

__version__ = get_versions()["version"]
del get_versions

from freemocap import fmc_runme, fmc_demo

def RunMe(sessionID=None,stage=1,useOpenPose=True, openPoseDummyRun = False, useMediaPipe=False,useDLC=False,dlcConfigPath=None,debug=False,setDataPath=False,userDataPath = None, recordVid=False):
    fmc_runme.Run(sessionID,stage,useOpenPose,openPoseDummyRun, useMediaPipe,useDLC,dlcConfigPath,debug,setDataPath,userDataPath,recordVid)

def RunDemo():
    sample_data_location = fmc_demo.DemoSetup() #run a bunch of GUIs, get the location of the directory where the data folder with the sample data is 
    fmc_runme.Run(sessionID = 'sesh_21-07-18_170130',stage = 6,useOpenPose = True,useDLC = True, userDataPath = sample_data_location)

