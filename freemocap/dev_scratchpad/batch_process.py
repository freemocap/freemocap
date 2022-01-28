#%%
from pathlib import Path
import freemocap as fmc
import datetime
import logging
from rich import inspect
from rich import print
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
out_vid_path = freemocap_data_path / 'output_animation_videos'
out_vid_path.mkdir(exist_ok=True)

csv_path = out_vid_path / 'viable_folders_status.csv'

detect_folders_to_process_bool = False
if detect_folders_to_process_bool:
    dataframe_init_dict = {'viable_folder_paths':[],
                           'outVid_exists_bool':[]}
    viable_folders_dataframe = pd.DataFrame(dataframe_init_dict)

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
                                # shutil.copy(this_mp4, str(out_vid_path))
                                # logging.info('OutVid - {} - Copied to - {}'.format(str(this_mp4), str(out_vid_path)))
                            viable_folders_dataframe.loc[len(viable_folders_dataframe.index)] = [str(this_folder), out_vid_exists]
    viable_folders_dataframe.to_csv(csv_path, index=False)
    logging.info('List of all viable session folders saved to {}'.format(str(csv_path)))
else: 
    viable_folders_dataframe = pd.read_csv(csv_path)
    logging.info('Loaded csv with list viable session folders from {}'.format(str(csv_path)))



# %%


# %%
folders_to_process = viable_folders_dataframe[viable_folders_dataframe["outVid_exists_bool"]==False]
for this_item in folders_to_process['viable_folder_paths']:
    this_session_id = Path(this_item).name
    print('Starting to process SessionID: {}'.format(this_session_id))
    logging.info('Starting to process SessionID: {}'.format(this_session_id))
    try:
        fmc.RunMe(sessionID = this_session_id, stage=3, useBlender=True, showAnimation=False)
        logging.info('SessionID: {} processed successfully!'.format(this_session_id))
    except Exception:
        console.print_exception(Exception)
        logging.info('SessionID: {} failed to process'.format(this_session_id))

