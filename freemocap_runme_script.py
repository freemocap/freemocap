import freemocap as fmc
from pathlib import Path
import socket 



fmc.RunMe(  stage=5, 
            useOpenPose=True, 
            openPoseDummyRun=True, 
            useMediaPipe=True, 
            useDLC=False, 
            recordVid = True,
            reconstructionConfidenceThreshold = 0.2,
            calVideoFrameLength = -1) 
