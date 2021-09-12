from freemocap.fmc_mediapipe import runMediaPipe
import freemocap as fmc
from pathlib import Path
import sys

fmc.RunMe(
    sessionID = 'sesh_2021-09-09_17_23_44',
    # sessionID=None,
    stage = 5,
    useOpenPose=False, 
    runOpenPose=True, 
    useMediaPipe=True,
    runMediaPipe = True,
    useDLC=False, 
    recordVid = True ,
    reconstructionConfidenceThreshold = 0.5,
    calVideoFrameLength = 60,
)
