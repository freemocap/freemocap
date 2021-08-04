import freemocap as fmc
from pathlib import Path
import socket 

dlcConfigPath = Path(r"C:\Users\jonma\Dropbox\DLC_Models\PinkGreenRedJugglingBalls-JSM-2021-05-31\config.yaml")

if socket.gethostname() == 'DESKTOP-DCG6K4F':
     fmc.RunMe( stage=7, openPoseDummyRun=True, useDLC = True, dlcConfigPath=dlcConfigPath, recordVid = True) 
else:
    fmc.RunMe(sessionID = 'sesh_21-07-29_112223',stage = 7,useOpenPose=True, useMediaPipe=True) 
