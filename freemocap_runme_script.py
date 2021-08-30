from freemocap.fmc_mediapipe import runMediaPipe
import freemocap as fmc
from pathlib import Path
import sys


fmc.RunMe(
    sessionID = 'sesh_2021-08-29_15_26_34',
    stage = 4,
    useOpenPose=True, 
    runOpenPose=True, 
    useMediaPipe=True, 
    runMediaPipe = True,
    useDLC=False, 
    recordVid = True,
    reconstructionConfidenceThreshold = 0.5,
    calVideoFrameLength = -1,
)
