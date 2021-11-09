from pathlib import Path

from pathos.helpers import mp as pathos_mp_helper
from rich.console import Console

from FMC_MultiCamera import FMC_MultiCamera
import freemocap as fmc



if __name__ == '__main__':
    pathos_mp_helper.freeze_support()
    console = Console() #create rich console to catch and print exceptions

    import socket
    this_computer_name = socket.gethostname()

    freemocap_data_path=None
    in_rotation_codes_list=None
        
    if this_computer_name=='jon-hallway-XPS-8930':
        freemocap_data_path = Path('/home/jon/Dropbox/FreeMoCapProject/FreeMocap_Data')
        in_rotation_codes_list = ['cv2.ROTATE_90_COUNTERCLOCKWISE', 'cv2.ROTATE_90_COUNTERCLOCKWISE', 'cv2.ROTATE_90_CLOCKWISE', 'cv2.ROTATE_90_CLOCKWISE', 'cv2.ROTATE_90_CLOCKWISE', ]
    elif this_computer_name == 'DESKTOP-DCG6K4F':
        freemocap_data_path = Path(r'C:\Users\jonma\Dropbox\FreeMoCapProject\FreeMocap_Data')


    try:
        multi_cam = FMC_MultiCamera(save_path=str(freemocap_data_path), rotation_codes_list=in_rotation_codes_list)
        multi_cam.start(standalone_mode=True)        
    except Exception:
        console.print_exception()
        
    fmc.RunMe(multi_cam._rec_name, stage=3)
    