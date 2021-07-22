import freemocap as fmc
from pathlib import Path
import socket 

dlcConfigPath = Path(r"C:\Users\jonma\Dropbox\DLC_Models\PinkGreenRedJugglingBalls-JSM-2021-05-31\config.yaml")

if socket.gethostname() == 'DESKTOP-DCG6K4F':
     fmc.RunMe( sessionID='sesh_21-07-19_231345', stage=7, openPoseDummyRun=True, useDLC = True, dlcConfigPath=dlcConfigPath, recordVid = False) 
else:
    fmc.RunMe( stage = 7, useDLC = True, dlcConfigPath=dlcConfigPath, recordVid = False) 
