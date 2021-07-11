import freemocap as fmc
from pathlib import Path

dlcConfigPath = Path(r"C:\Users\jonma\Dropbox\DLC_Models\PinkGreenRedJugglingBalls-JSM-2021-05-31\config.yaml")
fmc.RunMe(stage=4, openPoseDummyRun=True, dlcConfigPath=dlcConfigPath) 