import freemocap as fmc
from pathlib import Path

dlcConfigPath = Path(r"C:\Users\jonma\Dropbox\DLC_Models\PinkGreenRedJugglingBalls-JSM-2021-05-31\config.yaml")
fmc.RunMe(sessionID = 'sesh_21-07-08_131030', stage=7, openPoseDummyRun=True, useDLC = False, dlcConfigPath=dlcConfigPath) 