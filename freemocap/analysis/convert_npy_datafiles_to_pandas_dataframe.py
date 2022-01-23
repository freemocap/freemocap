#%%
import numpy as np 
import pandas as pd
from pathlib import Path
from ruamel.yaml import YAML
yaml = YAML()
#%%
path_to_session_congfig = Path("C:\Users\jonma\Dropbox\FreeMoCapProject\FreeMocap_Data\sesh_2021-09-14_10_22_15\sesh_2021-09-14_10_22_15_config.yaml")
configList = yaml.load(configFile, Loader=yaml.FullLoader)