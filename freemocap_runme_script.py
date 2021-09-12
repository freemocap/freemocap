from freemocap.fmc_mediapipe import runMediaPipe
import freemocap as fmc
from pathlib import Path
import sys

fmc.RunMe(
    # sessionID = 'sesh_2021-08-29_17_55_45',
    sessionID=None,
    stage = 5,
    useOpenPose=True, 
    runOpenPose=True, 
    useMediaPipe=False,
    runMediaPipe = True,
    useDLC=False, 
    recordVid = True ,
    reconstructionConfidenceThreshold = 0.0,
    calVideoFrameLength = 60,
)
