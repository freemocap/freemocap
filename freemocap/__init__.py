from ._version import get_versions

# __version__ = get_versions()["version"]
# del get_versions

from freemocap.fmc_runme import RunMe
from freemocap import fmc_demo, fmc_runme

# from freemocap import fmc_runme, fmc_demo #JSM NOTE - there's gotta be a better way to do this lol

# def RunMe(sessionID=None,
#             stage=1,
#             useOpenPose=True, 
#             openPoseDummyRun=False,
#             useMediaPipe=False,
#             useDLC=False,
#             dlcConfigPath=None,
#             debug=False,
#             setDataPath=False,
#             userDataPath = None, 
#             recordVid=False,
#             reconstructionConfidenceThreshold = .8,
#             charucoSquareSize = 36,
#             ):
#     """ 
#     Passes user-set values from the freemocap_runme_script to the fmc_runme.Run function (and allows the user to run the pipeline with just an fmc.RunMe command)
#     """  
#     fmc_runme.Run(sessionID,
#     stage,
#     useOpenPose,
#     openPoseDummyRun, 
#     useMediaPipe,
#     useDLC,
#     dlcConfigPath,
#     debug,
#     setDataPath,
#     userDataPath,
#     recordVid)

def RunDemo():
    """ 
    Will (eventually) download sample data from Figshare, and run the animation for it
    """  
    sample_data_location, sample_data_name = fmc_demo.DemoSetup() #run a bunch of GUIs, get the location of the directory where the data folder with the sample data is 
    #fmc_runme.RunMe(sessionID = sample_data_name,stage = 5,useOpenPose = False, useMediaPipe = True,useDLC = True, userDataPath = sample_data_location)