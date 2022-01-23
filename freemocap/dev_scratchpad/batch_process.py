#%%
from pathlib import Path
import freemocap as fmc
import datetime
import logging
from rich import inspect
from rich.console import Console
console = Console()
import shutil
import pandas as pd
#%%



import socket
this_computer_name = socket.gethostname()

freemocap_data_path=None

if this_computer_name=='jon-hallway-XPS-8930':
    freemocap_data_path = Path('/home/jon/Dropbox/FreeMoCapProject/FreeMocap_Data')

elif this_computer_name == 'DESKTOP-DCG6K4F':
    freemocap_data_path = Path(r'C:\Users\jonma\Dropbox\FreeMoCapProject\FreeMocap_Data')
elif this_computer_name == 'DESKTOP-V3D343U':
    freemocap_data_path = Path(r'C:\Users\WindowsPC_Hallway\Dropbox\FreeMoCapProject\FreeMocap_Data')
elif this_computer_name == 'Jons-MacBook-Pro.local':
    freemocap_data_path = Path('/Users/jon/Dropbox/FreeMoCapProject\FreeMocap_Data')

#%%

batch_process_ID = datetime.datetime.now().strftime("batch_process_%Y-%m-%d_%H_%M_%S")
path_to_log_file = freemocap_data_path / (batch_process_ID+'_log.txt')

logging.basicConfig(filename=str(path_to_log_file), filemode='w', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logging.info('Log file create :D')

#%%
dataframe_init_dict = {
                        'viable_folder_paths':[],
                        'outVid_exists_bool':[]}
viable_folders_dataframe = pd.DataFrame(dataframe_init_dict)
out_vid_path = freemocap_data_path / 'output_animation_videos'
out_vid_path.mkdir(exist_ok=True)

with console.status('Looking for viable folders (that contain synced vids)'):
    for this_folder in freemocap_data_path.glob('**/*'):
        if this_folder.is_dir():
            #check if there is a synced video folder in here
            for this_sub_folder in this_folder.iterdir():
                if this_sub_folder.is_dir():
                    if this_sub_folder.name.lower()[0:4]=='sync':
                        logging.info('Viable Folder found at {}'.format(str(this_folder)))
                        out_vid_exists = False
                        for this_mp4 in this_folder.glob('*.mp4'):
                            out_vid_exists = True
                            shutil.copy(this_mp4, str(out_vid_path))
                            logging.info('OutVid - {} - Copied to - {}'.format(str(this_mp4), str(out_vid_path)))
                        viable_folders_dataframe.loc[len(viable_folders_dataframe.index)] = [str(this_folder), out_vid_exists]


# %%
viable_folders_dataframe