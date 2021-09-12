from freemocap.fmc_mediapipe import runMediaPipe
import freemocap as fmc
from pathlib import Path
import sys

fmc.RunMe(
    # sessionID = 'sesh_2021-08-29_17_55_45',
    sessionID=None,
    stage = 1,
    useOpenPose=False, 
    runOpenPose=True, 
    useMediaPipe=True,
    runMediaPipe = True,
    useDLC=False, 
    recordVid = True ,
    reconstructionConfidenceThreshold = 0.7,
    calVideoFrameLength = -1,
)
