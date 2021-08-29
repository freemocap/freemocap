from freemocap.fmc_mediapipe import runMediaPipe
import freemocap as fmc
from pathlib import Path
import socket 

try:
    fmc.RunMe(  stage=5,
                useOpenPose=False, 
                runOpenPose=True, 
                useMediaPipe=True, 
                runMediaPipe = True,
                useDLC=False, 
                recordVid = True,
                reconstructionConfidenceThreshold = 0.5,
                calVideoFrameLength = -1) 
except:
    print("Unexpected error:", sys.exc_info()[0])
    raise